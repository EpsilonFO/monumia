"""Requalification d'aides déjà ingérées (scripts/prospection/requalification.py).

Le test du destinataire décide de ce qui ENTRE au catalogue ; il reste à
l'appliquer à ce qui y est déjà — 643 aides écrites sans aucun point de contrôle
entre le tri LLM et l'écriture des YAML, plus 436 antérieures.

Ce que ces tests fixent :

  - le module ne touche RIEN. Il lit le catalogue et écrit une fiche ;
  - la décision est DÉRIVÉE du couple destinataire × objet, comme à la lecture :
    la même règle, au même endroit, quel que soit le moment où on l'applique ;
  - la fiche se relit à la machine (bloc « Slugs à écarter »), parce que c'est
    elle que l'utilisateur corrige avant les renommages.

Aucun réseau, aucun modèle : `fake_provider`.

Run from backend/:  uv run pytest tests/test_requalification.py
"""

import sys
import tempfile
import unittest
import unittest.mock
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import providall  # noqa: E402
from pipeline.etat import Tache, charger, ecrire  # noqa: E402
from prospection.requalification import (  # noqa: E402
    PARALLELE_DEFAUT,
    SANS_MOTIF,
    Rapport,
    RapportApplication,
    Requalification,
    Verdict,
    appliquer,
    consigne,
    parser_ecarts,
    rendre_fiche,
    requalifier,
    reviews_de,
    slugs_du_fichier,
)
from providall.testing import fake_provider, json_reply  # noqa: E402

from aides_schema import Aide  # noqa: E402

JOUR = date(2026, 9, 21)


def client() -> providall.Client:
    return providall.Client("ds-flash", api_key="faux", retry=providall.RetryPolicy(retries=0))


def aide(slug: str, **kw) -> Aide:
    return Aide.model_validate(
        {
            "slug": slug,
            "nom": f"Aide {slug}",
            "organisme": "Région d'exemple",
            "categorie": "region",
            "type": "subvention",
            "description": "Une aide pour tester la requalification.",
            **kw,
        }
    )


RETENUE = {
    "destinataire": "proprietaire_gestionnaire",
    "objet": "bien_ou_lieu",
    "motif": "S'adresse aux propriétaires d'édifices protégés.",
}
ECARTEE = {
    "destinataire": "activite_tiers",
    "objet": "hors_lieu",
    "categorie_ecart": "metier_agricole",
    "motif": "Réservée aux exploitants agricoles affiliés MSA.",
}


class TestVerdict(unittest.TestCase):
    """La décision est la MÊME règle qu'à la lecture, au même endroit."""

    def test_le_bon_couple_retient(self):
        self.assertTrue(Requalification.model_validate(RETENUE).retenir)

    def test_un_metier_ecarte_meme_sur_du_bati(self):
        """Une aide au ravalement réservée aux bailleurs sociaux n'est pas la sienne."""
        r = Requalification.model_validate({**ECARTEE, "objet": "bien_ou_lieu"})
        self.assertFalse(r.retenir)
        self.assertFalse(r.indeterminee)

    def test_le_defaut_est_indetermine(self):
        r = Requalification()
        self.assertFalse(r.retenir)
        self.assertTrue(r.indeterminee)

    def test_le_sort_a_quatre_valeurs(self):
        a = aide("x")
        self.assertEqual(Verdict("x", a, Requalification.model_validate(RETENUE)).sort, "retenir")
        self.assertEqual(Verdict("x", a, Requalification.model_validate(ECARTEE)).sort, "ecarter")
        self.assertEqual(Verdict("x", a, Requalification()).sort, "indetermine")
        self.assertEqual(Verdict("x", a, erreur="panne").sort, "erreur")


class TestRequalifier(unittest.TestCase):
    def test_lot_nominal(self):
        aides = {"a": aide("a"), "b": aide("b")}
        with fake_provider(json_reply(RETENUE), json_reply(ECARTEE)):
            rapport = requalifier(aides, client(), parallele=1)
        self.assertEqual(len(rapport.par_sort("retenir")), 1)
        self.assertEqual(len(rapport.par_sort("ecarter")), 1)

    def test_une_panne_devient_un_verdict_en_erreur(self):
        """Une aide non jugée n'est ni retenue ni écartée : elle se voit dans la fiche."""
        with fake_provider(providall.NetworkError("boum", provider="x")):
            rapport = requalifier({"a": aide("a")}, client(), parallele=1)
        self.assertEqual(rapport.par_sort("erreur")[0].slug, "a")
        self.assertIn("boum", rapport.par_sort("erreur")[0].erreur or "")

    def test_la_consigne_porte_le_test_et_sa_restriction(self):
        texte = consigne()
        self.assertIn("proprietaire_gestionnaire", texte)
        self.assertIn("DÉJÀ au catalogue", texte)
        # Le point qui empêche de confondre les deux chantiers : une aide mal
        # ingérée mais bien destinée se corrige, l'inverse se retire.
        self.assertIn("QUALITÉ de l'extraction", texte)

    def test_la_progression_est_appelee(self):
        vus: list[int] = []
        with fake_provider(json_reply(RETENUE), json_reply(RETENUE)):
            requalifier(
                {"a": aide("a"), "b": aide("b")},
                client(),
                progression=lambda i, n, v: vus.append(i),
                parallele=1,
            )
        self.assertEqual(vus, [1, 2])


