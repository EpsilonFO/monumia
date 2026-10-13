"""Tests du triage de la veille (scripts/veille_analyze.py).

Le triage décide QUI part à l'étage C (coûteux) et QUI part en ré-ingestion
complète (encore plus coûteux, et du temps humain). Deux règles portent
l'essentiel du risque et sont testées sous tous les angles :

  - une quote ne « régresse » que si elle était retrouvée dans la baseline ET
    que le document qui la justifiait a été re-téléchargé ;
  - une panne réseau n'escalade jamais.

Run from backend/:  uv run pytest tests/test_veille_analyze.py
"""

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from veille_analyze import (  # noqa: E402
    MIN_CONTENU_UTILE,
    analyze,
    contenu_utile,
    lignes_de_chrome,
)
from veille_collect import AideCollect, FetchResult, MonitoredUrl  # noqa: E402

from aides_schema import Aide  # noqa: E402

TODAY = date(2026, 8, 6)
URL = "https://ex.fr/aide"
PDF_URL = "https://ex.fr/reglement.pdf"

# Assez longue pour dépasser MIN_CONTENU_UTILE : sinon tous les tests butent
# d'abord sur la règle « page servie mais vide » et ne testent rien de ce
# qu'ils annoncent. C'est arrivé, d'où ce commentaire.
BASELINE = """# Aide à la restauration du patrimoine rural

## Bénéficiaires

Les propriétaires privés et les collectivités territoriales peuvent déposer un
dossier, dès lors que l'édifice est situé sur le territoire régional et qu'il
présente un intérêt patrimonial reconnu par le service de l'inventaire.

## Conditions d'éligibilité

Les édifices doivent être antérieurs à 1800.
Les travaux portent sur le gros œuvre : charpente, couverture, maçonnerie.
Un architecte du patrimoine est requis pour les édifices classés.
L'édifice doit être visible depuis l'espace public ou ouvert à la visite au
moins quarante jours par an, dont les journées européennes du patrimoine.

## Montant et modalités

La subvention est de 5 000 € en moyenne.
Le taux d'intervention est plafonné à 30 % du montant des travaux hors taxes.
Le dépôt se fait en ligne avant le 31 octobre.
Le versement intervient sur présentation des factures acquittées, après visite
de conformité du service instructeur.
"""


# Règlement de remplacement, de volume comparable à BASELINE : distingue une
# refonte éditoriale d'un simple défaut de collecte.
REGLEMENT_REMPLACE = """# Dispositif de soutien aux équipements sportifs

## Porteurs éligibles

Le dispositif est réservé aux collectivités territoriales et à leurs
groupements. Les associations et les propriétaires privés en sont exclus.

## Nature des opérations

Les opérations retenues portent sur la construction, l'extension ou la
rénovation thermique d'équipements sportifs couverts.
Le taux d'intervention est fixé à 30 % du montant hors taxes.
Les travaux d'entretien courant ne sont pas pris en charge.
Une visite préalable est organisée par le service des sports avant instruction.

## Dépôt

Le dossier est déposé sur le portail régional, au fil de l'eau.
La commission se réunit trois fois par an pour examiner les demandes reçues.
"""


def make_aide(**kwargs) -> Aide:
    base = {
        "slug": "mon-aide",
        "nom": "Aide test",
        "organisme": "Organisme test",
        "categorie": "region",
        "type": "subvention",
        "description": "Une aide de test.",
        "source": {"url_officielle": URL},
    }
    return Aide.model_validate({**base, **kwargs})


def condition(cond_id: str, quote: str) -> dict:
    return {"id": cond_id, "text": f"Condition {cond_id}", "kind": "info", "quote": quote}


