"""Tests de l'orchestration du job de rappels (scripts/rappels_aides.py).

La sélection des aides est testée à part (test_rappels_service). Ici on vérifie
ce que le job décide AUTOUR d'elle : le respect des préférences, le paywall, et
le dédoublonnage — les trois endroits où une erreur envoie un email de trop, ou
un email qui divulgue ce que le produit caviarde.
"""

import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import rappels_aides  # noqa: E402

TODAY = date(2026, 9, 1)
APP_URL = "https://app.monumia.fr"

MONUMENT = {"id": "m1", "nom": "Église Saint-Pierre", "code_insee": "35238", "my_role": "owner"}
PROJET = {"id": "p1", "monument_id": "m1", "titre": "Réfection de la toiture", "questionnaire": {}}

# Une aide à J-30 (palier par défaut) et une ouverture du jour, sur la même aide.
DIAGNOSTIC = {
    "aidesEligibles": [
        {
            "statut": "eligible",
            "disponibilite": "maintenant",
            "aide": {
                "id": "drac-toiture",
                "nom": "DRAC Toiture",
                "dateLimite": "2026-10-01",
                "dateOuverture": "2026-09-01",
                "permanent": False,
                "montantMax": 50_000,
            },
        }
    ],
    "aidesPotentiellementEligibles": [],
    "aidesAtteignables": [],
    "aidesNonEligibles": [],
}


class CollecterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.acces = {"allAccess": False, "unlockedMonumentIds": ["m1"]}
        self.deja: set[tuple] = set()

        patches = [
            patch.object(
                rappels_aides, "projets_de", return_value=([PROJET], {"m1": MONUMENT}, {})
            ),
            patch.object(rappels_aides, "rappels_deja_envoyes", side_effect=lambda *_: self.deja),
            patch.object(rappels_aides, "deterministic_diagnostic_for", return_value=DIAGNOSTIC),
            patch.object(
                rappels_aides.billing, "access_snapshot", side_effect=lambda *_: self.acces
            ),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _collecter(self, **prefs):
        user = {
            "id": "u1",
            "email": "marie@example.fr",
            "prenom": "Marie",
            "notification_preferences": prefs,
        }
        return rappels_aides.collecter(None, user, TODAY, APP_URL)

    def test_les_deux_familles_par_defaut(self) -> None:
        # Préférences vides = tout activé : un compte créé avant la migration
        # ne doit pas se retrouver privé de rappels.
        blocs_e, blocs_o, cles = self._collecter()
        self.assertEqual(len(blocs_e), 1)
        self.assertEqual(len(blocs_o), 1)
        self.assertEqual(len(cles), 2)
        self.assertEqual(blocs_e[0].projet_url, f"{APP_URL}/app/projets/p1")
        self.assertEqual(blocs_e[0].monument_nom, "Église Saint-Pierre")

    def test_echeances_coupees(self) -> None:
        blocs_e, blocs_o, cles = self._collecter(rappelsEcheances=False)
        self.assertEqual(blocs_e, [])
        self.assertEqual(len(blocs_o), 1)
        self.assertEqual([c[2] for c in cles], ["ouverture"])

    def test_ouvertures_coupees(self) -> None:
        blocs_e, blocs_o, _ = self._collecter(rappelsOuvertures=False)
        self.assertEqual(len(blocs_e), 1)
        self.assertEqual(blocs_o, [])

    def test_tout_coupe_ne_lance_aucun_diagnostic(self) -> None:
        with patch.object(rappels_aides, "projets_de") as projets:
            resultat = self._collecter(rappelsEcheances=False, rappelsOuvertures=False)
        self.assertEqual(resultat, ([], [], []))
        projets.assert_not_called()

    def test_paliers_personnalises(self) -> None:
        # L'aide est à 30 jours : avec un seul palier à 7 jours, rien ne part.
        blocs_e, _, _ = self._collecter(rappelDelaisJours=[7])
        self.assertEqual(blocs_e, [])

    def test_monument_verrouille_ne_sort_pas_du_produit(self) -> None:
        # Le nom d'une aide sur un monument non débloqué est caviardé dans
        # l'app ; un email le nommerait en clair.
        self.acces = {"allAccess": False, "unlockedMonumentIds": []}
        self.assertEqual(self._collecter(), ([], [], []))

    def test_abonnement_ouvre_tous_les_monuments(self) -> None:
        self.acces = {"allAccess": True, "unlockedMonumentIds": []}
        blocs_e, _, _ = self._collecter()
        self.assertEqual(len(blocs_e), 1)

    def test_rappel_deja_envoye_ne_repart_pas(self) -> None:
        self.deja = {
            ("p1", "drac-toiture", "echeance", 30, "2026-10-01"),
            ("p1", "drac-toiture", "ouverture", None, "2026-09-01"),
        }
        self.assertEqual(self._collecter(), ([], [], []))

    def test_les_cles_journalisees_decrivent_ce_qui_est_parti(self) -> None:
        _, _, cles = self._collecter()
        self.assertIn(("p1", "drac-toiture", "echeance", 30, "2026-10-01"), cles)
        self.assertIn(("p1", "drac-toiture", "ouverture", None, "2026-09-01"), cles)


class TraiterTests(unittest.TestCase):
    """Le dry-run n'écrit ni n'envoie, et le journal ne s'écrit qu'après l'envoi."""

    def setUp(self) -> None:
        self.user = {"id": "u1", "email": "marie@example.fr", "prenom": "Marie"}
        bloc = rappels_aides.BlocProjet(
            projet_titre="Toiture",
            monument_nom="Église",
            projet_url=f"{APP_URL}/app/projets/p1",
            echeances=tuple(
                rappels_aides.echeances_a_rappeler(DIAGNOSTIC, TODAY, (30,)),
            ),
        )
        patches = [
            patch.object(
                rappels_aides,
                "collecter",
                return_value=([bloc], [], [("p1", "drac-toiture", "echeance", 30, "2026-10-01")]),
            ),
            patch.object(rappels_aides, "send_rappel_email"),
            patch.object(rappels_aides, "journaliser"),
            patch.object(rappels_aides, "notifier_in_app"),
        ]
        self.mocks = {}
        for p in patches:
            self.mocks[p.attribute] = p.start()
            self.addCleanup(p.stop)

    def test_dry_run_nenvoie_rien(self) -> None:
        n_e, n_o = rappels_aides.traiter(None, self.user, TODAY, APP_URL, dry_run=True)
        self.assertEqual((n_e, n_o), (1, 0))
        self.mocks["send_rappel_email"].assert_not_called()
        self.mocks["journaliser"].assert_not_called()

    def test_envoi_puis_journalisation(self) -> None:
        rappels_aides.traiter(None, self.user, TODAY, APP_URL, dry_run=False)
        self.mocks["send_rappel_email"].assert_called_once()
        self.mocks["notifier_in_app"].assert_called_once()
        self.mocks["journaliser"].assert_called_once()

    def test_un_echec_denvoi_laisse_le_rappel_repartir_demain(self) -> None:
        self.mocks["send_rappel_email"].side_effect = RuntimeError("Resend HS")
        with self.assertRaises(RuntimeError):
            rappels_aides.traiter(None, self.user, TODAY, APP_URL, dry_run=False)
        self.mocks["journaliser"].assert_not_called()

    def test_compte_sans_email(self) -> None:
        n_e, n_o = rappels_aides.traiter(
            None, {"id": "u1", "email": "", "prenom": ""}, TODAY, APP_URL, dry_run=False
        )
        self.assertEqual((n_e, n_o), (0, 0))
        self.mocks["send_rappel_email"].assert_not_called()
        self.mocks["journaliser"].assert_not_called()


if __name__ == "__main__":
    unittest.main()