class TestParallelisme(unittest.TestCase):
    """950 aides séquentiellement font plus d'une heure — et un run qu'on n'ose
    plus relancer est un point de contrôle qu'on saute."""

    def test_le_lot_est_juge_en_parallele(self):
        import threading
        import time

        vivants, pic = set(), 0
        verrou = threading.Lock()

        def juger(slug, a, cl, **kw):
            nonlocal pic
            with verrou:
                vivants.add(slug)
                pic = max(pic, len(vivants))
            time.sleep(0.02)
            with verrou:
                vivants.discard(slug)
            return Verdict(slug, a, Requalification.model_validate(RETENUE))

        aides = {f"a{i}": aide(f"a{i}") for i in range(8)}
        with unittest.mock.patch("prospection.requalification.requalifier_une", side_effect=juger):
            rapport = requalifier(aides, client(), parallele=4)
        self.assertGreater(pic, 1, "les appels se sont faits l'un après l'autre")
        self.assertLessEqual(pic, 4)
        self.assertEqual(len(rapport.verdicts), 8)

    def test_le_rapport_reste_trie_par_slug(self):
        """La fiche se compare d'un passage à l'autre : un ordre qui dépend de
        l'ordonnancement des threads rendrait tout diff illisible."""
        import random
        import time

        def juger(slug, a, cl, **kw):
            time.sleep(random.uniform(0, 0.03))
            return Verdict(slug, a, Requalification.model_validate(RETENUE))

        aides = {f"a{i:02d}": aide(f"a{i:02d}") for i in range(12)}
        with unittest.mock.patch("prospection.requalification.requalifier_une", side_effect=juger):
            rapport = requalifier(aides, client(), parallele=6)
        self.assertEqual([v.slug for v in rapport.verdicts], sorted(aides))

    def test_la_progression_compte_juste_en_parallele(self):
        def juger(slug, a, cl, **kw):
            return Verdict(slug, a, Requalification.model_validate(RETENUE))

        vus: list[int] = []
        aides = {f"a{i}": aide(f"a{i}") for i in range(10)}
        with unittest.mock.patch("prospection.requalification.requalifier_une", side_effect=juger):
            requalifier(aides, client(), parallele=4, progression=lambda i, n, v: vus.append(i))
        self.assertEqual(vus, list(range(1, 11)))

    def test_le_defaut_est_parallele(self):
        self.assertGreater(PARALLELE_DEFAUT, 1)