def make_collect(
    aide: Aide,
    *,
    fresh: str | None = BASELINE,
    baseline: str | None = BASELINE,
    baseline_sha: str | None = "sha-baseline",
    fresh_sha: str = "sha-fraiche",
    status: int | None = 200,
    error: str | None = None,
    baseline_docs: list | None = None,
    extra_urls: list[MonitoredUrl] | None = None,
    baseline_path_name: str = "2026-07-01-page.md",
    baseline_urls: dict[str, str] | None = None,
) -> AideCollect:
    murl = MonitoredUrl(
        url=URL,
        role="officielle",
        # Un seul nom, parce que `_snapshot_baselines` ne retient que le
        # snapshot le PLUS RÉCENT de l'URL — même quand le dossier en garde
        # plusieurs. Les tests qui simulent ce cas surchargent ce nom.
        baseline_path=Path(baseline_path_name),
        baseline_sha=baseline_sha,
        baseline_body=baseline,
    )
    result = FetchResult(
        url=URL,
        status=status,
        error=error,
        raw_text=fresh,
        body_md=fresh,
        sha256=fresh_sha if fresh is not None else None,
    )
    urls = [murl, *(extra_urls or [])]
    return AideCollect(
        slug=aide.slug,
        urls=urls,
        fetched={URL: result},
        baseline_docs=(
            baseline_docs
            if baseline_docs is not None
            else ([("2026-07-01-page.md", baseline, "text")] if baseline else [])
        ),
        baseline_urls=baseline_urls or {},
    )


class TestPagesInchangees(unittest.TestCase):
    def test_sha_identique_court_circuite_le_diff(self):
        aide = make_aide()
        col = make_collect(aide, baseline_sha="meme-sha", fresh_sha="meme-sha")
        an = analyze(aide, col, today=TODAY)
        self.assertEqual(an.statut, "OK")
        self.assertTrue(an.urls[0].sha_identique)
        # Le diff n'est même pas calculé : c'est tout l'intérêt du chemin rapide.
        self.assertIsNone(an.urls[0].diff)

    def test_bruit_typographique_seul_reste_OK(self):
        # Le sha change (les CMS glissent un jeton à chaque requête) mais le
        # fond est identique : c'est le cas le plus fréquent du parc.
        aide = make_aide()
        cosmetique = BASELINE.replace("antérieurs à 1800", "antérieurs à 1800").replace(
            "5 000 €", "5 000 €"
        )
        an = analyze(aide, make_collect(aide, fresh=cosmetique), today=TODAY)
        self.assertEqual(an.statut, "OK")


class TestChangementsCirconscrits(unittest.TestCase):
    def test_montant_modifie_declenche_la_mise_a_jour(self):
        aide = make_aide()
        modifie = BASELINE.replace("5 000 €", "8 000 €")
        an = analyze(aide, make_collect(aide, fresh=modifie), today=TODAY)
        self.assertEqual(an.statut, "MAJ_LLM")
        self.assertTrue(any("a changé" in r for r in an.raisons))

    def test_refonte_complete_escalade(self):
        # Page entièrement réécrite, de volume comparable : ce n'est pas un
        # défaut de collecte, c'est un règlement remplacé.
        aide = make_aide()
        refonte = REGLEMENT_REMPLACE
        an = analyze(aide, make_collect(aide, fresh=refonte), today=TODAY)
        self.assertEqual(an.statut, "ESCALADE_INGESTION")
        self.assertTrue(any("refonte" in r for r in an.raisons))


