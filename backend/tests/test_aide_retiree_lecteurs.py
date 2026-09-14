"""Une aide retirée du catalogue est introuvable PARTOUT.

Les deux seules portes vers une aide nommée sont `GET /aides/{id}` (la fiche
complète) et `POST /dossiers` (l'ouverture d'un dossier). Le retrait ferme les
deux, y compris pour qui suivait déjà l'aide : contrairement au paywall des
guichets à venir, il n'y a pas d'exemption `_deja_engage` — l'aide s'est révélée
fausse, la laisser ouvrable pour les uns et pas pour les autres n'aurait aucun
sens.
"""

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from aides_schema import Aide
from routers.aides import get_aide
from routers.dossiers import CreateDossierRequest, create_dossier
from services import catalogue_admin as ca
from services.offres import VEILLE

SLUG = "aide-retiree"
UUID_AIDE = "11111111-1111-4111-8111-111111111111"


def _aides() -> dict[str, Aide]:
    return {
        SLUG: Aide.model_validate(
            {
                "slug": SLUG,
                "nom": "Aide supprimée du catalogue",
                "organisme": "Région",
                "categorie": "region",
                "type": "subvention",
                "description": "d",
            }
        )
    }


class _Resp:
    def __init__(self, data) -> None:
        self.data = data


class _Query:
    def __init__(self, rows: list) -> None:
        self._rows = rows
        self._single = False

    def select(self, *_a, **_k) -> "_Query":
        return self

    def eq(self, colonne, valeur) -> "_Query":
        self._rows = [r for r in self._rows if r.get(colonne) == valeur]
        return self

    def limit(self, n) -> "_Query":
        self._rows = self._rows[:n]
        return self

    def single(self) -> "_Query":
        self._single = True
        return self

    def maybe_single(self) -> "_Query":
        self._single = True
        return self

    def execute(self) -> _Resp:
        if self._single:
            return _Resp(self._rows[0] if self._rows else None)
        return _Resp(list(self._rows))


class _FakeSupabase:
    def __init__(self, **tables) -> None:
        self._tables = tables

    def table(self, name: str) -> _Query:
        return _Query(list(self._tables.get(name, [])))


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        ca.invalider()

    def tearDown(self) -> None:
        ca.invalider()


class FicheAideTests(_Base):
    def test_aide_retiree_est_404(self) -> None:
        db = _FakeSupabase(aides_retirees=[{"slug": SLUG}])
        with (
            patch("routers.aides.load_all_aides", return_value=_aides()),
            patch("routers.aides.billing.offre_du_compte", return_value=VEILLE),
            self.assertRaises(HTTPException) as leve,
        ):
            get_aide(SLUG, "u1", db)
        self.assertEqual(leve.exception.status_code, 404)
        self.assertEqual(leve.exception.detail, "Aide retirée du catalogue")

    def test_404_meme_avec_un_dossier_en_cours(self) -> None:
        """Pas d'exemption `_deja_engage` : le retrait vaut pour tout le monde."""
        db = _FakeSupabase(
            aides_retirees=[{"slug": SLUG}],
            dossiers=[{"id": "d1", "user_id": "u1", "aide_id": SLUG}],
        )
        with (
            patch("routers.aides.load_all_aides", return_value=_aides()),
            patch("routers.aides.billing.offre_du_compte", return_value=VEILLE),
            self.assertRaises(HTTPException) as leve,
        ):
            get_aide(SLUG, "u1", db)
        self.assertEqual(leve.exception.status_code, 404)

    def test_retrait_resolu_depuis_un_uuid(self) -> None:
        db = _FakeSupabase(
            aides_retirees=[{"slug": SLUG}],
            aides_v3=[{"id": UUID_AIDE, "slug": SLUG, "nom": "Aide"}],
        )
        with (
            patch("routers.aides.load_all_aides", return_value=_aides()),
            patch("routers.aides.billing.offre_du_compte", return_value=VEILLE),
            self.assertRaises(HTTPException) as leve,
        ):
            get_aide(UUID_AIDE, "u1", db)
        self.assertEqual(leve.exception.status_code, 404)

    def test_ligne_heritee_sans_slug_reste_servie(self) -> None:
        """Fail-open : une `aides_v3` sans slug ne peut être rapprochée d'aucun
        retrait, et un faux 404 vaudrait pire qu'un retrait manqué."""
        db = _FakeSupabase(
            aides_retirees=[{"slug": SLUG}],
            aides_v3=[{"id": UUID_AIDE, "slug": None, "nom": "Aide héritée"}],
        )
        with (
            patch("routers.aides.load_all_aides", return_value=_aides()),
            patch("routers.aides.billing.offre_du_compte", return_value=VEILLE),
        ):
            aide = get_aide(UUID_AIDE, "u1", db)
        self.assertEqual(aide["nom"], "Aide héritée")

    def test_aide_non_retiree_reste_servie(self) -> None:
        db = _FakeSupabase(aides_retirees=[])
        with (
            patch("routers.aides.load_all_aides", return_value=_aides()),
            patch("routers.aides.billing.offre_du_compte", return_value=VEILLE),
        ):
            aide = get_aide(SLUG, "u1", db)
        self.assertEqual(aide["nom"], "Aide supprimée du catalogue")


class OuvertureDossierTests(_Base):
    MONUMENT = {"id": "m1", "user_id": "u1", "nom": "Château", "code_insee": None}
    PROJET = {"id": "p1", "monument_id": "m1", "user_id": "u1"}

    def _creer(self, db):
        with patch(
            "routers.dossiers.require_projet_access", return_value=(self.PROJET, "co_owner")
        ):
            return create_dossier(
                CreateDossierRequest(projet_id="p1", aide_id=SLUG, travaux_prevus=[]),
                "u1",
                db,
            )

    def test_aide_retiree_est_404(self) -> None:
        db = _FakeSupabase(
            monuments=[self.MONUMENT],
            aides_v3=[{"id": UUID_AIDE, "slug": SLUG, "nom": "Aide"}],
            aides_retirees=[{"slug": SLUG}],
        )
        with self.assertRaises(HTTPException) as leve:
            self._creer(db)
        self.assertEqual(leve.exception.status_code, 404)
        self.assertEqual(leve.exception.detail, "Aide retirée du catalogue")


if __name__ == "__main__":
    unittest.main()