class TestFiche(unittest.TestCase):
    def setUp(self):
        self.rapport = Rapport(
            verdicts=[
                Verdict(
                    "garde",
                    aide("garde", familles=["restauration_bati"]),
                    Requalification.model_validate(RETENUE),
                ),
                Verdict(
                    "ferme",
                    aide("ferme", familles=["eau_nature_domaine"]),
                    Requalification.model_validate(ECARTEE),
                ),
                Verdict("doute", aide("doute"), Requalification()),
                Verdict("panne", aide("panne"), erreur="modèle indisponible"),
            ],
            cout="4 appel(s), $0.02",
        )
        self.markdown = rendre_fiche(self.rapport, nom="lot-4-regions", jour=JOUR)

    def test_structure(self):
        for titre in (
            "# Requalification — lot-4-regions — 2026-09-21",
            "## À écarter",
            "## À trancher à la main",
            "## Retenues",
            "## Non jugées",
            "## Slugs à écarter",
        ):
            self.assertIn(titre, self.markdown)

    def test_la_fiche_dit_que_rien_na_ete_renomme(self):
        """C'est le seul point de contrôle humain du chantier."""
        self.assertIn("Rien n'a été renommé", self.markdown)
        self.assertIn("retyper_faits.py --retirer-orphelins", self.markdown)
        self.assertIn("data/sources/", self.markdown)

    def test_les_ecartees_sont_groupees_par_categorie(self):
        self.assertIn("### `metier_agricole` — 1 aide(s)", self.markdown)

    def test_le_bloc_de_slugs_se_relit(self):
        self.assertEqual(parser_ecarts(self.markdown), [("ferme", "metier_agricole")])

    def test_un_bloc_edite_a_la_main_se_relit_aussi(self):
        """Retirer une ligne = garder l'aide. C'est le geste de validation."""
        edite = self.markdown.replace("ferme  metier_agricole\n", "")
        self.assertEqual(parser_ecarts(edite), [])

    def test_une_fiche_sans_ecart_ne_casse_pas_le_parseur(self):
        vide = rendre_fiche(Rapport(), nom="x", jour=JOUR)
        self.assertEqual(parser_ecarts(vide), [])
        self.assertIn("_aucune_", vide)

    def test_le_cout_est_dans_les_notes(self):
        self.assertIn("4 appel(s), $0.02", self.markdown)

    def test_une_ecartee_sans_motif_le_dit(self):
        """Mesuré sur le passage du 2026-09-22 : 19 écartées sans motif, donc
        écartées sans qu'on puisse relire la décision. La ligne doit le signaler
        plutôt que de finir sur un tiret."""
        muet = Requalification.model_validate({**ECARTEE, "motif": "   "})
        fiche = rendre_fiche(
            Rapport(verdicts=[Verdict("muette", aide("muette"), muet)]),
            nom="x",
            jour=JOUR,
        )
        self.assertIn(SANS_MOTIF, fiche)
        self.assertNotIn("objet `hors_lieu` — \n", fiche)


class TestEntrees(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name)

    def test_slugs_du_fichier_ignore_commentaires_et_vides(self):
        chemin = self.racine / "slugs.txt"
        chemin.write_text("# un commentaire\n\naide-a\naide-b  note\n", encoding="utf-8")
        self.assertEqual(slugs_du_fichier(chemin), ["aide-a", "aide-b"])

    def test_reviews_de_prend_la_plus_recente(self):
        reviews = self.racine / "reviews"
        reviews.mkdir()
        (reviews / "2026-09-01-ex-aide.md").write_text("ancienne", encoding="utf-8")
        (reviews / "2026-09-18-ex-aide.md").write_text("récente", encoding="utf-8")
        self.assertEqual(reviews_de(["ex-aide"], reviews), {"ex-aide": "récente"})

    def test_un_dossier_absent_ne_casse_rien(self):
        self.assertEqual(reviews_de(["x"], self.racine / "absent"), {})

    def test_un_slug_court_ne_prend_pas_la_fiche_dun_slug_plus_long(self):
        """Le bug qui a fait écarter la subvention MH de la Région Normandie.

        `region-normandie` est un préfixe de
        `normandie-region-normandie-droits-culturels` : la recherche par
        sous-chaîne lui a donné la fiche de cette aide-là, et le modèle a jugé
        une aide aux droits culturels en croyant juger une aide MH à 20-30 %.
        """
        reviews = self.racine / "reviews"
        reviews.mkdir()
        (reviews / "2026-09-10-ingest-normandie-region-normandie-droits-culturels.md").write_text(
            "droits culturels", encoding="utf-8"
        )
        univers = ["region-normandie", "normandie-region-normandie-droits-culturels"]
        self.assertEqual(reviews_de(["region-normandie"], reviews, univers=univers), {})
        self.assertEqual(
            reviews_de(["normandie-region-normandie-droits-culturels"], reviews, univers=univers),
            {"normandie-region-normandie-droits-culturels": "droits culturels"},
        )

    def test_un_lot_dune_seule_aide_a_besoin_de_lunivers(self):
        """Sans `univers`, le lot d'une aide se compare à lui-même et reprend le bug."""
        reviews = self.racine / "reviews"
        reviews.mkdir()
        (reviews / "2026-09-10-region-normandie-droits-culturels.md").write_text(
            "pas la sienne", encoding="utf-8"
        )
        univers = ["region-normandie", "region-normandie-droits-culturels"]
        self.assertEqual(reviews_de(["region-normandie"], reviews, univers=univers), {})

    def test_un_suffixe_de_nom_de_fichier_reste_reconnu(self):
        """`<slug>-deepseek-review.md` est un nom réel du dépôt."""
        reviews = self.racine / "reviews"
        reviews.mkdir()
        (reviews / "eure-mon-village-mon-amour-deepseek-review.md").write_text(
            "fiche", encoding="utf-8"
        )
        self.assertEqual(
            reviews_de(["eure-mon-village-mon-amour"], reviews),
            {"eure-mon-village-mon-amour": "fiche"},
        )