class TestQuotes(unittest.TestCase):
    """Garde-fous du signal « citation disparue »."""

    def test_regression_declenche_la_mise_a_jour(self):
        aide = make_aide(
            conditions=[condition("architecte", "Un architecte du patrimoine est requis")]
        )
        # La phrase disparaît de la source, le reste ne bouge pas.
        fresh = BASELINE.replace(
            "Un architecte du patrimoine est requis pour les édifices classés.\n", ""
        )
        an = analyze(aide, make_collect(aide, fresh=fresh), today=TODAY)
        self.assertEqual(an.statut, "MAJ_LLM")
        self.assertEqual([q.cond_id for q in an.regressions], ["architecte"])

    def test_dette_preexistante_ne_declenche_rien(self):
        # La quote n'était DÉJÀ pas dans la baseline : c'est de la dette
        # d'ingestion, pas un changement de source. Sans ce garde-fou, 56 aides
        # partiraient au modèle dès le premier passage.
        aide = make_aide(
            conditions=[condition("jamais-vue", "Une phrase absente de partout depuis toujours")]
        )
        an = analyze(aide, make_collect(aide), today=TODAY)
        self.assertEqual(an.statut, "OK")
        self.assertEqual(an.regressions, [])
        self.assertEqual([q.cond_id for q in an.dette_quotes], ["jamais-vue"])

    def test_quote_justifiee_par_un_pdf_non_retelecharge_ne_declenche_rien(self):
        # 802 quotes du dépôt sont justifiées par un PDF souvent sans URL
        # connue : leur absence du HTML frais ne prouve rien.
        aide = make_aide(conditions=[condition("du-pdf", "Le plafond réglementaire est de 40 %")])
        col = make_collect(
            aide,
            baseline_docs=[
                ("2026-07-01-page.md", BASELINE, "text"),
                ("2026-07-01-reglement.pdf", "Le plafond réglementaire est de 40 %.", "pdf"),
            ],
        )
        an = analyze(aide, col, today=TODAY)
        self.assertEqual(an.statut, "OK")
        self.assertEqual(an.regressions, [])
        self.assertEqual([q.cond_id for q in an.non_recontrolables], ["du-pdf"])

    def test_quote_trouvee_dans_un_snapshot_plus_ancien_de_la_meme_page(self):
        # Régression vécue sur 35-faat : le dossier gardait deux snapshots de la
        # MÊME page, `find_quote_in_any` rattachait la quote au plus ancien, et
        # la table nom→URL ne connaissait que le plus récent. Les 4 citations
        # sortaient « non recontrôlables » alors que leur page venait d'être
        # re-téléchargée. 9 aides du dépôt sont dans ce cas, et ce nombre croît
        # à chaque ré-archivage. C'est la provenance lue dans les snapshots qui
        # tranche, pas le nom de fichier.
        aide = make_aide(
            conditions=[condition("architecte", "Un architecte du patrimoine est requis")]
        )
        fresh = BASELINE.replace(
            "Un architecte du patrimoine est requis pour les édifices classés.\n", ""
        )
        col = make_collect(
            aide,
            fresh=fresh,
            baseline_path_name="2026-08-24-page.md",
            baseline_docs=[
                ("2026-07-01-page.md", BASELINE, "text"),
                ("2026-08-24-page.md", BASELINE, "text"),
            ],
            baseline_urls={"2026-07-01-page.md": URL, "2026-08-24-page.md": URL},
        )
        an = analyze(aide, col, today=TODAY)
        self.assertEqual([q.cond_id for q in an.regressions], ["architecte"])
        self.assertEqual(an.non_recontrolables, [])
        self.assertEqual(an.couverture_quotes, (1, 1))

    def test_provenance_hors_perimetre_reste_non_recontrolable(self):
        # L'autre moitié de la règle : une provenance connue mais non
        # re-téléchargée ne rend pas la citation contrôlable pour autant.
        # Assouplir le garde-fou ne doit pas le désarmer.
        aide = make_aide(conditions=[condition("du-pdf", "Le plafond réglementaire est de 40 %")])
        col = make_collect(
            aide,
            baseline_docs=[
                ("2026-07-01-page.md", BASELINE, "text"),
                ("2026-07-01-reglement.pdf", "Le plafond réglementaire est de 40 %.", "pdf"),
            ],
            baseline_urls={"2026-07-01-page.md": URL, "2026-07-01-reglement.pdf": PDF_URL},
        )
        an = analyze(aide, col, today=TODAY)
        self.assertEqual(an.statut, "OK")
        self.assertEqual(an.regressions, [])
        self.assertEqual([q.cond_id for q in an.non_recontrolables], ["du-pdf"])

    def test_regressions_massives_escaladent(self):
        aide = make_aide(
            conditions=[
                condition("c1", "Les édifices doivent être antérieurs à 1800"),
                condition("c2", "La subvention est de 5 000 € en moyenne"),
                condition("c3", "Le dépôt se fait en ligne avant le 31 octobre"),
                condition("c4", "Les travaux portent sur le gros œuvre"),
            ]
        )
        # Le règlement est remplacé par un autre de volume comparable : toutes
        # les citations tombent.
        an = analyze(aide, make_collect(aide, fresh=REGLEMENT_REMPLACE), today=TODAY)
        self.assertEqual(an.statut, "ESCALADE_INGESTION")
        self.assertTrue(any("citations recontrôlables" in r or "refonte" in r for r in an.raisons))

    def test_quotes_ignorees_si_rien_n_a_pu_etre_telecharge(self):
        # Sans contenu frais, conclure « la citation a disparu » serait faux.
        aide = make_aide(
            conditions=[condition("c1", "Les édifices doivent être antérieurs à 1800")]
        )
        col = make_collect(aide, fresh=None, status=None, error="ConnectTimeout")
        an = analyze(aide, col, today=TODAY)
        self.assertEqual(an.quotes, [])


