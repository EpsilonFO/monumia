"""Visites guidées déjà vues (`users.guides_vus`) : fusion, refus d'une visite
inconnue, et parité avec le catalogue du front."""

import re
import unittest
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from routers.auth import GUIDES, GuideVuRequest, marquer_guide_vu

FRONT_GUIDES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "guides.ts"
QUAND = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)


class GuidesVusTest(unittest.TestCase):
    def test_fusionne_sans_perdre_les_autres(self) -> None:
        vus = marquer_guide_vu({"monuments": "2026-10-01T00:00:00+00:00"}, "projet", QUAND)
        self.assertEqual(
            vus,
            {"monuments": "2026-10-01T00:00:00+00:00", "projet": QUAND.isoformat()},
        )

    def test_idempotent_la_date_se_rafraichit(self) -> None:
        vus = marquer_guide_vu({"projet": "2026-10-01T00:00:00+00:00"}, "projet", QUAND)
        self.assertEqual(vus, {"projet": QUAND.isoformat()})

    def test_valeur_illisible_ou_cle_retiree(self) -> None:
        self.assertEqual(marquer_guide_vu(None, "aide", QUAND), {"aide": QUAND.isoformat()})
        self.assertEqual(marquer_guide_vu("x", "aide", QUAND), {"aide": QUAND.isoformat()})
        self.assertEqual(
            marquer_guide_vu({"ancienne_visite": "x"}, "aide", QUAND), {"aide": QUAND.isoformat()}
        )

    def test_refuse_une_visite_inconnue(self) -> None:
        for mauvais in ("inconnue", "", None, 3):
            with self.assertRaises(ValidationError, msg=repr(mauvais)):
                GuideVuRequest.model_validate({"id": mauvais})
        self.assertEqual(GuideVuRequest.model_validate({"id": "dossier"}).id, "dossier")

    def test_le_front_declare_les_memes_visites(self) -> None:
        source = FRONT_GUIDES.read_text(encoding="utf-8")
        bloc = re.search(r"export const GUIDE_IDS = \[(.*?)\] as const;", source, re.S)
        assert bloc is not None, "GUIDE_IDS introuvable dans guides.ts"
        self.assertEqual(tuple(re.findall(r"'([a-z_]+)'", bloc.group(1))), GUIDES)


if __name__ == "__main__":
    unittest.main()