class TestAppliquer(unittest.TestCase):
    """Le geste qui manquait : produire la fiche ne servait à rien sans lui.

    Le module écrivait la fiche, `parser_ecarts` la relisait, et RIEN ne
    renommait — la boucle du §7.6 s'arrêtait sur une liste de 480 slugs à
    traiter à la main.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name)
        self.aides = self.racine / "aides"
        self.aides.mkdir()
        for slug in ("garde", "ferme", "aussi"):
            (self.aides / f"{slug}.yaml").write_text(f"slug: {slug}\n", encoding="utf-8")
        self.etat = self.racine / "file-attente.yaml"

    def appliquer(self, ecarts, **kw):
        return appliquer(ecarts, aides_dir=self.aides, etat_path=self.etat, **kw)

    def test_le_defaut_ne_touche_a_rien(self):
        """`ecrire=False` vérifie et rend la main : c'est le dry-run."""
        rapport = self.appliquer([("ferme", "metier_agricole")])
        self.assertTrue(rapport.ok)
        self.assertEqual(rapport.renommes, [])
        self.assertTrue((self.aides / "ferme.yaml").exists())

    def test_une_ecartee_devient_un_echec_et_rien_nest_supprime(self):
        rapport = self.appliquer([("ferme", "metier_agricole")], ecrire=True)
        self.assertEqual(rapport.renommes, ["ferme"])
        self.assertFalse((self.aides / "ferme.yaml").exists())
        self.assertTrue((self.aides / "ferme.yaml.echec").exists())
        self.assertTrue((self.aides / "garde.yaml").exists())

    def test_la_tache_passe_ignore_avec_son_motif(self):
        ecrire(self.etat, {"ferme": Tache(titre="Ferme", url="https://x", territoire="t")})
        self.appliquer([("ferme", "metier_agricole")], ecrire=True)
        tache = charger(self.etat)["ferme"]
        self.assertEqual(tache.statut, "ignore")
        self.assertIn("metier_agricole", tache.motif_ignore)

    def test_une_aide_sans_tache_se_renomme_quand_meme(self):
        """Les 436 aides antérieures à la prospection n'ont pas de tâche."""
        rapport = self.appliquer([("garde", "aide_personne")], ecrire=True)
        self.assertTrue(rapport.ok)
        self.assertTrue((self.aides / "garde.yaml.echec").exists())

    def test_un_slug_absent_arrete_TOUT_le_lot(self):
        """La moitié appliquée est le pire état : on ne sait plus ce qui reste."""
        rapport = self.appliquer(
            [("ferme", "metier_agricole"), ("fantome", "aide_personne")], ecrire=True
        )
        self.assertFalse(rapport.ok)
        self.assertEqual(rapport.renommes, [])
        self.assertTrue((self.aides / "ferme.yaml").exists())

    def test_un_slug_repete_est_une_erreur(self):
        rapport = self.appliquer([("ferme", "a"), ("ferme", "b")], ecrire=True)
        self.assertFalse(rapport.ok)
        self.assertTrue((self.aides / "ferme.yaml").exists())

    def test_la_fiche_produite_se_rapplique_telle_quelle(self):
        """Le contrat de bout en bout : `rendre_fiche` → `parser_ecarts` → `appliquer`."""
        markdown = rendre_fiche(
            Rapport(
                verdicts=[
                    Verdict("ferme", aide("ferme"), Requalification.model_validate(ECARTEE)),
                    Verdict("garde", aide("garde"), Requalification.model_validate(RETENUE)),
                ]
            ),
            nom="x",
            jour=JOUR,
        )
        rapport = self.appliquer(parser_ecarts(markdown), ecrire=True)
        self.assertEqual(rapport.renommes, ["ferme"])
        self.assertTrue((self.aides / "garde.yaml").exists())


if __name__ == "__main__":
    unittest.main()