class TestErreursReseau(unittest.TestCase):
    def test_page_morte_escalade(self):
        aide = make_aide()
        an = analyze(aide, make_collect(aide, fresh=None, status=404), today=TODAY)
        self.assertEqual(an.statut, "ESCALADE_INGESTION")
        self.assertIn("morte", an.raisons[0])

    def test_timeout_est_reessayable_jamais_escalade(self):
        aide = make_aide()
        col = make_collect(aide, fresh=None, status=None, error="ConnectTimeout: délai dépassé")
        an = analyze(aide, col, today=TODAY)
        self.assertEqual(an.statut, "ERREUR_HTTP")

    def test_403_anti_bot_est_reessayable(self):
        aide = make_aide()
        an = analyze(aide, make_collect(aide, fresh=None, status=403), today=TODAY)
        self.assertEqual(an.statut, "ERREUR_HTTP")

    def test_500_est_reessayable(self):
        aide = make_aide()
        an = analyze(aide, make_collect(aide, fresh=None, status=503), today=TODAY)
        self.assertEqual(an.statut, "ERREUR_HTTP")

    def test_panne_generalisee_signalee_dans_la_raison(self):
        aide = make_aide()
        col = make_collect(aide, fresh=None, status=None, error="ConnectError")
        an = analyze(aide, col, today=TODAY, panne_generalisee=True)
        self.assertEqual(an.statut, "ERREUR_HTTP")
        self.assertIn("panne réseau généralisée", an.raisons[0])

    def test_page_servie_mais_vide_est_un_echec_de_collecte(self):
        # Mesuré sur neuf aides Auvergne-Rhône-Alpes : 200 OK, 980 octets de
        # coquille HTML, zéro caractère utile. La baseline prouve que la page
        # AVAIT du contenu : ce n'est donc pas le financeur qui l'a vidée, c'est
        # un rendu JavaScript ou un pare-feu. Ré-ingérer se heurterait au même
        # mur — d'où un statut réessayable, et surtout pas une escalade.
        aide = make_aide()
        an = analyze(aide, make_collect(aide, fresh="# Accès refusé\n"), today=TODAY)
        self.assertEqual(an.statut, "ERREUR_HTTP")
        self.assertTrue(any("--proxy jina" in r for r in an.raisons))

    def test_page_vraiment_videe_sans_baseline_escalade(self):
        # Sans baseline, rien ne dit que la page a jamais eu du contenu :
        # l'escalade reste le bon réflexe.
        aide = make_aide()
        col = make_collect(aide, fresh="# Accès refusé\n", baseline=None, baseline_sha="sha-b")
        an = analyze(aide, col, today=TODAY)
        self.assertEqual(an.statut, "ESCALADE_INGESTION")
        self.assertTrue(any("contenu utile" in r for r in an.raisons))


class TestSansBaseline(unittest.TestCase):
    def test_aucun_snapshot(self):
        aide = make_aide()
        col = make_collect(aide, baseline=None, baseline_sha=None)
        an = analyze(aide, col, today=TODAY)
        self.assertEqual(an.statut, "SANS_BASELINE")

    def test_aucune_url_surveillable(self):
        aide = make_aide(source={})
        an = analyze(aide, AideCollect(slug=aide.slug), today=TODAY)
        self.assertEqual(an.statut, "SANS_BASELINE")
        self.assertIn("aucune URL surveillable", an.raisons[0])


