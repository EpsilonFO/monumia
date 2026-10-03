"""Tests unitaires pour suivi_service — logique pure, sans DB."""

import unittest

from services.suivi_service import (
    SuiviValidationError,
    apply_statut_change,
    compute_etat_projet,
    statut_suivi_au_depot,
    validate_payload,
)


class ValidatePayloadTests(unittest.TestCase):
    def test_rejects_unknown_statut(self) -> None:
        with self.assertRaises(SuiviValidationError):
            validate_payload({"statut": "nope"})

    def test_rejects_negative_montant(self) -> None:
        with self.assertRaises(SuiviValidationError):
            validate_payload({"statut": "accorde", "montant_obtenu": -1})

    def test_rejects_unknown_motif(self) -> None:
        with self.assertRaises(SuiviValidationError):
            validate_payload({"statut": "refuse", "motif_refus_code": "xxx"})

    def test_rejects_bool_montant(self) -> None:
        with self.assertRaises(SuiviValidationError):
            validate_payload({"statut": "accorde", "montant_obtenu": True})

    def test_accepts_valid_minimal(self) -> None:
        validate_payload({"statut": "a_faire"})  # ne lève pas


class ApplyStatutChangeTests(unittest.TestCase):
    def test_nulls_montant_when_not_accorde(self) -> None:
        fields = apply_statut_change(None, {"statut": "depose", "montant_obtenu": 5000}, now="t0")
        self.assertIsNone(fields["montant_obtenu"])

    def test_keeps_montant_when_accorde(self) -> None:
        fields = apply_statut_change(None, {"statut": "accorde", "montant_obtenu": 5000}, now="t0")
        self.assertEqual(fields["montant_obtenu"], 5000)

    def test_nulls_motif_when_not_refuse(self) -> None:
        fields = apply_statut_change(
            None, {"statut": "accorde", "motif_refus_code": "autre"}, now="t0"
        )
        self.assertIsNone(fields["motif_refus_code"])

    def test_nulls_motif_detail_when_not_refuse(self) -> None:
        fields = apply_statut_change(
            None, {"statut": "accorde", "motif_refus_detail": "x"}, now="t0"
        )
        self.assertIsNone(fields["motif_refus_detail"])

    def test_appends_historique_on_change(self) -> None:
        existing = {"statut": "a_faire", "historique": [{"statut": "a_faire", "at": "t0"}]}
        fields = apply_statut_change(existing, {"statut": "depose"}, now="t1")
        self.assertEqual(len(fields["historique"]), 2)
        self.assertEqual(fields["historique"][-1], {"statut": "depose", "at": "t1"})

    def test_no_duplicate_historique_when_same_statut(self) -> None:
        existing = {"statut": "depose", "historique": [{"statut": "depose", "at": "t0"}]}
        fields = apply_statut_change(existing, {"statut": "depose"}, now="t1")
        self.assertEqual(len(fields["historique"]), 1)

    def test_new_suivi_seeds_historique(self) -> None:
        fields = apply_statut_change(None, {"statut": "a_faire"}, now="t0")
        self.assertEqual(fields["historique"], [{"statut": "a_faire", "at": "t0"}])


class ComputeEtatProjetTests(unittest.TestCase):
    def test_boucle_when_cloture_at_set(self) -> None:
        self.assertEqual(compute_etat_projet("t0", []), "boucle")

    def test_ouvert_when_no_suivis(self) -> None:
        self.assertEqual(compute_etat_projet(None, []), "ouvert")

    def test_ouvert_when_some_active(self) -> None:
        suivis = [{"statut": "accorde"}, {"statut": "a_faire"}]
        self.assertEqual(compute_etat_projet(None, suivis), "ouvert")

    def test_pret_when_all_terminal(self) -> None:
        suivis = [{"statut": "accorde"}, {"statut": "refuse"}]
        self.assertEqual(compute_etat_projet(None, suivis), "pret_a_cloturer")


class StatutAuDepotTests(unittest.TestCase):
    def test_depot_fait_avancer_un_suivi_en_amont(self) -> None:
        for actuel in (None, "a_faire", "en_preparation"):
            self.assertEqual(statut_suivi_au_depot(actuel, depose=True), "depose")

    def test_depot_ne_touche_ni_depose_ni_decision(self) -> None:
        for actuel in ("depose", "accorde", "refuse"):
            self.assertIsNone(statut_suivi_au_depot(actuel, depose=True))

    def test_reouverture_ne_defait_que_le_depot(self) -> None:
        self.assertEqual(statut_suivi_au_depot("depose", depose=False), "en_preparation")
        for actuel in (None, "a_faire", "en_preparation", "accorde", "refuse"):
            self.assertIsNone(statut_suivi_au_depot(actuel, depose=False))


if __name__ == "__main__":
    unittest.main()
