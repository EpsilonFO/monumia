"""Tests des trois étages de prospection (scripts/prospection/).

Aucun réseau (`httpx.MockTransport`), aucun modèle (`fake_provider`). Ce qui
est vérifié, dans l'ordre du pipeline :

  - les recettes RÉELLES de `territoires.yaml` se chargent et se valident : ce
    fichier est la mémoire de ce qu'on a appris de chaque site, et une entrée
    cassée fait échouer un balayage entier au premier appel réseau ;
  - la collecte trouve les fiches et écarte ce qui est déjà au catalogue ;
  - le tri ne transforme jamais un oubli du modèle en refus ;
  - la lecture n'invente ni PDF ni chiffre ;
  - la fiche produite se relit à la machine (bloc « Slugs proposés »).

Run from backend/:  uv run pytest tests/test_prospection.py
"""

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import providall  # noqa: E402
from pipeline.web import Fetcheur, reinitialiser_delais  # noqa: E402
from prospection.annuaire import sites_departementaux  # noqa: E402
from prospection.collecte import (  # noqa: E402
    Candidat,
    Collecte,
    collecter,
    dedoublonner,
    liens,
    titre_et_chapeau,
)
from prospection.fiche import attribuer_slugs, parser_slugs, rendre_fiche, taches  # noqa: E402
from prospection.lecture import Lecture, LectureFiche, kebab, lire, slug_final  # noqa: E402
from prospection.territoires import (  # noqa: E402
    Strategie,
    Territoire,
    aides_existantes,
    charger_territoires,
    selectionner,
)
from prospection.tri import (  # noqa: E402
    MOTIF_SANS_TITRE,
    TriCandidat,
    a_lire,
    doctrine,
    prompt_systeme,
    trier,
)
from providall.testing import chat_reply, fake_provider, json_reply  # noqa: E402

from aides_schema import Aide  # noqa: E402
from labels import DEPARTEMENT_LABELS, REGION_LABELS  # noqa: E402

JOUR = date(2026, 9, 6)

ACCUEIL = """\
<html><body>
<h1>Guide des aides</h1>
<ul>
  <li><a href="/dispositif1">Restauration du patrimoine protégé</a> — jusqu'à 40 %</li>
  <li><a href="/dispositif2">Aide aux festivals</a> — programmation en plein air</li>
  <li><a href="/dispositif3">Bourse d'écriture pour auteurs</a> — résidence individuelle</li>
  <li><a href="/actualites/le-budget-2027">Le budget 2027</a></li>
  <li><a href="https://ailleurs.example/x">Un site partenaire</a></li>
</ul>
<p>Le guide recense l'ensemble des dispositifs de la collectivité, thème par thème,
et permet de déposer une demande en ligne. Les dispositifs sont mis à jour chaque
trimestre par les services. Pour toute question, contacter le service des aides.</p>
</body></html>
"""

FICHE = """\
<html><body>
<h1>Restauration du patrimoine protégé</h1>
<p>La collectivité soutient la restauration des édifices protégés au titre des
monuments historiques appartenant à une commune, un EPCI ou une personne privée.</p>
<p>Le taux d'intervention est de 40 % des dépenses éligibles, plafonné à
150 000 euros par opération.</p>
<p><a href="/documents/reglement-2027.pdf">Règlement d'intervention (PDF)</a></p>
<p>Les demandes se déposent avant le 31 mars de chaque année, accompagnées d'un
devis détaillé, de l'arrêté de protection et d'un plan de financement.</p>
</body></html>
"""


def territoire(**kw) -> Territoire:
    base = {
        "nom": "Région d'exemple",
        "type": "region",
        "prefixe_slug": "ex",
        "statut": "pret",
        "guides": ["https://guide.example/"],
        "strategie": {"type": "liste_html"},
        "motif_fiche": r"^https://guide\.example/dispositif\d+$",
    }
    return Territoire.model_validate({**base, **kw})


def aide(slug: str, url: str | None = None, **kw) -> Aide:
    return Aide.model_validate(
        {
            "slug": slug,
            "nom": slug,
            "organisme": "Région",
            "categorie": "region",
            "type": "subvention",
            "description": "x",
            "source": {"url_officielle": url} if url else {},
            **kw,
        }
    )


def repondre(request: httpx.Request) -> httpx.Response:
    chemin = request.url.path
    if chemin.startswith("/dispositif"):
        return httpx.Response(200, text=FICHE, headers={"content-type": "text/html"})
    if chemin.endswith(".pdf"):
        return httpx.Response(200, content=b"%PDF-1.4", headers={"content-type": "application/pdf"})
    if chemin == "/vide":
        return httpx.Response(
            200, text="<html><body></body></html>", headers={"content-type": "text/html"}
        )
    if chemin == "/absent":
        return httpx.Response(404, text="rien")
    return httpx.Response(200, text=ACCUEIL, headers={"content-type": "text/html"})


class BaseProspection(unittest.TestCase):
    def setUp(self):
        reinitialiser_delais()
        self.fetcheur = Fetcheur(transport=httpx.MockTransport(repondre), delai_s=0.0)
        self.addCleanup(self.fetcheur.close)


# ---------------------------------------------------------------------------
# Recettes
# ---------------------------------------------------------------------------