class TestDatesPerimees(unittest.TestCase):
    def test_source_inchangee_demande_un_arbitrage_humain(self):
        aide = make_aide(calendrier={"permanent": False, "date_limite": "2025-10-31"})
        col = make_collect(aide, baseline_sha="meme-sha", fresh_sha="meme-sha")
        an = analyze(aide, col, today=TODAY)
        self.assertEqual(an.statut, "DATE_PERIMEE_SOURCE_INCHANGEE")
        self.assertEqual(an.date_limite_perimee, date(2025, 10, 31))

    def test_page_modifiee_prime_sur_la_date(self):
        # Si la page a bougé, la nouvelle échéance y est peut-être : c'est un
        # cas pour l'étage C, pas pour l'arbitrage humain.
        aide = make_aide(calendrier={"permanent": False, "date_limite": "2025-10-31"})
        fresh = BASELINE.replace("31 octobre", "30 novembre")
        an = analyze(aide, make_collect(aide, fresh=fresh), today=TODAY)
        self.assertEqual(an.statut, "MAJ_LLM")
        self.assertTrue(any("date limite dépassée" in r and "modifiée" in r for r in an.raisons))

    def test_date_future_ne_declenche_rien(self):
        aide = make_aide(calendrier={"permanent": False, "date_limite": "2027-01-31"})
        col = make_collect(aide, baseline_sha="meme-sha", fresh_sha="meme-sha")
        self.assertEqual(analyze(aide, col, today=TODAY).statut, "OK")


class TestContenuUtile(unittest.TestCase):
    def test_chrome_de_page_ne_compte_pas(self):
        menu = "\n".join("  * [Nos rubriques](https://ex.fr/rubriques)" for _ in range(80))
        self.assertLess(contenu_utile(menu), MIN_CONTENU_UTILE)

    def test_prose_compte(self):
        self.assertGreater(contenu_utile(BASELINE * 3), MIN_CONTENU_UTILE)


class TestChromeEtReglementPartage(unittest.TestCase):
    """Une ligne qui change à l'identique sur deux pages est du gabarit… sauf
    si c'est du règlement : deux aides sœurs d'un même guide changent leur
    échéance d'un bloc (cvl-pact-cooperation et cvl-pact-programmation, le
    2026-10-04, classées « source inchangée » alors que la date avait bougé)."""

    def _deux_soeurs(self, avant: str, apres: str) -> dict[str, AideCollect]:
        collects = {}
        for i in (1, 2):
            url = f"https://region.fr/aide-{i}"
            murl = MonitoredUrl(
                url=url,
                role="officielle",
                baseline_sha="ancien",
                baseline_body=f"# Aide {i}\n\nTexte propre à l'aide {i}.\n\n{avant}\n",
            )
            collects[f"aide-{i}"] = AideCollect(
                slug=f"aide-{i}",
                urls=[murl],
                fetched={
                    url: FetchResult(
                        url=url,
                        status=200,
                        sha256="nouveau",
                        body_md=f"# Aide {i}\n\nTexte propre à l'aide {i}.\n\n{apres}\n",
                    )
                },
            )
        return collects

    def test_echeance_partagee_n_est_pas_du_chrome(self):
        collects = self._deux_soeurs(
            "Les dossiers doivent être déposés avant le 15 novembre 2025.",
            "Les dossiers doivent être déposés avant le 16 novembre 2026.",
        )
        self.assertEqual(lignes_de_chrome(collects), frozenset())

    def test_plafond_partage_n_est_pas_du_chrome(self):
        collects = self._deux_soeurs(
            "Subvention plafonnée à 50 000 €.", "Subvention plafonnée à 40 000 €."
        )
        self.assertEqual(lignes_de_chrome(collects), frozenset())

    def test_menu_et_date_de_mise_a_jour_restent_du_chrome(self):
        for avant, apres in (
            (
                "Mon été, ma Région : que faire cet été en Île-de-France ?",
                "Cet automne, découvrez les journées du patrimoine en région",
            ),
            ("Mis à jour le 28 septembre 2026", "Mis à jour le 1er octobre 2026"),
            ("Le 19 juin 2026", "Le 29 septembre 2026"),
            ("Corrèze 100% Fibre", "Corrèze Mobilité"),
        ):
            with self.subTest(avant=avant):
                self.assertTrue(lignes_de_chrome(self._deux_soeurs(avant, apres)))


