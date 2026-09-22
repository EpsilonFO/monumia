"""Tests des post-contrôles et de l'orchestration (worker.py, orchestrateur.py).

C'est ici que se joue la promesse du pipeline : **rien d'invérifiable n'entre au
catalogue**. Les tests ci-dessous fixent le verdict sur les six contrôles, et
surtout ce qui arrive à un YAML refusé — renommé `.yaml.echec`, donc hors du
glob `*.yaml`, donc invisible au lint, au moteur et au loader.

Côté orchestrateur, on vérifie l'ordonnancement seul : `ingerer_aide` est
remplacé par une fonction de test, aucun modèle n'est appelé.

Run from backend/:  uv run pytest tests/test_ingestion_worker.py
"""

import dataclasses
import sys
import tempfile
import threading
import unittest
import unittest.mock
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import veille_collect  # noqa: E402
from ingestion import orchestrateur  # noqa: E402
from ingestion.atelier import atelier_redirige, restaurer_sources  # noqa: E402
from ingestion.boucle import Resultat  # noqa: E402
from ingestion.outils import EtatOutils  # noqa: E402
from ingestion.verification import RapportVerification  # noqa: E402
from ingestion.worker import ConfigIngestion, ResultatIngestion, controler  # noqa: E402
from pipeline.etat import Ingestion, Tache, charger, ecrire  # noqa: E402
from pipeline.llm import Compteur  # noqa: E402
from providall import Usage  # noqa: E402

JOUR = date(2026, 9, 6)

FACTS = """\
monument_ouvert_au_public:
  type: boolean
  scope: monument
  question: Le monument est-il ouvert au public ?
"""

SNAPSHOT = """\
---
url: https://example.org/aide
fetched_at: 2026-09-06T09:00:00+00:00
sha256: 0000000000000000000000000000000000000000000000000000000000000000
---

# Aide d'exemple

Le monument doit être ouvert au public au moins quarante jours par an.
"""

REVIEW = "## Conditions\n\n" + ("Une ligne de fiche de review humaine. " * 40)


def aide_yaml(conditions: str) -> str:
    return f"""\
slug: ex-aide
nom: Aide d'exemple
nom_court: Exemple
organisme: Région d'exemple
categorie: region
type: subvention
# Le ressort du financeur : `check_portee_geographique` refuse une aide
# régionale qui ne le déclare pas, elle se proposerait dans toute la France.
hard_filters:
  regions:
  - grand-est
description: Une aide pour tester les post-contrôles.
familles: [restauration_bati]
source:
  url_officielle: https://example.org/aide
  verified_at: '2026-09-06'
  snapshot: data/sources/ex-aide/2026-09-06.md
conditions:
{conditions}
"""


CONDITION_OK = """\
  - id: ouvert-au-public
    text: Le monument est ouvert au public.
    kind: user_fact
    effect: gate
    fact: monument_ouvert_au_public
    predicate: {eq: true}
    quote: ouvert au public au moins quarante jours par an
"""

CONDITION_GATE = """\
  - id: appreciation
    text: Le dossier est apprécié au regard des priorités régionales.
    kind: manual_check
    effect: gate
    notes: Rien dans la source ne permet de trancher.
    quote: ouvert au public au moins quarante jours par an
"""


