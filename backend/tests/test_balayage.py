"""Le balayage multi-territoires (scripts/balayage.py).

Ce fichier n'existait pas : `balayage.py` orchestrait quatre régions et
39 départements, écrivait 643 YAML, et aucun test ne le regardait. Ce qu'on
garde ici est ce qui a lâché le 2026-09-18 :

  - `valider_en_attente` promouvait TOUT ce qui était `a_valider`, y compris
    140 candidates rangées `adjacente` et 5 dites `hors_perimetre` par le tri ;
  - rien ne regardait la file entière pour y voir des doublons d'URL, et 51
    aides déjà au catalogue sont revenues en `-2` ;
  - la prospection et l'ingestion étaient soudées, donc les 351 tâches perdues
    en panne réseau ne pouvaient repartir sans rebalayer les quatre régions.

Aucun réseau, aucun modèle, aucun sous-processus : les trois fonctions testées
opèrent sur un `file-attente.yaml` de test et sur des appelables injectés.

Run from backend/:  uv run pytest tests/test_balayage.py
"""

import argparse
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import balayage  # noqa: E402
from pipeline.etat import Tache, charger, ecrire  # noqa: E402

JOUR = date(2026, 9, 18)

RETENUE = {
    "destinataire": "proprietaire_gestionnaire",
    "objet": "bien_ou_lieu",
    "famille": "restauration_bati",
}


def tache(slug: str, **kw) -> Tache:
    base = {
        "titre": slug,
        "url": f"https://guide.example/{slug}",
        "territoire": "ex",
        "ajoute_le": JOUR,
    }
    return Tache.model_validate({**base, **kw})


class BaseBalayage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name) / "file-attente.yaml"
        patch = mock.patch.object(balayage, "FILE_ATTENTE", self.file)
        patch.start()
        self.addCleanup(patch.stop)

    def poser(self, taches: dict[str, Tache]) -> None:
        ecrire(self.file, taches)

    def statuts(self) -> dict[str, str]:
        return {s: t.statut for s, t in charger(self.file).items()}


class TestValiderEnAttente(BaseBalayage):
    def test_valider_en_attente_ne_promeut_que_les_retenues(self):
        """Le point de contrôle qui manquait entre le tri et l'écriture des YAML."""
        self.poser(
            {
                "ok": tache("ok", **RETENUE),
                "adjacente": tache(
                    "adjacente",
                    destinataire="proprietaire_gestionnaire",
                    objet="bien_ou_lieu",
                    famille="adjacente",
                ),
                "indeterminee": tache("indeterminee", famille="tourisme_hebergement"),
                "metier": tache(
                    "metier",
                    destinataire="activite_tiers",
                    objet="hors_lieu",
                    categorie_ecart="metier_agricole",
                    famille="eau_nature_domaine",
                ),
            }
        )
        promotion = balayage.valider_en_attente(["ex"])
        self.assertEqual(promotion.promus, ["ok"])
        self.assertEqual(
            self.statuts(),
            {
                "ok": "valide",
                "adjacente": "a_valider",
                "indeterminee": "a_valider",
                "metier": "a_valider",
            },
        )

    def test_ce_qui_nest_pas_promu_nest_pas_perdu(self):
        """Refuser la promotion n'est pas écarter : la file les garde, motif en main."""
        self.poser({"indeterminee": tache("indeterminee", famille="tourisme_hebergement")})
        promotion = balayage.valider_en_attente(["ex"])
        self.assertEqual(promotion.promus, [])
        self.assertIn("indeterminee", promotion.restants)
        self.assertIn("indéterminé", promotion.restants["indeterminee"])
        self.assertEqual(self.statuts(), {"indeterminee": "a_valider"})

    def test_un_autre_territoire_nest_pas_touche(self):
        self.poser(
            {
                "ici": tache("ici", **RETENUE),
                "ailleurs": tache("ailleurs", territoire="autre", **RETENUE),
            }
        )
        balayage.valider_en_attente(["ex"])
        self.assertEqual(self.statuts(), {"ici": "valide", "ailleurs": "a_valider"})

    def test_promouvoir_tout_rend_lancien_comportement(self):
        """Pour une file relue et corrigée à la main : l'utilisateur assume."""
        self.poser({"adjacente": tache("adjacente", famille="adjacente")})
        promotion = balayage.valider_en_attente(["ex"], tout=True)
        self.assertEqual(promotion.promus, ["adjacente"])
        self.assertEqual(self.statuts(), {"adjacente": "valide"})

    def test_le_compte_rendu_groupe_les_motifs(self):
        """Une liste de 140 slugs ne se relit pas ; un tableau de motifs, si."""
        self.poser(
            {
                f"indeterminee-{i}": tache(f"indeterminee-{i}", famille="tourisme_hebergement")
                for i in range(3)
            }
        )
        rendu = balayage.valider_en_attente(["ex"]).rendre()
        self.assertIn("3 laissée(s) en `a_valider`", rendu)
        self.assertIn("3  destinataire ou objet indéterminé", rendu)