class TestFormulaireUrl(unittest.TestCase):
    def test_formulaire_mort_ne_declenche_pas_d_escalade(self):
        # `formulaire_url` n'est qu'un contrôle de vivacité : son contenu n'est
        # ni diffé ni cité, et sa mort ne justifie pas une ré-ingestion.
        aide = make_aide(source={"url_officielle": URL, "formulaire_url": "https://ex.fr/form"})
        col = make_collect(
            aide,
            baseline_sha="meme-sha",
            fresh_sha="meme-sha",
            extra_urls=[MonitoredUrl(url="https://ex.fr/form", role="formulaire")],
        )
        col.fetched["https://ex.fr/form"] = FetchResult(url="https://ex.fr/form", status=404)
        an = analyze(aide, col, today=TODAY)
        self.assertEqual(an.statut, "OK")


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# Documents binaires : PDF diffés par leur texte, le reste par sha
# ---------------------------------------------------------------------------

# Assez long pour passer `PDF_MIN_TEXT` : en dessous, un PDF est un scan et son
# texte ne compte pas.
PDF_TEXTE = (
    "RÈGLEMENT D'INTERVENTION\n\n"
    "Article 1 — Objet\n"
    "Le présent règlement fixe les conditions d'attribution de l'aide régionale à la\n"
    "restauration du patrimoine bâti non protégé.\n\n"
    "Article 2 — Bénéficiaires\n"
    "Les communes, les établissements publics de coopération intercommunale et les\n"
    "propriétaires privés peuvent déposer une demande.\n\n"
    "Article 3 — Conditions\n"
    "Le plafond réglementaire est de 40 % du montant hors taxes des travaux.\n"
    "Les travaux ne doivent pas avoir commencé avant la notification de la décision.\n"
    "Le maître d'ouvrage s'engage à ouvrir l'édifice au public au moins dix jours par an.\n\n"
    "Article 4 — Dépôt\n"
    "Le dossier complet est transmis par voie dématérialisée avant le 30 juin.\n"
    "Il comprend un devis détaillé, des photographies de l'état actuel et une note\n"
    "de présentation du projet signée par le maître d'ouvrage.\n\n"
    "Article 5 — Versement\n"
    "La subvention est versée sur présentation des factures acquittées, après\n"
    "contrôle de conformité par le service instructeur de la Région.\n"
) * 2


def collect_avec_pdf(
    aide: Aide,
    *,
    pdf_frais: str | None = PDF_TEXTE,
    pdf_sha_frais: str = "sha-pdf-frais",
    pdf_baseline: str | None = PDF_TEXTE,
    contenu: bytes | None = b"%PDF-1.4 octets",
) -> AideCollect:
    """Une page HTML inchangée, plus un règlement PDF surveillé."""
    murl_pdf = MonitoredUrl(
        url=PDF_URL,
        role="snapshot",
        label="reglement",
        baseline_path=Path("2026-07-01-reglement.pdf"),
        baseline_sha="sha-pdf-baseline",
        baseline_body=pdf_baseline,
        is_binary=True,
    )
    col = make_collect(
        aide,
        baseline_sha="meme-sha",
        fresh_sha="meme-sha",
        extra_urls=[murl_pdf],
        baseline_docs=[
            ("2026-07-01-page.md", BASELINE, "text"),
            *([("2026-07-01-reglement.pdf", pdf_baseline, "pdf")] if pdf_baseline else []),
        ],
        baseline_urls={"2026-07-01-page.md": URL, "2026-07-01-reglement.pdf": PDF_URL},
    )
    col.fetched[PDF_URL] = FetchResult(
        url=PDF_URL,
        status=200,
        sha256=pdf_sha_frais,
        is_binary=True,
        content=contenu,
        texte_pdf=pdf_frais,
    )
    return col