class BaseWorker(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        # `atelier_redirige` détourne une globale de PROCESSUS : sans ce
        # nettoyage, les tests suivants liraient un tmpdir effacé.
        self.addCleanup(restaurer_sources)
        self.racine = Path(self._tmp.name)
        facts = self.racine / "facts.yaml"
        facts.write_text(FACTS, encoding="utf-8")
        baseline = self.racine / "manual_check_baseline.json"
        baseline.write_text("{}\n", encoding="utf-8")
        self.atelier = dataclasses.replace(
            atelier_redirige("ex-aide", self.racine, jour=JOUR),
            facts_path=facts,
            pending_path=self.racine / "pending.yaml",
        )
        (self.racine / "pending.yaml").write_text("", encoding="utf-8")
        veille_collect.pdf_to_text.cache_clear()

    def preparer(self, *, conditions=CONDITION_OK, snapshot=True, review=True):
        if snapshot:
            (self.atelier.dossier_sources / "2026-09-06.md").write_text(SNAPSHOT, encoding="utf-8")
        self.atelier.yaml_path.write_text(aide_yaml(conditions), encoding="utf-8")
        if review:
            self.atelier.review_path.write_text(REVIEW, encoding="utf-8")

    def etat(self, **kw) -> EtatOutils:
        base = {"review_ecrite": True, "aide_ecrite": True, "verification": RapportVerification()}
        return EtatOutils(**{**base, **kw})

    def resultat(self, arret="termine") -> Resultat:
        return Resultat(arret=arret, tours=12, usage=Usage(), cout_usd=0.2, cout_inconnu=False)


class TestControles(BaseWorker):
    def test_tout_vert(self):
        self.preparer()
        self.assertEqual(controler(self.atelier, self.resultat(), self.etat()), [])

    def test_trop_de_faits_neufs(self):
        """563 faits pour 643 aides : le plafond doit aussi se voir en SORTIE."""
        self.preparer()
        etat = self.etat()
        etat.faits_proposes = ["a", "b", "c", "d"]
        echecs = controler(self.atelier, self.resultat(), etat)
        self.assertEqual(len(echecs), 1, echecs)
        self.assertIn("4 faits neufs", echecs[0])

    def test_trois_faits_neufs_passent(self):
        self.preparer()
        etat = self.etat()
        etat.faits_proposes = ["a", "b", "c"]
        self.assertEqual(controler(self.atelier, self.resultat(), etat), [])

    def test_familles_vide_refuse(self):
        """114 aides du lot : `familles` vide est FAIL-OPEN, elles sortent partout."""
        self.preparer()
        self.atelier.yaml_path.write_text(
            self.atelier.yaml_path.read_text(encoding="utf-8").replace(
                "familles: [restauration_bati]\n", ""
            ),
            encoding="utf-8",
        )
        echecs = controler(self.atelier, self.resultat(), self.etat())
        self.assertEqual(len(echecs), 1, echecs)
        self.assertIn("familles", echecs[0])
        self.assertIn("fail-open", echecs[0])

    def test_hors_perimetre_est_un_arret_normal(self):
        """Ni YAML ni échec : l'agent a lu la source et l'aide s'adresse à un tiers."""
        from ingestion.outils import HorsPerimetre

        etat = self.etat()
        etat.hors_perimetre = HorsPerimetre(
            categorie="metier_agricole",
            motif="Réservé aux exploitants agricoles affiliés MSA.",
            citation="Bénéficiaires : exploitants agricoles",
        )
        self.assertEqual(controler(self.atelier, self.resultat(), etat), [])

    def test_hors_perimetre_avec_un_yaml_se_contredit(self):
        from ingestion.outils import HorsPerimetre

        self.preparer()
        etat = self.etat()
        etat.hors_perimetre = HorsPerimetre(
            categorie="metier_agricole", motif="x" * 50, citation="y"
        )
        echecs = controler(self.atelier, self.resultat(), etat)
        self.assertEqual(len(echecs), 1, echecs)
        self.assertIn("se contredisent", echecs[0])

    def test_sans_yaml(self):
        echecs = controler(self.atelier, self.resultat(), self.etat())
        self.assertEqual(echecs, ["aucun fichier YAML écrit"])

    def test_yaml_illisible(self):
        self.atelier.yaml_path.write_text("slug: [pas du yaml", encoding="utf-8")
        echecs = controler(self.atelier, self.resultat(), self.etat())
        self.assertIn("non chargeable", echecs[0])

    def test_lint_rouge(self):
        self.preparer(conditions=CONDITION_GATE)
        echecs = controler(self.atelier, self.resultat(), self.etat())
        self.assertTrue(any("lint rouge" in e for e in echecs), echecs)

    def test_sans_review(self):
        self.preparer(review=False)
        self.assertIn(
            "aucune fiche de review", controler(self.atelier, self.resultat(), self.etat())
        )

    def test_review_moignon(self):
        self.preparer()
        self.atelier.review_path.write_text("## Trop court", encoding="utf-8")
        self.assertIn(
            "fiche de review trop courte", controler(self.atelier, self.resultat(), self.etat())
        )

    def test_sans_snapshot(self):
        self.preparer(snapshot=False)
        echecs = controler(self.atelier, self.resultat(), self.etat())
        self.assertIn("aucune source archivée", echecs)

    def test_arret_anormal(self):
        self.preparer()
        echecs = controler(self.atelier, self.resultat(arret="budget"), self.etat())
        self.assertTrue(any("budget" in e for e in echecs), echecs)

    def test_verification_jamais_lancee(self):
        self.preparer()
        echecs = controler(self.atelier, self.resultat(), self.etat(verification=None))
        self.assertIn("vérification adversariale jamais lancée", echecs)


class TestMiseEnEchec(BaseWorker):
    def test_le_yaml_refuse_sort_du_glob(self):
        from ingestion.worker import _mettre_en_echec

        self.preparer(conditions=CONDITION_GATE)
        _mettre_en_echec(self.atelier, "lint rouge")
        self.assertFalse(self.atelier.yaml_path.exists())
        self.assertTrue(self.atelier.yaml_echec_path.exists())
        self.assertEqual(list(self.atelier.aides_dir.glob("*.yaml")), [])
        contenu = self.atelier.yaml_echec_path.read_text(encoding="utf-8")
        self.assertIn("ÉCHEC D'INGESTION", contenu)
        self.assertIn("lint rouge", contenu)
        self.assertIn("slug: ex-aide", contenu)

    def test_les_preuves_sont_conservees(self):
        from ingestion.worker import _mettre_en_echec

        self.preparer(conditions=CONDITION_GATE)
        _mettre_en_echec(self.atelier, "lint rouge")
        self.assertTrue(self.atelier.snapshots())
        self.assertTrue(self.atelier.review_path.exists())


# ---------------------------------------------------------------------------
# Orchestrateur
# ---------------------------------------------------------------------------


def tache(**kw) -> Tache:
    base = {
        "titre": "Aide",
        "url": "https://example.org/aide",
        "territoire": "hauts-de-france",
        "statut": "valide",
        "ajoute_le": JOUR,
    }
    return Tache.model_validate({**base, **kw})


def verdict(slug: str, *, ok=True, cout=0.2, **kw) -> ResultatIngestion:
    base = {
        "slug": slug,
        "ok": ok,
        "arret": "termine" if ok else "budget",
        "tours": 10,
        "cout_usd": cout,
        "cout_inconnu": False,
        "modele": "faux",
        "modele_verif": "faux",
        "debut": "2026-09-06T09:00:00+00:00",
        "fin": "2026-09-06T09:05:00+00:00",
        "motif_echec": None if ok else "budget dépassé",
    }
    return ResultatIngestion(**{**base, **kw})


def panne(slug: str, *, tours=1) -> ResultatIngestion:
    """La forme EXACTE des 351 échecs du 2026-09-18 : rien d'écrit, rien dépensé.

    `tours=1` par défaut, parce que 255 des 351 avaient fait un tour : le
    critère « 0 tour et 0 $ » en aurait raté 267.
    """
    return verdict(
        slug,
        ok=False,
        cout=0.0,
        arret="erreur_modele",
        tours=tours,
        motif_echec="NetworkError: Connection error",
        echec_transitoire=True,
    )


class TestOrchestrateur(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        # `executer` construit ses ateliers via `config.atelier(...)`, qui
        # redirige la globale de sources : à restaurer ici aussi.
        self.addCleanup(restaurer_sources)
        self.racine = Path(self._tmp.name)
        self.etat_path = self.racine / "file-attente.yaml"
        self.config = ConfigIngestion(sortie=self.racine / "sortie", jour=JOUR, journaliser=False)
        self.contexte_patch = unittest.mock.patch.object(
            orchestrateur.ContextePartage,
            "construire",
            classmethod(lambda cls, atelier: cls(systeme="SYS", facts={}, pending={})),
        )
        self.contexte_patch.start()
        self.addCleanup(self.contexte_patch.stop)

    def ecrire_etat(self, **taches):
        ecrire(self.etat_path, {slug: t for slug, t in taches.items()})

    def test_deux_aides_en_parallele(self):
        self.ecrire_etat(a=tache(), b=tache())
        vus: list[str] = []
        verrou = threading.Lock()

        def faux(slug, t, config, *, contexte, compteur=None):
            with verrou:
                vus.append(slug)
            return verdict(slug)

        resultats = orchestrateur.executer(
            ["a", "b"], self.config, parallele=2, etat_path=self.etat_path, ingerer=faux
        )
        self.assertEqual(sorted(vus), ["a", "b"])
        self.assertEqual(len(resultats), 2)
        etat = charger(self.etat_path)
        self.assertEqual(etat["a"].statut, "ingere")
        assert etat["a"].ingestion is not None
        self.assertEqual(etat["a"].ingestion.tentatives, 1)

    def test_un_echec_passe_en_statut_echec(self):
        self.ecrire_etat(a=tache())
        resultats = orchestrateur.executer(
            ["a"],
            self.config,
            etat_path=self.etat_path,
            ingerer=lambda slug, t, c, *, contexte, compteur=None: verdict(slug, ok=False),
        )
        self.assertFalse(resultats[0].ok)
        tache_a = charger(self.etat_path)["a"]
        self.assertEqual(tache_a.statut, "echec")
        assert tache_a.ingestion is not None
        self.assertEqual(tache_a.ingestion.motif_echec, "budget dépassé")

    def test_les_tentatives_saccumulent(self):
        self.ecrire_etat(a=tache(ingestion=Ingestion(tentatives=2)))
        orchestrateur.executer(
            ["a"],
            self.config,
            etat_path=self.etat_path,
            ingerer=lambda slug, t, c, *, contexte, compteur=None: verdict(slug),
        )
        tache_a = charger(self.etat_path)["a"]
        assert tache_a.ingestion is not None
        self.assertEqual(tache_a.ingestion.tentatives, 3)

    def test_une_aide_deja_en_cours_est_ignoree(self):
        self.ecrire_etat(a=tache(statut="en_cours"), b=tache())
        vus = []
        orchestrateur.executer(
            ["a", "b"],
            self.config,
            parallele=1,
            etat_path=self.etat_path,
            ingerer=lambda slug, t, c, *, contexte, compteur=None: (
                vus.append(slug) or verdict(slug)
            ),
        )
        self.assertEqual(vus, ["b"])

    def test_le_budget_total_arrete_les_soumissions(self):
        self.ecrire_etat(a=tache(), b=tache(), c=tache())
        compteur = Compteur()
        vus = []

        def faux(slug, t, config, *, contexte, compteur=None):
            vus.append(slug)
            if compteur is not None:
                local = Compteur()
                local._cout = 2.0  # une aide qui coûte 2 $
                compteur.fusionner(local, f"aide:{slug}")
            return verdict(slug, cout=2.0)

        orchestrateur.executer(
            ["a", "b", "c"],
            self.config,
            parallele=1,
            budget_total=3.0,
            etat_path=self.etat_path,
            compteur=compteur,
            ingerer=faux,
        )
        # 1re aide lancée (0 + 1,5 ≤ 3), puis le cumul passe à 2 $ et
        # 2 + 1,5 > 3 : les deux suivantes ne partent pas.
        self.assertEqual(vus, ["a"])
        self.assertEqual(charger(self.etat_path)["b"].statut, "valide")

    def test_slug_absent_de_la_file(self):
        self.ecrire_etat(a=tache())
        with self.assertRaises(KeyError):
            orchestrateur.executer(["zorglub"], self.config, etat_path=self.etat_path)

    def test_reprendre_relibere_les_en_cours(self):
        self.ecrire_etat(a=tache(statut="en_cours"), b=tache(statut="ingere"))
        self.assertEqual(orchestrateur.reprendre(self.etat_path), ["a"])
        etat = charger(self.etat_path)
        self.assertEqual(etat["a"].statut, "valide")
        self.assertEqual(etat["b"].statut, "ingere")

    def test_relancer_echecs_remet_en_valide_et_laisse_le_reste(self):
        self.ecrire_etat(
            a=tache(statut="echec"), b=tache(statut="ingere"), c=tache(statut="en_cours")
        )
        self.assertEqual(
            orchestrateur.relancer_echecs(self.etat_path, territoires=["nulle-part"]), []
        )
        self.assertEqual(orchestrateur.relancer_echecs(self.etat_path), ["a"])
        etat = charger(self.etat_path)
        self.assertEqual(etat["a"].statut, "valide")
        self.assertEqual(etat["b"].statut, "ingere")
        self.assertEqual(etat["c"].statut, "en_cours")

    def test_une_consignation_ratee_est_retentee_en_fin_de_run(self):
        # 2026-09-13 : un `git commit` lancé dans un autre terminal a fait passer
        # la file d'attente par sa version HEAD le temps des hooks de pre-commit.
        # `mettre_a_jour` a levé KeyError, la boucle principale est morte et huit
        # aides pourtant terminées sont restées `en_cours`. Un verdict qu'on ne
        # peut pas écrire tout de suite se garde et se réécrit à la fin.
        self.ecrire_etat(a=tache(), b=tache())
        vrai = orchestrateur.mettre_a_jour
        rates: list[str] = []

        def capricieux(chemin, slug, **champs):
            if not rates:
                rates.append(slug)
                raise KeyError(f"slug absent de la file d'attente : {slug}")
            return vrai(chemin, slug, **champs)

        with unittest.mock.patch.object(orchestrateur, "mettre_a_jour", capricieux):
            resultats = orchestrateur.executer(
                ["a", "b"],
                self.config,
                parallele=1,
                etat_path=self.etat_path,
                ingerer=lambda slug, t, c, *, contexte, compteur=None: verdict(slug),
            )
        self.assertEqual(len(resultats), 2)
        self.assertEqual(rates, ["a"])
        etat = charger(self.etat_path)
        self.assertEqual((etat["a"].statut, etat["b"].statut), ("ingere", "ingere"))

    def test_une_consignation_toujours_ratee_laisse_le_statut_en_cours(self):
        self.ecrire_etat(a=tache())
        with unittest.mock.patch.object(
            orchestrateur, "mettre_a_jour", side_effect=KeyError("slug absent")
        ):
            resultats = orchestrateur.executer(
                ["a"],
                self.config,
                etat_path=self.etat_path,
                ingerer=lambda slug, t, c, *, contexte, compteur=None: verdict(slug),
            )
        # Le run rend quand même son verdict ; la file, elle, garde le jeton :
        # `--reprendre` ré-ingérerait, c'est à la main qu'on corrige.
        self.assertTrue(resultats[0].ok)
        self.assertEqual(charger(self.etat_path)["a"].statut, "en_cours")


class TestEchecsTransitoires(TestOrchestrateur):
    """C3 — une panne du fournisseur rend l'aide à la file, elle ne la perd pas."""

    def _executer(self, slug, resultat):
        return orchestrateur.executer(
            [slug],
            self.config,
            etat_path=self.etat_path,
            ingerer=lambda s, t, c, *, contexte, compteur=None: resultat,
            disjoncteur=orchestrateur.Disjoncteur(seuil=99),
        )

    def test_un_echec_transitoire_revient_en_valide(self):
        """351 tâches sont passées `echec` définitif pour une coupure réseau."""
        self.ecrire_etat(a=tache())
        self._executer("a", panne("a"))
        tache_a = charger(self.etat_path)["a"]
        self.assertEqual(tache_a.statut, "valide")
        assert tache_a.ingestion is not None
        self.assertEqual(tache_a.ingestion.tentatives, 1)
        self.assertIn("NetworkError", tache_a.ingestion.motif_echec or "")

    def test_trois_echecs_transitoires_finissent_en_echec(self):
        """Une aide qui échoue trois fois « transitoirement » cache autre chose."""
        self.ecrire_etat(a=tache(ingestion=Ingestion(tentatives=2)))
        self._executer("a", panne("a"))
        self.assertEqual(charger(self.etat_path)["a"].statut, "echec")

    def test_un_vrai_refus_reste_un_echec(self):
        """Un lint rouge ne se rejoue pas : il demande une décision humaine."""
        self.ecrire_etat(a=tache())
        self._executer("a", verdict("a", ok=False))
        self.assertEqual(charger(self.etat_path)["a"].statut, "echec")

    def test_a_relire_est_consigne_dans_la_file(self):
        """132 aides livrées avec un bloquant non résolu, sans que rien le dise."""
        self.ecrire_etat(a=tache())
        self._executer("a", verdict("a", a_relire=True))
        tache_a = charger(self.etat_path)["a"]
        self.assertEqual(tache_a.statut, "ingere")
        self.assertTrue(tache_a.a_relire)

    def test_a_relire_deja_pose_survit_a_une_reprise(self):
        self.ecrire_etat(a=tache(a_relire=True))
        self._executer("a", verdict("a"))
        self.assertTrue(charger(self.etat_path)["a"].a_relire)

    def test_un_hors_perimetre_passe_ignore_et_ne_revient_pas(self):
        """`echec` la ferait revenir au balayage suivant ; `ignore` la classe."""
        self.ecrire_etat(a=tache())
        self._executer(
            "a",
            verdict(
                "a",
                ok=False,
                arret="termine",
                motif_echec=None,
                hors_perimetre=("metier_agricole", "Réservé aux exploitants agricoles."),
            ),
        )
        relu = charger(self.etat_path)["a"]
        self.assertEqual(relu.statut, "ignore")
        self.assertEqual(relu.categorie_ecart, "metier_agricole")
        self.assertIn("exploitants agricoles", relu.motif_ignore or "")


class TestDisjoncteur(TestOrchestrateur):
    """C4 — le run s'arrête quand c'est le FOURNISSEUR qui est à terre."""

    def test_le_disjoncteur_pause_puis_arrete_a_la_seconde_salve(self):
        self.ecrire_etat(**{f"a{i}": tache() for i in range(12)})
        pauses: list[float] = []
        disjoncteur = orchestrateur.Disjoncteur(seuil=2, pause_s=42.0, dormir=pauses.append)
        resultats = orchestrateur.executer(
            [f"a{i}" for i in range(12)],
            self.config,
            parallele=1,
            etat_path=self.etat_path,
            ingerer=lambda s, t, c, *, contexte, compteur=None: panne(s),
            disjoncteur=disjoncteur,
        )
        # Première salve : pause et reprise. Seconde : arrêt.
        self.assertEqual(pauses, [42.0])
        self.assertEqual(disjoncteur.salves, 2)
        self.assertIn("solde OpenRouter", disjoncteur.motif)
        self.assertLess(len(resultats), 12)
        # Tout ce qui n'a pas été traité est rendu à `valide` : rien n'est perdu.
        statuts = {s: t.statut for s, t in charger(self.etat_path).items()}
        self.assertNotIn("en_cours", statuts.values())
        self.assertNotIn("echec", statuts.values())

    def test_une_auth_error_arrete_le_run(self):
        """55 `AuthError` dans les journaux : rejouer une clé invalide 900 fois."""
        self.ecrire_etat(**{f"a{i}": tache() for i in range(6)})
        fatal = verdict(
            "x",
            ok=False,
            cout=0.0,
            arret="erreur_modele",
            tours=0,
            motif_echec="AuthError: clé invalide",
            echec_fatal=True,
        )
        disjoncteur = orchestrateur.Disjoncteur()
        resultats = orchestrateur.executer(
            [f"a{i}" for i in range(6)],
            self.config,
            parallele=1,
            etat_path=self.etat_path,
            ingerer=lambda s, t, c, *, contexte, compteur=None: dataclasses.replace(fatal, slug=s),
            disjoncteur=disjoncteur,
        )
        self.assertEqual(len(resultats), 1)
        self.assertIn("clé d'API", disjoncteur.motif)

    def test_un_echec_ordinaire_ne_declenche_rien(self):
        """Quatre lints rouges d'affilée ne sont pas une panne de fournisseur."""
        self.ecrire_etat(**{f"a{i}": tache() for i in range(5)})
        disjoncteur = orchestrateur.Disjoncteur(seuil=2)
        resultats = orchestrateur.executer(
            [f"a{i}" for i in range(5)],
            self.config,
            parallele=1,
            etat_path=self.etat_path,
            ingerer=lambda s, t, c, *, contexte, compteur=None: verdict(s, ok=False),
            disjoncteur=disjoncteur,
        )
        self.assertEqual(len(resultats), 5)
        self.assertEqual(disjoncteur.motif, "")

    def test_un_succes_remet_le_compteur_a_zero(self):
        d = orchestrateur.Disjoncteur(seuil=3)
        self.assertFalse(d.panne(panne("a")))
        self.assertFalse(d.panne(panne("b")))
        self.assertFalse(d.panne(verdict("c")))
        self.assertFalse(d.panne(panne("d")))
        self.assertFalse(d.panne(panne("e")))
        self.assertEqual(d.salves, 0)


class TestRelancerEchecs(TestOrchestrateur):
    """C5 — relancer les pannes sans re-brûler les vrais refus."""

    def test_relancer_echecs_seulement_sans_yaml(self):
        self.ecrire_etat(
            panne=tache(
                statut="echec",
                ingestion=Ingestion(motif_echec="aucun fichier YAML écrit", tentatives=1),
            ),
            lint_rouge=tache(
                statut="echec",
                ingestion=Ingestion(motif_echec="lint rouge : quote introuvable", tentatives=1),
            ),
        )
        relances = orchestrateur.relancer_echecs(self.etat_path, seulement_sans_yaml=True)
        self.assertEqual(relances, ["panne"])
        statuts = {s: t.statut for s, t in charger(self.etat_path).items()}
        self.assertEqual(statuts, {"panne": "valide", "lint_rouge": "echec"})

    def test_sans_le_filtre_tout_repart(self):
        self.ecrire_etat(
            a=tache(statut="echec", ingestion=Ingestion(motif_echec="lint rouge")),
            b=tache(statut="echec", ingestion=Ingestion(motif_echec="aucun fichier YAML écrit")),
        )
        self.assertEqual(sorted(orchestrateur.relancer_echecs(self.etat_path)), ["a", "b"])

    def test_une_tache_sans_bloc_ingestion_nest_pas_relancee_par_le_filtre(self):
        """Pas de motif = on ne sait pas : on ne la rejoue pas à l'aveugle."""
        self.ecrire_etat(a=tache(statut="echec"))
        self.assertEqual(
            orchestrateur.relancer_echecs(self.etat_path, seulement_sans_yaml=True), []
        )


class TestBilan(unittest.TestCase):
    def test_rappelle_les_commandes_manuelles(self):
        texte = orchestrateur.bilan([verdict("a"), verdict("b", ok=False)])
        self.assertIn("1/2 aide(s) ingérée(s)", texte)
        self.assertIn("lint_aides_data.py", texte)
        self.assertIn("git add", texte)
        self.assertIn("load_aides_yaml.py", texte)

    def test_liste_les_faits_proposes(self):
        r = verdict("a")
        r.faits_proposes = ["jardin_remarquable"]
        self.assertIn("jardin_remarquable", orchestrateur.bilan([r]))

    def test_sans_resultat(self):
        self.assertEqual(orchestrateur.bilan([]), "Aucune aide ingérée.")

    def test_un_banc_dessai_ninvite_ni_a_committer_ni_a_charger(self):
        """`--sortie` n'écrit rien dans data/ : le dire faux est un piège.

        Le bilan invitait à `git add -p backend/data` et à
        `load_aides_yaml.py` pour des fichiers qui sont sous `~/bench/`, et
        annonçait le fait proposé « dans data/facts_pending.yaml » alors qu'il
        était dans la copie du banc — sur un fichier qui a déjà été écrasé une
        fois, désigner le mauvais est le pire des messages.
        """
        r = verdict("a")
        r.faits_proposes = ["jardin_remarquable"]
        texte = orchestrateur.bilan([r], sortie=Path("/tmp/bench/x"))
        self.assertIn("/tmp/bench/x/facts_pending.yaml", texte)
        self.assertIn("n'a pas bougé", texte)
        self.assertIn("comparer_aides.py", texte)
        self.assertNotIn("git add", texte)
        self.assertNotIn("load_aides_yaml.py", texte)

    def test_un_run_reel_garde_les_commandes_manuelles(self):
        r = verdict("a")
        r.faits_proposes = ["jardin_remarquable"]
        texte = orchestrateur.bilan([r])
        self.assertIn("data/facts_pending.yaml", texte)
        self.assertIn("git add", texte)
        self.assertIn("load_aides_yaml.py", texte)


if __name__ == "__main__":
    unittest.main()