class TestTerritoiresReels(unittest.TestCase):
    """Le fichier du dépôt, tel qu'il sera lu en production."""

    @classmethod
    def setUpClass(cls):
        cls.territoires = charger_territoires()

    def test_treize_regions_et_cent_un_departements(self):
        regions = [c for c, t in self.territoires.items() if t.type == "region"]
        departements = [c for c, t in self.territoires.items() if t.type == "departement"]
        self.assertEqual(len(regions), 13)
        self.assertEqual(len(departements), 101)
        self.assertEqual(set(departements), set(DEPARTEMENT_LABELS))
        self.assertTrue(set(regions) <= set(REGION_LABELS))

    def test_les_recettes_pretes_ont_un_motif_de_fiche(self):
        for cle, t in self.territoires.items():
            if t.statut == "pret":
                self.assertTrue(t.motif_fiche, f"{cle} : recette prête sans motif_fiche")

    def test_normandie_exige_les_entetes_navigateur(self):
        normandie = self.territoires["normandie"]
        self.assertEqual(normandie.entetes, "navigateur")
        self.assertEqual(len(normandie.pages_paginees()), 12)

    def test_hauts_de_france_reconnait_ses_fiches_et_ses_pdf(self):
        hdf = self.territoires["hauts-de-france"]
        self.assertTrue(hdf.fiche_probable("https://guide-aides.hautsdefrance.fr/dispositif748"))
        self.assertFalse(hdf.fiche_probable("https://guide-aides.hautsdefrance.fr/rubrique3"))
        self.assertTrue(
            hdf.pdf_probable(
                "https://guide-aides.hautsdefrance.fr/spip.php?fichier_dispositif=2046"
            )
        )

    def test_la_corse_na_pas_durl_fabriquee(self):
        corse = self.territoires["corse"]
        self.assertEqual(corse.statut, "sans_point_entree")
        self.assertEqual(corse.guides, [])

    def test_les_sans_point_entree_sont_ecartes_par_defaut(self):
        tous = selectionner(self.territoires, regions=True, departements=True)
        self.assertNotIn("corse", tous)
        self.assertIn("corse", selectionner(self.territoires, ["corse"], forcer=True))