class TestDocumentsBinaires(unittest.TestCase):
    """Un règlement PDF remplacé doit être VU. Avant : le sha n'était comparé que
    pour les pages en markdown, et 97 URL binaires surveillées ne pouvaient
    jamais sortir « modifiées »."""

    def test_pdf_au_sha_identique_ne_change_rien(self):
        aide = make_aide(conditions=[condition("du-pdf", "Le plafond réglementaire est de 40 %")])
        col = collect_avec_pdf(aide, pdf_sha_frais="sha-pdf-baseline")
        an = analyze(aide, col, today=TODAY)
        self.assertEqual(an.statut, "OK")
        self.assertTrue(an.urls[1].sha_identique)
        # Et la citation qu'il porte est bien RECONTRÔLÉE : le PDF frais est lisible.
        self.assertEqual(an.couverture_quotes, (1, 1))

    def test_pdf_modifie_et_lisible_part_a_l_etage_c(self):
        aide = make_aide(conditions=[condition("du-pdf", "Le plafond réglementaire est de 40 %")])
        frais = PDF_TEXTE.replace("40 %", "50 %")
        an = analyze(aide, collect_avec_pdf(aide, pdf_frais=frais), today=TODAY)
        self.assertEqual(an.statut, "MAJ_LLM")
        self.assertTrue(an.urls[1].a_change)
        self.assertIsNotNone(an.urls[1].diff)
        self.assertEqual([q.cond_id for q in an.regressions], ["du-pdf"])
        self.assertTrue(any(PDF_URL in r for r in an.raisons))

    def test_pdf_modifie_mais_illisible_escalade(self):
        # Scan, .docx, pdftotext absent : le sha dit qu'il a bougé, personne ne
        # peut dire quoi. C'est un humain qui doit ouvrir le document.
        aide = make_aide()
        col = collect_avec_pdf(aide, pdf_frais=None, contenu=b"PK\x03\x04 docx")
        an = analyze(aide, col, today=TODAY)
        self.assertEqual(an.statut, "ESCALADE_INGESTION")
        self.assertTrue(an.urls[1].binaire_modifie)
        self.assertTrue(any("binaire modifié" in r for r in an.raisons))

    def test_pdf_court_au_texte_identique_ne_change_rien(self):
        # PDF généré à la volée (meuse.fr/…/pdf) : trop court pour servir de
        # baseline, ses octets changent à chaque requête, son texte non. Il
        # escaladait l'aide à chaque passage.
        from dataclasses import replace

        from veille_collect import empreinte_texte

        court = "Formulaire de demande. Date limite : 31 mars 2027."
        aide = make_aide()
        col = collect_avec_pdf(aide, pdf_frais=court, pdf_baseline=None)
        col.urls = [
            replace(u, baseline_empreinte_texte=empreinte_texte(court)) if u.url == PDF_URL else u
            for u in col.urls
        ]
        an = analyze(aide, col, today=TODAY)
        self.assertEqual(an.statut, "OK", an.raisons)
        self.assertTrue(an.urls[1].sha_identique)

    def test_pdf_frais_lisible_mais_baseline_scannee_escalade(self):
        # L'archive ne s'extrait pas : rien à quoi comparer le texte frais.
        aide = make_aide()
        col = collect_avec_pdf(aide, pdf_baseline=None)
        an = analyze(aide, col, today=TODAY)
        self.assertEqual(an.statut, "ESCALADE_INGESTION")

    def test_pdf_scanne_ne_fait_pas_disparaitre_ses_citations(self):
        # Le garde-fou d'origine : un PDF frais dont on ne tire rien n'est pas
        # « rafraîchi », donc l'absence de la citation ne prouve rien.
        aide = make_aide(conditions=[condition("du-pdf", "Le plafond réglementaire est de 40 %")])
        col = collect_avec_pdf(aide, pdf_frais="trop court", pdf_sha_frais="sha-pdf-baseline")
        an = analyze(aide, col, today=TODAY)
        self.assertEqual(an.regressions, [])
        self.assertEqual([q.cond_id for q in an.non_recontrolables], ["du-pdf"])

    def test_fresh_docs_expose_le_texte_du_pdf_en_type_pdf(self):
        aide = make_aide()
        docs = collect_avec_pdf(aide).fresh_docs()
        self.assertEqual([(nom, kind) for nom, _, kind in docs], [(URL, "text"), (PDF_URL, "pdf")])
        self.assertIn("plafond réglementaire", docs[1][1])