class TestDoublonsDurl(BaseBalayage):
    def test_valider_en_attente_ecarte_les_doublons_durl(self):
        """51 aides déjà au catalogue sont revenues en `-2`, même URL, même jour."""
        self.poser(
            {
                "aide": tache("aide", url="https://g/x", statut="ingere", **RETENUE),
                "aide-2": tache("aide-2", url="https://g/x", **RETENUE),
            }
        )
        promotion = balayage.valider_en_attente(["ex"])
        self.assertEqual(promotion.doublons, {"aide-2": "aide"})
        self.assertEqual(promotion.promus, [])
        relu = charger(self.file)["aide-2"]
        self.assertEqual(relu.statut, "ignore")
        self.assertEqual(relu.doublon_de, "aide")
        self.assertIn("doublon", relu.motif_ignore or "")

    def test_le_dedoublonnage_regarde_toute_la_file(self):
        """Le doublon d'une aide du Grand Est peut venir d'un balayage des PdL."""
        self.poser(
            {
                "ailleurs": tache(
                    "ailleurs", url="https://g/x", territoire="autre", statut="ingere", **RETENUE
                ),
                "ici": tache("ici", url="https://g/x", **RETENUE),
            }
        )
        promotion = balayage.valider_en_attente(["ex"])
        self.assertEqual(promotion.doublons, {"ici": "ailleurs"})
        self.assertEqual(self.statuts()["ici"], "ignore")

    def test_un_doublon_deja_ingere_nest_pas_rebascule(self):
        """Deux `ingere` sur la même URL : les YAML existent, on n'y touche pas ici."""
        self.poser(
            {
                "a": tache("a", url="https://g/x", statut="ingere", **RETENUE),
                "b": tache("b", url="https://g/x", statut="ingere", **RETENUE),
            }
        )
        balayage.valider_en_attente(["ex"])
        self.assertEqual(self.statuts(), {"a": "ingere", "b": "ingere"})