class TestCommande(unittest.TestCase):
    """Le câblage CLI, qui n'avait aucun test — et c'est là que le bug était.

    `cmd_requalifier` demandait un client au rôle « requalification », qui
    n'existe pas : la liste des rôles est FERMÉE (`pipeline.llm.ROLES`), parce
    que chacun a sa variable d'environnement. Le module était testé, la commande
    ne l'était pas, et l'erreur n'est apparue qu'à l'exécution réelle.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name)

    def args(self, **kw):
        import argparse

        base = {
            "appliquer": None,
            "lot": None,
            "territoire": [],
            "catalogue": True,
            "sortie": self.racine / "fiche.md",
            "model_requalification": None,
            "parallele": 2,
            "etat": self.racine / "file-attente.yaml",
            "territoires": None,
        }
        return argparse.Namespace(**{**base, **kw})

    def test_le_role_du_client_existe(self):
        """La garde qui manquait : un rôle inconnu lève à l'exécution, pas au test."""
        import prospecter
        from pipeline.llm import ROLES

        roles = []
        with (
            unittest.mock.patch.object(
                prospecter, "client_pour", side_effect=lambda r, m=None: roles.append(r) or client()
            ),
            unittest.mock.patch.object(
                prospecter.requalification,
                "requalifier",
                return_value=Rapport(verdicts=[]),
            ),
            unittest.mock.patch.object(prospecter, "load_all_aides", return_value={"a": aide("a")}),
            unittest.mock.patch("sys.stdout"),
        ):
            code = prospecter.cmd_requalifier(self.args())
        self.assertEqual(code, 0)
        self.assertEqual(len(roles), 1, roles)
        self.assertIn(roles[0], ROLES)

    def test_la_commande_ecrit_la_fiche(self):
        import prospecter

        rapport = Rapport(
            verdicts=[Verdict("a", aide("a"), Requalification.model_validate(ECARTEE))]
        )
        with (
            unittest.mock.patch.object(prospecter, "client_pour", return_value=client()),
            unittest.mock.patch.object(
                prospecter.requalification, "requalifier", return_value=rapport
            ),
            unittest.mock.patch.object(prospecter, "load_all_aides", return_value={"a": aide("a")}),
            unittest.mock.patch("sys.stdout"),
        ):
            prospecter.cmd_requalifier(self.args())
        texte = (self.racine / "fiche.md").read_text(encoding="utf-8")
        self.assertIn("## Slugs à écarter", texte)
        self.assertIn("a  metier_agricole", texte)

    def test_le_parallelisme_est_transmis(self):
        import prospecter

        vus = {}
        with (
            unittest.mock.patch.object(prospecter, "client_pour", return_value=client()),
            unittest.mock.patch.object(
                prospecter.requalification,
                "requalifier",
                side_effect=lambda *a, **kw: vus.update(kw) or Rapport(),
            ),
            unittest.mock.patch.object(prospecter, "load_all_aides", return_value={"a": aide("a")}),
            unittest.mock.patch("sys.stdout"),
        ):
            prospecter.cmd_requalifier(self.args(parallele=5))
        self.assertEqual(vus["parallele"], 5)

    def test_un_catalogue_vide_ne_paie_rien(self):
        import prospecter

        appels = []
        with (
            unittest.mock.patch.object(
                prospecter, "client_pour", side_effect=lambda *a, **k: appels.append(1)
            ),
            unittest.mock.patch.object(prospecter, "load_all_aides", return_value={}),
            unittest.mock.patch("sys.stdout"),
        ):
            self.assertEqual(prospecter.cmd_requalifier(self.args()), 0)
        self.assertEqual(appels, [], "un client a été ouvert pour zéro aide")

    def test_appliquer_ne_paie_rien_et_passe_la_fiche_relue(self):
        """La branche d'application ne juge rien : elle relit une fiche validée.

        Le renommage lui-même est couvert par `TestAppliquer` ; ce qu'on vérifie
        ici est le câblage, seul endroit où le bug précédent avait pu passer.
        """
        import prospecter

        fiche = self.racine / "fiche.md"
        fiche.write_text("## Slugs à écarter\n\nferme  metier_agricole\n", encoding="utf-8")

        appels, recus = [], []
        with (
            unittest.mock.patch.object(
                prospecter, "client_pour", side_effect=lambda *a, **k: appels.append(1)
            ),
            unittest.mock.patch.object(
                prospecter.requalification,
                "appliquer",
                side_effect=lambda e, **k: recus.append((e, k)) or RapportApplication(),
            ),
            unittest.mock.patch.object(prospecter, "load_all_aides", side_effect=AssertionError),
            unittest.mock.patch("sys.stdout"),
        ):
            code = prospecter.cmd_requalifier(self.args(catalogue=False, appliquer=fiche))
        self.assertEqual(code, 0)
        self.assertEqual(appels, [], "un client a été ouvert pour un simple renommage")
        self.assertEqual(recus[0][0], [("ferme", "metier_agricole")])
        self.assertIs(recus[0][1]["ecrire"], True)

    def test_appliquer_une_fiche_sans_slug_ne_fait_rien(self):
        import prospecter

        fiche = self.racine / "fiche.md"
        fiche.write_text("## Slugs à écarter\n\n_aucun_\n", encoding="utf-8")
        with unittest.mock.patch("sys.stdout"):
            self.assertEqual(
                prospecter.cmd_requalifier(self.args(catalogue=False, appliquer=fiche)), 0
            )