class TestValidation(unittest.TestCase):
    def test_pagination_sans_marqueur_refusee(self):
        with self.assertRaises(ValueError):
            Strategie(type="pagination", patron="https://x/page2")

    def test_sitemap_sans_url_refuse(self):
        with self.assertRaises(ValueError):
            Strategie(type="sitemap")

    def test_sitemap_accepte_une_liste_durl(self):
        s = Strategie(type="sitemap", url=["https://x/a.xml", "https://x/b.xml"])
        self.assertEqual(s.urls_sitemap, ["https://x/a.xml", "https://x/b.xml"])
        self.assertEqual(
            Strategie(type="sitemap", url="https://x/a.xml").urls_sitemap, ["https://x/a.xml"]
        )

    def test_sitemap_liste_vide_refusee(self):
        with self.assertRaises(ValueError):
            Strategie(type="sitemap", url=[])

    def test_statut_pret_sans_guide_refuse(self):
        with self.assertRaises(ValueError):
            territoire(guides=[])

    def test_motif_invalide_refuse(self):
        with self.assertRaises(ValueError):
            territoire(motif_fiche="[non fermé")

    def test_prefixe_dun_departement_doit_etre_son_numero(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "t.yaml"
            chemin.write_text(
                "'71':\n  nom: Saône-et-Loire\n  type: departement\n  prefixe_slug: sl\n"
                "  statut: sans_point_entree\n  strategie: {type: decouverte}\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                charger_territoires(chemin)


class TestAidesExistantes(unittest.TestCase):
    def test_par_prefixe_et_par_hard_filters(self):
        corpus = {
            "ex-restauration": aide("ex-restauration"),
            "region-machin": aide("region-machin", hard_filters={"regions": ["normandie"]}),
            "autre": aide("autre"),
        }
        t = territoire()
        trouvees = aides_existantes("normandie", t, corpus)
        self.assertEqual(set(trouvees), {"ex-restauration", "region-machin"})


# ---------------------------------------------------------------------------
# Étage 1
# ---------------------------------------------------------------------------


class TestCollecte(BaseProspection):
    def test_liste_html_retient_les_fiches_et_ecarte_le_reste(self):
        collecte = collecter(territoire(), self.fetcheur, {})
        urls = {c.url for c in collecte.candidats}
        self.assertEqual(
            urls,
            {
                "https://guide.example/dispositif1",
                "https://guide.example/dispositif2",
                "https://guide.example/dispositif3",
            },
        )

    def test_le_titre_et_le_contexte_sont_captes(self):
        collecte = collecter(territoire(), self.fetcheur, {})
        premier = next(c for c in collecte.candidats if c.url.endswith("dispositif1"))
        self.assertEqual(premier.titre, "Restauration du patrimoine protégé")
        self.assertIn("40 %", premier.extrait)

    def test_les_aides_deja_au_catalogue_sont_ecartees(self):
        corpus = {"ex-deja": aide("ex-deja", "https://guide.example/dispositif1/")}
        collecte = collecter(territoire(), self.fetcheur, corpus)
        urls = {c.url for c in collecte.candidats}
        self.assertNotIn("https://guide.example/dispositif1", urls)
        self.assertEqual(collecte.doublons, [("https://guide.example/dispositif1", "ex-deja")])

    def test_sans_guide_rien_et_une_note(self):
        collecte = collecter(territoire(statut="sans_point_entree", guides=[]), self.fetcheur, {})
        self.assertEqual(collecte.candidats, [])
        self.assertIn("aucun guide renseigné", collecte.notes[0])

    def test_page_vide_signalee(self):
        collecte = collecter(territoire(guides=["https://guide.example/vide"]), self.fetcheur, {})
        self.assertTrue(any("SPA" in n for n in collecte.notes))

    def test_page_en_erreur_signalee(self):
        collecte = collecter(territoire(guides=["https://guide.example/absent"]), self.fetcheur, {})
        self.assertTrue(any("erreur" in n for n in collecte.notes))

    def test_sitemap(self):
        xml = (
            '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url><loc>https://guide.example/dispositif1</loc></url>"
            "<url><loc>https://guide.example/actualites/x</loc></url>"
            "</urlset>"
        )

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith(".xml"):
                return httpx.Response(200, text=xml, headers={"content-type": "application/xml"})
            return repondre(request)

        with Fetcheur(transport=httpx.MockTransport(handler), delai_s=0.0) as f:
            collecte = collecter(
                territoire(strategie={"type": "sitemap", "url": "https://guide.example/s.xml"}),
                f,
                {},
            )
        self.assertEqual([c.url for c in collecte.candidats], ["https://guide.example/dispositif1"])
        # Un sitemap ne rend que des URL : la fiche est ouverte pour son titre,
        # sans quoi l'étage 2 trierait sur le seul slug.
        self.assertEqual(collecte.candidats[0].titre, "Restauration du patrimoine protégé")
        self.assertIn("édifices protégés", collecte.candidats[0].extrait)
        self.assertEqual(collecte.pages_visitees, 2)

    def test_deux_sitemaps_dedoublonnes(self):
        """Grand Est range ses appels à projets dans un sitemap à part."""
        sitemaps = {
            "/a.xml": ["https://guide.example/dispositif1", "https://guide.example/dispositif2"],
            "/b.xml": ["https://guide.example/dispositif2", "https://guide.example/dispositif3"],
        }
        ouvertes: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            chemin = request.url.path
            if chemin in sitemaps:
                corps = "".join(f"<url><loc>{u}</loc></url>" for u in sitemaps[chemin])
                return httpx.Response(
                    200,
                    text='<?xml version="1.0"?><urlset xmlns='
                    f'"http://www.sitemaps.org/schemas/sitemap/0.9">{corps}</urlset>',
                    headers={"content-type": "application/xml"},
                )
            ouvertes.append(chemin)
            return repondre(request)

        with Fetcheur(transport=httpx.MockTransport(handler), delai_s=0.0) as f:
            collecte = collecter(
                territoire(
                    strategie={
                        "type": "sitemap",
                        "url": ["https://guide.example/a.xml", "https://guide.example/b.xml"],
                    }
                ),
                f,
                {},
            )
        self.assertEqual(
            [c.url for c in collecte.candidats],
            [
                "https://guide.example/dispositif1",
                "https://guide.example/dispositif2",
                "https://guide.example/dispositif3",
            ],
        )
        # dispositif2 est dans les deux sitemaps : ouvert une seule fois.
        self.assertEqual(len(ouvertes), 3)
        self.assertEqual(len([n for n in collecte.notes if "URL énumérées" in n]), 2)

    def test_sitemap_page_injoignable_donne_un_titre_vide(self):
        xml = (
            '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url><loc>https://guide.example/dispositif1</loc></url>"
            "</urlset>"
        )

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith(".xml"):
                return httpx.Response(200, text=xml, headers={"content-type": "application/xml"})
            return httpx.Response(500, text="boum")

        with Fetcheur(transport=httpx.MockTransport(handler), delai_s=0.0) as f:
            collecte = collecter(
                territoire(strategie={"type": "sitemap", "url": "https://guide.example/s.xml"}),
                f,
                {},
            )
        self.assertEqual(len(collecte.candidats), 1)
        self.assertEqual(collecte.candidats[0].titre, "")
        self.assertTrue(any("1 sans titre lisible" in n for n in collecte.notes))


class TestTitreEtChapeau(unittest.TestCase):
    def page(self, html: str, **kw):
        from pipeline.web import Page

        return Page(
            url="https://x/a",
            url_finale="https://x/a",
            status=kw.pop("status", 200),
            content_type=kw.pop("content_type", "text/html"),
            contenu=b"",
            texte=html,
            **kw,
        )

    def test_ignore_les_listes_et_les_titres_secondaires(self):
        page = self.page(
            "<html><head><title>Ignoré - Le Site</title></head><body>"
            "<h1>Anticiper le manque d'eau</h1>"
            "<h5>Aide correspondante au Pacte pour les ruralités</h5>"
            '<p><a href="/plus">En savoir plus sur ce dispositif régional</a></p>'
            "<p>Aide régionale</p>"
            "<ul><li>Une avance de trésorerie de 30 % dès le démarrage du projet</li></ul>"
            "<p>Bénéficiez de l'aide régionale pouvant aller jusqu'à 100 000 euros.</p>"
            "</body></html>"
        )
        titre, chapeau = titre_et_chapeau(page)
        self.assertEqual(titre, "Anticiper le manque d'eau")
        self.assertEqual(
            chapeau, "Bénéficiez de l'aide régionale pouvant aller jusqu'à 100 000 euros."
        )

    def test_repli_sur_la_balise_title(self):
        page = self.page(
            "<html><head><title>Aide  aux  moulins</title></head><body>"
            "<h2>Pas un H1</h2></body></html>"
        )
        titre, _chapeau = titre_et_chapeau(page)
        self.assertEqual(titre, "Aide aux moulins")

    def test_page_en_erreur_ne_rend_rien(self):
        page = self.page("<html><body><h1>Titre</h1></body></html>", status=500)
        self.assertEqual(titre_et_chapeau(page), ("", ""))

    def test_chapeau_plafonne(self):
        from prospection.collecte import MAX_CAR_EXTRAIT

        page = self.page(f"<html><body><h1>T</h1><p>{'a' * 900}</p></body></html>")
        _titre, chapeau = titre_et_chapeau(page)
        self.assertEqual(len(chapeau), MAX_CAR_EXTRAIT)

    def test_pagination_sarrete_quand_rien_de_neuf(self):
        vues: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            vues.append(str(request.url))
            return repondre(request)

        with Fetcheur(transport=httpx.MockTransport(handler), delai_s=0.0) as f:
            collecter(
                territoire(
                    strategie={
                        "type": "pagination",
                        "patron": "https://guide.example/?p={n}",
                        "de": 0,
                        "a": 30,
                    }
                ),
                f,
                {},
            )
        # Toutes les pages rendent la même liste : l'arrêt anticipé doit couper
        # bien avant la borne haute de 30.
        self.assertLessEqual(len(vues), 4)

    def test_jsonl_aller_retour(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "candidats.jsonl"
            collecte = Collecte(candidats=[Candidat("https://x/1", "Titre", "extrait", "test")])
            collecte.ecrire(chemin)
            self.assertEqual(Collecte.lire(chemin), collecte.candidats)


class TestDedoublonnage(unittest.TestCase):
    def tache(self, slug: str, url: str, statut: str):
        from pipeline.etat import Tache

        return Tache(titre=slug, url=url, territoire="ex", statut=statut)

    def test_ignore_www_https_et_slash_final(self):
        corpus = {"deja": aide("deja", "http://www.guide.example/aide/")}
        retenus, doublons, en_file = dedoublonner(
            [Candidat("https://guide.example/aide"), Candidat("https://guide.example/autre")],
            corpus,
        )
        self.assertEqual([c.url for c in retenus], ["https://guide.example/autre"])
        self.assertEqual(doublons, [("https://guide.example/aide", "deja")])
        self.assertEqual(en_file, [])

    def test_le_formulaire_compte_aussi(self):
        corpus = {"deja": aide("deja", source={"formulaire_url": "https://guide.example/form"})}
        _retenus, doublons, _en_file = dedoublonner(
            [Candidat("https://guide.example/form")], corpus
        )
        self.assertEqual(len(doublons), 1)

    def test_une_url_deja_en_file_nest_pas_retriee(self):
        """Les cinq `ignore` de Grand Est revenaient à chaque passage, en `-2`."""
        file = {"ex-ecartee": self.tache("ex-ecartee", "https://guide.example/aide/", "ignore")}
        retenus, doublons, en_file = dedoublonner(
            [Candidat("https://guide.example/aide"), Candidat("https://guide.example/autre")],
            {},
            file,
        )
        self.assertEqual([c.url for c in retenus], ["https://guide.example/autre"])
        self.assertEqual(doublons, [])
        self.assertEqual(en_file, [("https://guide.example/aide", "ex-ecartee", "ignore")])

    def test_une_url_ingeree_mais_absente_du_corpus_nest_pas_retriee(self):
        """Ingérée, en échec, en cours : tous les statuts comptent, pas seulement `ignore`."""
        for statut in ("ingere", "echec", "en_cours", "valide", "a_valider"):
            file = {"ex-deja": self.tache("ex-deja", "https://guide.example/aide", statut)}
            retenus, _doublons, en_file = dedoublonner(
                [Candidat("https://guide.example/aide")], {}, file
            )
            self.assertEqual(retenus, [], statut)
            self.assertEqual(en_file[0][2], statut)

    def test_le_catalogue_prime_sur_la_file(self):
        corpus = {"ex-deja": aide("ex-deja", "https://guide.example/aide")}
        file = {"ex-deja": self.tache("ex-deja", "https://guide.example/aide", "ingere")}
        _retenus, doublons, en_file = dedoublonner(
            [Candidat("https://guide.example/aide")], corpus, file
        )
        self.assertEqual(len(doublons), 1)
        self.assertEqual(en_file, [])


class TestLiens(unittest.TestCase):
    def page(self, html: str):
        from pipeline.web import Page

        return Page(
            url="https://x/a",
            url_finale="https://x/guide",
            status=200,
            content_type="text/html",
            contenu=b"",
            texte=html,
        )

    def test_un_lien_qui_enveloppe_une_carte_entiere_nest_pas_perdu(self):
        """paysdelaloire.fr, 2026-09-11 : 14 liens perdus sur 187, dont les 12 fiches.

        Le `<a>` enveloppe la carte entière ; html2text en rend un libellé sur
        dix lignes, que le balayage ligne à ligne ne voyait pas.
        """
        page = self.page(
            "<html><body>"
            '<a href="/les-aides/aap-handicap-et-tourisme">'
            "<ul><li>Économie et Entreprise</li><li>Tourisme</li></ul>"
            "<h3>AAP Handicap et Tourisme</h3>"
            "<p>Améliorer l'accessibilité touristique des sites de visite.</p>"
            "<ul><li>Associations</li><li>Entreprises</li></ul>"
            "<span>En savoir plus</span></a>"
            "</body></html>"
        )
        trouves = liens(page)
        self.assertEqual(len(trouves), 1)
        titre, url, contexte = trouves[0]
        self.assertEqual(url, "https://x/les-aides/aap-handicap-et-tourisme")
        # Les puces sont les étiquettes et les bénéficiaires : le titre est la
        # plus longue ligne qui n'en est pas une.
        self.assertIn("accessibilité touristique", titre)
        self.assertNotIn("*", titre)
        self.assertIn("Associations", contexte)

    def test_un_lien_sur_une_ligne_garde_son_titre_et_sa_ligne(self):
        """Le cas courant ne doit rien changer : même titre, même contexte."""
        page = self.page(
            "<html><body><p>Avant. "
            '<a href="/fiche1">Restauration du patrimoine</a> jusqu\'à 40 %.</p></body></html>'
        )
        titre, url, contexte = liens(page)[0]
        self.assertEqual(titre, "Restauration du patrimoine")
        self.assertEqual(url, "https://x/fiche1")
        self.assertIn("Avant.", contexte)
        self.assertIn("40 %", contexte)

    def test_un_libelle_ne_deborde_pas_sur_le_lien_suivant(self):
        page = self.page(
            '<html><body><p>Voir [1] plus bas.</p><p><a href="/fiche1">Fiche 1</a></p>'
            '<p><a href="/fiche2">Fiche 2</a></p></body></html>'
        )
        self.assertEqual([u for _t, u, _c in liens(page)], ["https://x/fiche1", "https://x/fiche2"])

    def test_titre_du_libelle(self):
        from prospection.collecte import titre_du_libelle

        self.assertEqual(titre_du_libelle("  Aide aux  moulins "), "Aide aux moulins")
        self.assertEqual(titre_du_libelle(""), "")
        self.assertEqual(
            titre_du_libelle("* Tourisme\n\nUne aide longue et descriptive\n* Associations"),
            "Une aide longue et descriptive",
        )
        # Rien que des puces : on rend la plus longue plutôt que rien.
        self.assertEqual(
            titre_du_libelle("* court\n* une puce plus longue"), "* une puce plus longue"
        )

    def test_resolution_relative_contre_lurl_finale(self):
        from pipeline.web import Page

        page = Page(
            url="https://x/a",
            url_finale="https://x/guide/",
            status=200,
            content_type="text/html",
            contenu=b"",
            texte='<a href="fiche1">Fiche 1</a>',
        )
        self.assertEqual(liens(page)[0][1], "https://x/guide/fiche1")


# ---------------------------------------------------------------------------
# Étage 2
# ---------------------------------------------------------------------------


def client(modele="ds-flash") -> providall.Client:
    return providall.Client(modele, api_key="faux", retry=providall.RetryPolicy(retries=0))


class TestTri(unittest.TestCase):
    def setUp(self):
        self.candidats = [
            Candidat("https://guide.example/dispositif1", "Restauration du patrimoine"),
            Candidat("https://guide.example/dispositif2", "Aide aux festivals"),
            Candidat("https://guide.example/dispositif3", "Bourse d'écriture"),
        ]

    def test_doctrine_extraite_du_skill(self):
        texte = doctrine()
        self.assertIn("Le spectre", texte)
        self.assertIn("test d'admission", texte)
        self.assertIn("Ce qu'on écarte", texte)
        # La doctrine large du 2026-09-11 : si ces phrases disparaissent du
        # skill, les deux prompts repartent sur un tri étroit sans prévenir.
        self.assertIn("faire vivre", texte)
        self.assertIn("retenir par défaut", texte.lower())
        self.assertIn("absolument rien", texte.lower())

    def test_familles_coherentes(self):
        from typing import get_args

        from prospection.tri import FAMILLES, FAMILLES_DESCRIPTION, Famille, familles_rendues

        self.assertEqual(set(FAMILLES), set(get_args(Famille)))
        for famille, description in FAMILLES_DESCRIPTION.items():
            self.assertTrue(description.strip(), famille)
        self.assertIn("energie_climat", familles_rendues())

    def test_le_prompt_du_tri_liste_les_familles(self):
        systeme = prompt_systeme(territoire(), {})
        self.assertIn("eau_nature_domaine", systeme)
        self.assertIn("Natura 2000", systeme)

    def test_famille_hors_perimetre_sur_un_retenir_devient_adjacente(self):
        c = Candidat("https://guide.example/dispositif4", "Prêt aux entreprises du tourisme")
        reponse = {
            "resultats": [
                {"url": c.url, "decision": "retenir", "famille": "hors_perimetre", "motif": "m"}
            ]
        }
        with fake_provider(json_reply(reponse)):
            tries = trier([c], territoire(), {}, client())
        self.assertEqual(tries[0].decision, "retenir")
        self.assertEqual(tries[0].famille, "adjacente")

    def test_famille_hors_perimetre_sur_un_ecarter_est_conservee(self):
        c = Candidat("https://guide.example/dispositif4", "Bourse de mobilité internationale")
        reponse = {
            "resultats": [
                {"url": c.url, "decision": "ecarter", "famille": "hors_perimetre", "motif": "m"}
            ]
        }
        with fake_provider(json_reply(reponse)):
            tries = trier([c], territoire(), {}, client())
        self.assertEqual(tries[0].famille, "hors_perimetre")

    def test_le_prompt_liste_les_aides_deja_au_catalogue(self):
        systeme = prompt_systeme(territoire(), {"ex-deja": aide("ex-deja")})
        self.assertIn("ex-deja", systeme)
        self.assertIn("déjà au catalogue", systeme)

    def test_tri_nominal(self):
        reponse = {
            "resultats": [
                {"url": c.url, "decision": d, "famille": f, "motif": "m"}
                for c, d, f in zip(
                    self.candidats,
                    ["retenir", "douteux", "ecarter"],
                    ["restauration_bati", "spectacles_manifestations", "hors_perimetre"],
                    strict=True,
                )
            ]
        }
        with fake_provider(json_reply(reponse)):
            tries = trier(self.candidats, territoire(), {}, client())
        self.assertEqual([t.decision for t in tries], ["retenir", "douteux", "ecarter"])
        self.assertEqual(len(a_lire(tries)), 2)

    def test_url_oubliee_devient_douteuse(self):
        reponse = {
            "resultats": [
                {
                    "url": self.candidats[0].url,
                    "decision": "retenir",
                    "famille": "restauration_bati",
                }
            ]
        }
        with fake_provider(json_reply(reponse)):
            tries = trier(self.candidats, territoire(), {}, client())
        self.assertEqual([t.decision for t in tries], ["retenir", "douteux", "douteux"])
        self.assertIn("absente de la réponse", tries[1].motif)

    def test_url_inventee_ignoree(self):
        reponse = {
            "resultats": [
                {"url": "https://guide.example/dispositif999", "decision": "retenir"},
                {"url": self.candidats[0].url, "decision": "retenir"},
            ]
        }
        with fake_provider(json_reply(reponse)):
            tries = trier(self.candidats, territoire(), {}, client())
        self.assertEqual({t.url for t in tries}, {c.url for c in self.candidats})

    def test_lot_en_echec_devient_douteux(self):
        with fake_provider(chat_reply("pas du JSON")):
            tries = trier(self.candidats, territoire(), {}, client())
        self.assertTrue(all(t.decision == "douteux" for t in tries))
        self.assertEqual(len(a_lire(tries)), 3)

    def test_ecarter_sans_titre_devient_douteux(self):
        """Grand Est 2026-09-08 : 173 URL écartées sur leur seul slug, jamais ouvertes."""
        nu = Candidat("https://guide.example/dispositif4")
        reponse = {
            "resultats": [
                {
                    "url": nu.url,
                    "decision": "ecarter",
                    "famille": "adjacente",
                    "motif": "sécheresse, hors patrimoine",
                }
            ]
        }
        with fake_provider(json_reply(reponse)):
            tries = trier([nu], territoire(), {}, client())
        self.assertEqual(tries[0].decision, "douteux")
        self.assertTrue(tries[0].motif.startswith(MOTIF_SANS_TITRE))
        self.assertIn("sécheresse", tries[0].motif)
        self.assertEqual(tries[0].famille, "adjacente")
        self.assertEqual(a_lire(tries), [nu.url])

    def test_ecarter_avec_titre_reste_ecarter(self):
        titre = Candidat("https://guide.example/dispositif4", "Bourse de mobilité internationale")
        reponse = {
            "resultats": [{"url": titre.url, "decision": "ecarter", "motif": "aide à la personne"}]
        }
        with fake_provider(json_reply(reponse)):
            tries = trier([titre], territoire(), {}, client())
        self.assertEqual(tries[0].decision, "ecarter")
        self.assertEqual(tries[0].motif, "aide à la personne")

    def test_un_contexte_seul_suffit_a_laisser_ecarter(self):
        """Le garde-fou porte sur l'absence TOTALE d'information, pas sur le titre seul."""
        c = Candidat("https://guide.example/dispositif4", "", "Bourse d'écriture pour auteurs")
        reponse = {"resultats": [{"url": c.url, "decision": "ecarter", "motif": "individuel"}]}
        with fake_provider(json_reply(reponse)):
            tries = trier([c], territoire(), {}, client())
        self.assertEqual(tries[0].decision, "ecarter")


# ---------------------------------------------------------------------------
# Étage 3
# ---------------------------------------------------------------------------

LECTURE = {
    "retenir": True,
    "famille": "restauration_bati",
    "titre": "Restauration du patrimoine protégé",
    "montant_taux": "40 %, plafond 150 000 €",
    "beneficiaires": "communes, EPCI, personnes privées",
    "note": "Cœur de cible.",
    "slug_propose": "restauration-patrimoine-protege",
    "urls_pdf": [
        "https://guide.example/documents/reglement-2027.pdf",
        "https://guide.example/documents/invente.pdf",
    ],
    "priorite": "haute",
}


class TestLecture(BaseProspection):
    def test_lecture_nominale(self):
        with fake_provider(json_reply(LECTURE)):
            lecture = lire(
                Candidat("https://guide.example/dispositif1"),
                territoire(),
                self.fetcheur,
                client(),
            )
        self.assertTrue(lecture.retenue)
        assert lecture.fiche is not None
        self.assertEqual(lecture.fiche.montant_taux, "40 %, plafond 150 000 €")

    def test_les_pdf_inventes_sont_retires(self):
        with fake_provider(json_reply(LECTURE)):
            lecture = lire(
                Candidat("https://guide.example/dispositif1"),
                territoire(),
                self.fetcheur,
                client(),
            )
        assert lecture.fiche is not None
        self.assertEqual(
            lecture.fiche.urls_pdf, ["https://guide.example/documents/reglement-2027.pdf"]
        )

    def test_page_absente(self):
        with fake_provider(json_reply(LECTURE)):
            lecture = lire(
                Candidat("https://guide.example/absent"), territoire(), self.fetcheur, client()
            )
        self.assertFalse(lecture.retenue)
        self.assertIn("404", lecture.erreur or "")

    def test_page_vide_signalee_sans_appel_de_modele(self):
        with fake_provider(json_reply(LECTURE)) as faux:
            lecture = lire(
                Candidat("https://guide.example/vide"), territoire(), self.fetcheur, client()
            )
        self.assertIn("SPA", lecture.erreur or "")
        self.assertEqual(faux.calls, 0)

    def test_modele_en_echec(self):
        with fake_provider(chat_reply("pas du JSON")):
            lecture = lire(
                Candidat("https://guide.example/dispositif1"),
                territoire(),
                self.fetcheur,
                client(),
            )
        self.assertFalse(lecture.retenue)
        self.assertIn("lecture impossible", lecture.erreur or "")

    def test_la_lecture_charge_la_meme_doctrine_que_le_tri(self):
        """Une doctrine écrite en dur ici recalerait ce que le tri a laissé passer."""
        from prospection.lecture import consigne

        texte = consigne()
        self.assertIn("test d'admission", texte)
        self.assertIn("n'invente rien", texte)
        self.assertIn("eau_nature_domaine", texte)
        self.assertIn("retenir: true", texte)
        self.assertIn(doctrine(), texte)


class TestSlugs(unittest.TestCase):
    def test_kebab(self):
        self.assertEqual(
            kebab("Restauration du Patrimoine « protégé » !"), "restauration-du-patrimoine-protege"
        )

    def test_prefixe_ajoute_une_seule_fois(self):
        t = territoire()
        self.assertEqual(slug_final(t, "restauration", "x", set()), "ex-restauration")
        self.assertEqual(slug_final(t, "ex-restauration", "x", set()), "ex-restauration")

    def test_territoire_deja_en_tete_de_la_proposition_nest_pas_double(self):
        """Balayage Grand Est du 2026-09-08 : 8 slugs sur 42 en « region-grand-est-grand-est-… »."""
        t = territoire(nom="Grand Est", prefixe_slug="region-grand-est")
        for propose in (
            "grand-est-culture-et-creation-numerique",
            "grandest-culture-et-creation-numerique",
            "region-grand-est-culture-et-creation-numerique",
            "culture-et-creation-numerique",
        ):
            self.assertEqual(
                slug_final(t, propose, "x", set()),
                "region-grand-est-culture-et-creation-numerique",
                propose,
            )

    def test_troncature_sur_un_tiret_jamais_au_milieu_dun_mot(self):
        t = territoire(nom="Grand Est", prefixe_slug="region-grand-est")
        slug = slug_final(t, "aide-proprietaires-renovation-patrimoine-ardennes", "x", set())
        self.assertLessEqual(len(slug), 60)
        self.assertEqual(slug, "region-grand-est-aide-proprietaires-renovation-patrimoine")
        # Un slug qui tient en 60 n'est pas touché.
        self.assertEqual(
            slug_final(t, "soutien-memoire", "x", set()), "region-grand-est-soutien-memoire"
        )

    def test_collision_suffixee(self):
        t = territoire()
        self.assertEqual(
            slug_final(t, "restauration", "x", {"ex-restauration"}), "ex-restauration-2"
        )

    def test_repli_sur_le_titre(self):
        self.assertEqual(
            slug_final(territoire(), "", "Aide aux festivals", set()), "ex-aide-aux-festivals"
        )

    def test_deux_lectures_ne_partagent_pas_un_slug(self):
        lectures = [
            Lecture(
                Candidat(f"https://guide.example/dispositif{i}"),
                LectureFiche.model_validate({**LECTURE, "urls_pdf": []}),
            )
            for i in (1, 2)
        ]
        slugs = attribuer_slugs(territoire(), lectures, set())
        self.assertEqual(len(set(slugs.values())), 2)


# ---------------------------------------------------------------------------
# Fiche
# ---------------------------------------------------------------------------


class TestFiche(unittest.TestCase):
    def setUp(self):
        self.lectures = [
            Lecture(
                Candidat("https://guide.example/dispositif1", "Restauration"),
                LectureFiche.model_validate(
                    {**LECTURE, "urls_pdf": ["https://guide.example/documents/r.pdf"]}
                ),
            ),
            Lecture(
                Candidat("https://guide.example/dispositif3", "Bourse"),
                LectureFiche.model_validate(
                    {
                        "retenir": False,
                        "titre": "Bourse d'écriture",
                        "note": "Bénéficiaire individuel, aucun lien avec un lieu.",
                    }
                ),
            ),
            Lecture(Candidat("https://guide.example/dispositif9"), erreur="HTTP 500"),
        ]
        self.tries = [
            TriCandidat(
                url="https://guide.example/dispositif2", decision="ecarter", motif="hors sujet"
            )
        ]
        self.collecte = Collecte(
            notes=["3 URL trouvées"],
            doublons=[("https://x/1", "ex-deja")],
            en_file=[("https://x/2", "ex-ecartee", "ignore")],
        )
        self.slugs = attribuer_slugs(territoire(), self.lectures, set())
        self.markdown = rendre_fiche(
            "ex",
            territoire(),
            self.lectures,
            self.tries,
            self.collecte,
            {"ex-deja": aide("ex-deja")},
            self.slugs,
            jour=JOUR,
            cout="3 appel(s), $0.0100",
        )

    def test_structure_de_la_fiche(self):
        for titre in (
            "# Prospection — Région d'exemple — 2026-09-06",
            "## Candidates retenues",
            "## Écartées (et pourquoi)",
            "## Slugs proposés",
            "## Notes techniques",
        ):
            self.assertIn(titre, self.markdown)

    def test_la_retenue_est_dans_le_tableau_avec_ses_colonnes(self):
        ligne = next(li for li in self.markdown.splitlines() if li.startswith("| 1 |"))
        self.assertIn("Restauration du patrimoine protégé", ligne)
        self.assertIn("40 %, plafond 150 000 €", ligne)
        self.assertIn("restauration_bati", ligne)
        self.assertIn("1 document(s)", ligne)

    def test_les_ecartees_portent_leur_motif(self):
        self.assertIn("Bénéficiaire individuel", self.markdown)
        self.assertIn("hors sujet", self.markdown)

    def test_les_notes_techniques_disent_ce_qui_a_rate(self):
        self.assertIn("HTTP 500", self.markdown)
        self.assertIn("déjà au catalogue", self.markdown)
        self.assertIn("$0.0100", self.markdown)
        self.assertIn(
            "déjà en file d'attente (`ignore`) : https://x/2 → `ex-ecartee`", self.markdown
        )

    def test_les_requalifications_sont_comptees(self):
        markdown = rendre_fiche(
            "ex",
            territoire(),
            [],
            [
                TriCandidat(
                    url="https://guide.example/dispositif4",
                    decision="douteux",
                    motif=f"{MOTIF_SANS_TITRE} (sécheresse)",
                )
            ],
            Collecte(),
            {},
            {},
            jour=JOUR,
        )
        self.assertIn("1 élimination(s) prise(s) sans titre ni contexte", markdown)
        self.assertIn("requalifiée(s) en douteuses", markdown)

    def test_le_bloc_de_slugs_se_relit(self):
        relu = parser_slugs(self.markdown)
        self.assertEqual(
            relu, [("ex-restauration-patrimoine-protege", "https://guide.example/dispositif1")]
        )

    def test_les_taches_entrent_en_a_valider(self):
        creees = taches(
            "ex", territoire(), self.lectures, self.slugs, "data/reviews/x.md", jour=JOUR
        )
        self.assertEqual(list(creees), ["ex-restauration-patrimoine-protege"])
        tache = creees["ex-restauration-patrimoine-protege"]
        self.assertEqual(tache.statut, "a_valider")
        self.assertEqual(tache.priorite, "haute")
        self.assertEqual(tache.territoire, "ex")
        self.assertEqual(tache.urls_pdf, ["https://guide.example/documents/r.pdf"])

    def test_fiche_sans_aucune_retenue(self):
        markdown = rendre_fiche("ex", territoire(), [], [], Collecte(), {}, {}, jour=JOUR)
        self.assertIn("_aucune_", markdown)
        self.assertIn("_aucun_", markdown)
        self.assertEqual(parser_slugs(markdown), [])


# ---------------------------------------------------------------------------
# Point de contrôle humain (valider / ignorer)
# ---------------------------------------------------------------------------


class TestTransitions(unittest.TestCase):
    """`valider` / `ignorer`, et surtout ce qu'ils REFUSENT de rebasculer."""

    def setUp(self):
        import prospecter

        self.prospecter = prospecter
        self.dossier = tempfile.TemporaryDirectory()
        self.addCleanup(self.dossier.cleanup)
        self.etat_path = Path(self.dossier.name) / "file-attente.yaml"

    def _poser(self, **statuts):
        from pipeline.etat import Tache, ecrire

        ecrire(
            self.etat_path,
            {
                slug: Tache(
                    titre=slug,
                    url=f"https://guide.example/{slug}",
                    territoire="ex",
                    statut=statut,
                    ajoute_le=JOUR,
                )
                for slug, statut in statuts.items()
            },
        )

    def _lancer(self, sous_commande, *slugs, tout=False):
        import argparse

        from pipeline.etat import charger

        args = argparse.Namespace(
            territoire="ex", slugs=list(slugs), tout=tout, etat=self.etat_path
        )
        self.prospecter._transitionner(args, "valide" if sous_commande == "valider" else "ignore")
        return {s: t.statut for s, t in charger(self.etat_path).items()}

    def test_valider_un_slug_nomme_revient_sur_un_ignorer(self):
        """Sans ça, la seule issue est d'éditer le YAML à la main — vu le 2026-09-09."""
        self._poser(a="ignore", b="a_valider")
        self.assertEqual(self._lancer("valider", "a"), {"a": "valide", "b": "a_valider"})

    def test_tout_ne_ressuscite_jamais_les_ignorees(self):
        self._poser(a="ignore", b="a_valider")
        self.assertEqual(self._lancer("valider", tout=True), {"a": "ignore", "b": "valide"})

    def test_une_aide_ingeree_ou_en_cours_reste_intouchee(self):
        self._poser(a="ingere", b="en_cours", c="echec")
        self.assertEqual(
            self._lancer("valider", "a", "b", "c"),
            {"a": "ingere", "b": "en_cours", "c": "echec"},
        )


# ---------------------------------------------------------------------------
# Comparaison avec une liste externe
# ---------------------------------------------------------------------------


class TestComparer(unittest.TestCase):
    """`prospecter.py comparer` : pourquoi une URL du voisin nous manque."""

    def setUp(self):
        from pipeline.etat import Tache

        self.corpus = {"ex-deja": aide("ex-deja", "https://guide.example/dispositif1")}
        self.file = {
            "ex-ecartee": Tache(
                titre="Écartée",
                url="https://guide.example/dispositif2",
                territoire="ex",
                statut="ignore",
            ),
            "autre-territoire": Tache(
                titre="Ailleurs",
                url="https://guide.example/dispositif9",
                territoire="ailleurs",
                statut="ingere",
            ),
        }
        self.fiche = (
            "# Prospection\n\n## Écartées (et pourquoi)\n\n"
            "- **Bourse d'écriture** — https://guide.example/dispositif3 — bénéficiaire individuel\n"
            "- https://guide.example/dispositif4 — hors sujet au tri\n\n"
            "## Notes techniques\n\n"
            "- non lue : https://guide.example/dispositif5 — HTTP 500\n"
        )

    def _comparer(self, externes):
        from prospection.comparer import comparer

        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "fiche.md"
            chemin.write_text(self.fiche, encoding="utf-8")
            return comparer("ex", territoire(), externes, self.corpus, self.file, fiche=chemin)

    def test_lire_urls_tolere_puces_et_commentaires(self):
        from prospection.comparer import lire_urls

        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "urls.txt"
            chemin.write_text(
                "# une liste\n"
                "https://guide.example/a\n"
                "- https://guide.example/b (annoté)\n"
                "\n"
                "https://guide.example/a/\n",
                encoding="utf-8",
            )
            self.assertEqual(
                lire_urls(chemin), ["https://guide.example/a", "https://guide.example/b"]
            )

    def test_une_url_commune_dit_dou_on_la_connait(self):
        r = self._comparer(["https://guide.example/dispositif1/"])
        self.assertEqual(
            r.communes, [("https://guide.example/dispositif1/", "catalogue `ex-deja`")]
        )
        self.assertEqual(r.externes_seules, [])

    def test_la_file_compte_comme_nous_lavons(self):
        r = self._comparer(["https://guide.example/dispositif2"])
        self.assertEqual(r.communes[0][1], "file `ex-ecartee` (ignore)")

    def test_le_motif_dune_manquante_vient_de_la_fiche(self):
        r = self._comparer(
            [
                "https://guide.example/dispositif3",
                "https://guide.example/dispositif4",
                "https://guide.example/dispositif5",
                "https://guide.example/dispositif404",
            ]
        )
        motifs = dict(r.externes_seules)
        self.assertIn("bénéficiaire individuel", motifs["https://guide.example/dispositif3"])
        self.assertIn("hors sujet au tri", motifs["https://guide.example/dispositif4"])
        self.assertIn("HTTP 500", motifs["https://guide.example/dispositif5"])
        self.assertIn("jamais vue", motifs["https://guide.example/dispositif404"])

    def test_les_notres_seules_ignorent_les_autres_territoires(self):
        r = self._comparer([])
        urls = [u for u, _ in r.notres_seules]
        self.assertEqual(len(urls), 2)
        self.assertFalse(any("dispositif9" in u for u in urls))

    def test_rendu_lisible(self):
        from prospection.comparer import rendre

        texte = rendre(self._comparer(["https://guide.example/dispositif3"]), "ex")
        self.assertIn("Chez eux et pas chez nous (1)", texte)
        self.assertIn("bénéficiaire individuel", texte)


# ---------------------------------------------------------------------------
# Annuaire de l'État
# ---------------------------------------------------------------------------


REPONSE_ANNUAIRE = {
    "total_count": 3,
    "results": [
        {
            "nom": "Conseil départemental - Vendée",
            # Les colonnes composites de l'annuaire arrivent en JSON DANS une
            # chaîne : c'est ce qui rend le parsing non trivial.
            "site_internet": '[{"libelle": "", "valeur": "https://www.vendee.fr/"}]',
            "pivot": '[{"type_service_local": "cg", "code_insee_commune": ["85191"]}]',
        },
        {
            "nom": "Conseil départemental - Guadeloupe",
            "site_internet": '[{"libelle": "", "valeur": "https://www.cg971.fr/"}]',
            "pivot": '[{"type_service_local": "cg", "code_insee_commune": ["97105"]}]',
        },
        {
            "nom": "Mairie de Quelque-Part",
            "site_internet": '[{"valeur": "https://mairie.example/"}]',
            "pivot": '[{"type_service_local": "mairie", "code_insee_commune": ["12345"]}]',
        },
    ],
}


class TestAnnuaire(unittest.TestCase):
    def annuaire(self, pages):
        appels = []

        def handler(request: httpx.Request) -> httpx.Response:
            appels.append(str(request.url))
            charge = pages[min(len(appels) - 1, len(pages) - 1)]
            if isinstance(charge, int):
                return httpx.Response(charge, text="nope")
            return httpx.Response(200, json=charge, headers={"content-type": "application/json"})

        with Fetcheur(transport=httpx.MockTransport(handler), delai_s=0.0) as f:
            return sites_departementaux(f), appels

    def test_extrait_les_conseils_departementaux(self):
        sites, _ = self.annuaire([REPONSE_ANNUAIRE, {"results": []}])
        self.assertEqual(set(sites), {"85", "971"})
        self.assertEqual(sites["85"].url, "https://www.vendee.fr/")

    def test_ignore_ce_qui_nest_pas_un_conseil_departemental(self):
        sites, _ = self.annuaire([REPONSE_ANNUAIRE, {"results": []}])
        self.assertNotIn("12", sites)

    def test_loutre_mer_garde_ses_trois_chiffres(self):
        sites, _ = self.annuaire([REPONSE_ANNUAIRE, {"results": []}])
        self.assertIn("971", sites)
        self.assertNotIn("97", sites)

    def test_sarrete_sur_une_page_vide(self):
        _sites, appels = self.annuaire([REPONSE_ANNUAIRE, {"results": []}])
        self.assertEqual(len(appels), 2)

    def test_api_muette_donne_un_dictionnaire_vide(self):
        sites, appels = self.annuaire([503])
        self.assertEqual(sites, {})
        self.assertEqual(len(appels), 1)

    def test_json_casse_ne_leve_pas(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, text="{pas du json", headers={"content-type": "application/json"}
            )

        with Fetcheur(transport=httpx.MockTransport(handler), delai_s=0.0) as f:
            self.assertEqual(sites_departementaux(f), {})


if __name__ == "__main__":
    unittest.main()