class TestPhaseIngestion(BaseBalayage):
    def args(self, **kw) -> argparse.Namespace:
        base = {
            "promouvoir_tout": False,
            "parallele": 2,
            "budget_aide": 1.0,
            "budget_total": 10.0,
            "model_ingestion": "ds-v41",
            "model_verif": "ds-v41",
            "model_audit": "ds-v41",
            "relances_ingestion": 0,
            "pause_relance": 0,
        }
        return argparse.Namespace(**{**base, **kw})

    def test_rien_a_ingerer_nest_pas_une_erreur(self):
        self.poser({"indeterminee": tache("indeterminee", famille="tourisme_hebergement")})
        with redirect_stdout(io.StringIO()):
            code = balayage.phase_ingestion(["ex"], self.args(), "2026-09-18-0152")
        self.assertEqual(code, balayage.RIEN_A_INGERER)

    def test_la_promotion_precede_lingestion(self):
        self.poser({"ok": tache("ok", **RETENUE)})
        with (
            mock.patch.object(balayage, "ingerer", return_value=0) as ingerer,
            redirect_stdout(io.StringIO()),
        ):
            code = balayage.phase_ingestion(["ex"], self.args(), "2026-09-18-0152")
        self.assertEqual(code, 0)
        ingerer.assert_called_once()
        self.assertEqual(self.statuts(), {"ok": "valide"})

    def test_une_coupure_du_fournisseur_est_relancee(self):
        """Code 3 : les aides non traitées sont en `valide`, on repart après la pause."""
        self.poser({"ok": tache("ok", **RETENUE)})
        with (
            mock.patch.object(balayage, "DOSSIER_LOGS", Path(self.tmp.name) / "logs"),
            mock.patch.object(
                balayage, "ingerer", side_effect=[balayage.CODE_FOURNISSEUR, 0]
            ) as ingerer,
            mock.patch.object(balayage.time, "sleep") as dormir,
            redirect_stdout(io.StringIO()),
        ):
            code = balayage.phase_ingestion(
                ["ex"], self.args(relances_ingestion=2, pause_relance=5), "2026-09-18-0152"
            )
        self.assertEqual(code, 0)
        self.assertEqual(ingerer.call_count, 2)
        dormir.assert_called_once_with(5)

    def test_une_erreur_fatale_nest_pas_relancee(self):
        """Clé invalide : attendre un quart d'heure n'y changerait rien."""
        self.poser({"ok": tache("ok", **RETENUE)})

        def ingerer(args, journal):
            journal.parent.mkdir(parents=True, exist_ok=True)
            journal.write_text("⛔ erreur fatale sur ok (AuthError)", encoding="utf-8")
            return balayage.CODE_FOURNISSEUR

        with (
            mock.patch.object(balayage, "DOSSIER_LOGS", Path(self.tmp.name) / "logs"),
            mock.patch.object(balayage, "ingerer", side_effect=ingerer) as appel,
            mock.patch.object(balayage.time, "sleep") as dormir,
            redirect_stdout(io.StringIO()),
        ):
            code = balayage.phase_ingestion(
                ["ex"], self.args(relances_ingestion=2), "2026-09-18-0152"
            )
        self.assertEqual(code, balayage.CODE_FOURNISSEUR)
        self.assertEqual(appel.call_count, 1)
        dormir.assert_not_called()

    def test_les_echecs_rattrapes_sont_promus_hors_territoire(self):
        """Un ancien échec relu d'un autre territoire entre dans la promotion du run."""
        self.poser(
            {
                "ok": tache("ok", **RETENUE),
                "ancien": tache("ancien", territoire="ailleurs", **RETENUE),
            }
        )
        with (
            mock.patch.object(balayage, "ingerer", return_value=0),
            redirect_stdout(io.StringIO()),
        ):
            balayage.phase_ingestion(["ex"], self.args(), "2026-09-18-0152", en_plus=["ancien"])
        self.assertEqual(self.statuts(), {"ok": "valide", "ancien": "valide"})

    def test_reprendre_ingestion_saute_la_prospection(self):
        """Les 351 tâches perdues en panne réseau ne doivent pas coûter un rebalayage."""
        self.poser({"ok": tache("ok", **RETENUE)})
        appels = {"prospecter": 0}

        def jamais(*a, **kw):
            appels["prospecter"] += 1
            return 0

        argv = ["balayage.py", "ex", "--reprendre-ingestion"]
        with (
            mock.patch.object(balayage, "prospecter", jamais),
            mock.patch.object(balayage, "ingerer", return_value=0) as ingerer,
            mock.patch.object(balayage, "runs_en_cours", return_value=[]),
            mock.patch.object(balayage, "verifier_modeles", return_value=[]),
            mock.patch.object(balayage, "_ecrire_bilan", return_value=Path("bilan.md")),
            mock.patch.object(balayage, "rediger_fiches") as fiches,
            mock.patch.object(
                balayage,
                "territoires_a_balayer",
                return_value=(["ex"], []),
            ),
            mock.patch.object(balayage, "charger_etat", return_value={"faits": [], "debut": None}),
            mock.patch.object(balayage, "ecrire_etat"),
            mock.patch.object(sys, "argv", argv),
            redirect_stdout(io.StringIO()),
        ):
            code = balayage.main()
        self.assertEqual(code, 0)
        self.assertEqual(appels["prospecter"], 0)
        ingerer.assert_called_once()
        fiches.assert_called_once()


class TestBilan(BaseBalayage):
    """G — le run du 2026-09-18 s'est terminé sans qu'aucun fichier ne dise ce
    qu'il avait fait. Il a fallu trois jours d'analyse pour le reconstituer."""

    def setUp(self):
        super().setUp()
        self.sortie = Path(self.tmp.name) / "bilan.md"

    def ecrire_bilan(self, **kw):
        base = {
            "lint": lambda: "✓ lint OK",
            "tronc": lambda: "✓ le tronc commun ne regrossit pas",
            "audit": lambda: "## Orphelins (0)",
            "etat_path": self.file,
            "sortie": self.sortie,
        }
        balayage.bilan_balayage(
            "2026-09-18-0152", ["ex"], {"aides": 436, "pending": 0}, **{**base, **kw}
        )
        return self.sortie.read_text(encoding="utf-8")

    def test_bilan_ecrit_les_quatre_sections(self):
        self.poser({"ok": tache("ok", statut="ingere", **RETENUE)})
        texte = self.ecrire_bilan()
        for titre in (
            "## Ce que le run a produit",
            "## À relire en priorité",
            "## Échecs",
            "## Lint",
            "## Doublons d'URL",
            "## Questionnaire",
            "## Ontologie",
        ):
            self.assertIn(titre, texte)

    def test_le_delta_du_catalogue_est_dit(self):
        """Sans le relevé d'avant, le bilan dirait « 1 079 aides » au lieu de « +643 »."""
        self.poser({"ok": tache("ok", statut="ingere", **RETENUE)})
        self.assertIn("436 →", self.ecrire_bilan())

    def test_les_a_relire_sont_nommees(self):
        """132 aides livrées avec un bloquant non résolu, sans que rien ne le dise."""
        self.poser(
            {
                "douteuse": tache("douteuse", statut="ingere", a_relire=True, **RETENUE),
                "nette": tache("nette", statut="ingere", **RETENUE),
            }
        )
        section = self.ecrire_bilan().split("## À relire", 1)[1].split("## Échecs", 1)[0]
        self.assertIn("douteuse", section)
        self.assertNotIn("nette", section)

    def test_les_echecs_portent_leur_motif_et_la_commande_de_relance(self):
        self.poser(
            {
                "perdue": tache(
                    "perdue",
                    statut="echec",
                    ingestion={"motif_echec": "aucun fichier YAML écrit"},
                    **RETENUE,
                )
            }
        )
        texte = self.ecrire_bilan()
        self.assertIn("aucun fichier YAML écrit", texte)
        self.assertIn("--relancer-echecs --seulement-sans-yaml", texte)

    def test_un_autre_territoire_nest_pas_compte(self):
        self.poser(
            {
                "ici": tache("ici", statut="ingere", **RETENUE),
                "ailleurs": tache("ailleurs", territoire="autre", statut="echec", **RETENUE),
            }
        )
        self.assertNotIn("ailleurs", self.ecrire_bilan())

    def test_les_mesures_injectees_sont_reprises_telles_quelles(self):
        self.poser({"ok": tache("ok", statut="ingere", **RETENUE)})
        texte = self.ecrire_bilan(
            lint=lambda: "✗ 3 erreur(s)",
            tronc=lambda: "✗ **le cliquet du questionnaire est ROUGE**",
        )
        self.assertIn("✗ 3 erreur(s)", texte)
        self.assertIn("ROUGE", texte)

    def test_sans_mesure_le_bilan_le_dit(self):
        """Un bilan partiel vaut mieux qu'un run qui échoue après six heures."""
        self.poser({"ok": tache("ok", statut="ingere", **RETENUE)})
        texte = self.ecrire_bilan(lint=None, tronc=None, audit=None)
        self.assertIn("_non lancé_", texte)
        self.assertIn("_non mesuré_", texte)
        self.assertIn("_non audité_", texte)

    def test_le_bilan_rappelle_ce_qui_reste_a_la_main(self):
        self.poser({"ok": tache("ok", statut="ingere", **RETENUE)})
        texte = self.ecrire_bilan()
        self.assertIn("git add -A && git commit", texte)
        self.assertIn("load_aides_yaml.py", texte)


if __name__ == "__main__":
    unittest.main()
