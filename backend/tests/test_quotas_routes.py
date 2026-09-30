"""Les garde-fous d'offre sont-ils réellement branchés sur les routes ?

`test_billing_access.py` prouve que les fonctions de `services/quotas.py`
refusent ce qu'il faut. Ce fichier prouve autre chose, et c'est la panne la plus
probable : que les routes les APPELLENT. Un quota parfaitement écrit mais oublié
sur `POST /monuments` laisse le plafond grand ouvert, et aucun test unitaire du
module ne s'en aperçoit.

D'où le parti pris : on appelle les fonctions de route directement, avec une
base factice, et on vérifie le refus ET l'absence d'écriture. Un refus rendu
après l'insertion laisserait un bien orphelin en base.
"""

import unittest
from datetime import date, timedelta
from unittest.mock import patch

from fastapi import HTTPException

from aides_schema import Aide
from routers import monuments as monuments_router
from routers import projets as projets_router
from routers.aides import get_aide
from services.offres import GRATUIT, VEILLE


class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    """Filtre `eq` / `in_` pour de vrai, et note les écritures."""

    def __init__(self, table: str, rows: list, writes: list):
        self._table = table
        self._rows = rows
        self._writes = writes
        self._single = False
        self._limit: int | None = None
        self._op = "select"
        self._payload = None

    def select(self, *a, **k):
        return self

    def eq(self, column, value):
        self._rows = [r for r in self._rows if r.get(column) == value]
        return self

    def in_(self, column, values):
        allowed = set(values)
        self._rows = [r for r in self._rows if r.get(column) in allowed]
        return self

    def is_(self, column, _value):
        self._rows = [r for r in self._rows if r.get(column) is None]
        return self

    def order(self, column, desc: bool = False):
        self._rows = sorted(self._rows, key=lambda r: str(r.get(column) or ""), reverse=desc)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def single(self):
        self._single = True
        return self

    def maybe_single(self):
        self._single = True
        return self

    def insert(self, payload, *a, **k):
        self._op, self._payload = "insert", payload
        return self

    def update(self, payload, *a, **k):
        self._op, self._payload = "update", payload
        return self

    def upsert(self, payload, *a, **k):
        self._op, self._payload = "upsert", payload
        return self

    def delete(self, *a, **k):
        self._op = "delete"
        return self

    def execute(self):
        if self._op != "select":
            self._writes.append((self._table, self._op, self._payload))
            return _Resp([self._payload] if self._payload else [])
        rows = self._rows if self._limit is None else self._rows[: self._limit]
        if self._single:
            return _Resp(rows[0] if rows else None)
        return _Resp(list(rows))


class _FakeSupabase:
    def __init__(self, tables: dict):
        self.tables = tables
        self.writes: list = []

    def table(self, name):
        return _Query(name, list(self.tables.get(name, [])), self.writes)


def _abonnement(user_id: str, plan: str) -> dict:
    return {
        "user_id": user_id,
        "stripe_subscription_id": f"sub_{plan}",
        "stripe_price_id": None,
        "plan": plan,
        "status": "active",
        "created_at": "2026-09-01T00:00:00+00:00",
    }


def _db(**overrides) -> _FakeSupabase:
    tables: dict = {
        "subscriptions": [],
        "monuments": [{"id": "mon-1", "user_id": "u1"}],
        "projets": [{"id": "prj-1", "monument_id": "mon-1"}],
        "project_members": [{"monument_id": "mon-1", "user_id": "u1", "role": "owner"}],
        "projet_members": [],
        "dossiers": [],
        "aide_suivis": [],
    }
    tables.update(overrides)
    return _FakeSupabase(tables)


def _refus(test: unittest.TestCase, fn, *args, **kwargs) -> HTTPException:
    with test.assertRaises(HTTPException) as ctx:
        fn(*args, **kwargs)
    test.assertEqual(ctx.exception.status_code, 402)
    return ctx.exception


class CreationMonumentTest(unittest.TestCase):
    BODY = monuments_router.CreateMonumentRequest(
        nom="Chapelle", commune="Rouen", protection="classe", proprietaire="prive_personne_physique"
    )

    def test_second_monument_refuse_au_gratuit_et_rien_ecrit(self):
        db = _db()
        _refus(self, monuments_router.create_monument, self.BODY, "u1", db)
        self.assertEqual(db.writes, [])

    def test_le_quota_est_compte_sur_l_appelant(self):
        """Le plafond de monuments est le seul qui ne consulte PAS l'offre d'un
        propriétaire : le bien n'existe pas encore."""
        db = _db()
        # La route continue au-delà du contrôle et bute sur la base factice :
        # c'est le contrôle et ses arguments qu'on observe, pas la création.
        with (
            patch.object(monuments_router.quotas, "verifier_creation_monument") as check,
            self.assertRaises(HTTPException),
        ):
            monuments_router.create_monument(self.BODY, "u1", db)
        check.assert_called_once_with(db, "u1")


class SuppressionMonumentTest(unittest.TestCase):
    def test_refusee_au_gratuit_et_rien_supprime(self):
        db = _db()
        _refus(self, monuments_router.delete_monument, "mon-1", "u1", db)
        self.assertEqual(db.writes, [])

    def test_autorisee_avec_multi_monuments(self):
        db = _db(subscriptions=[_abonnement("u1", "multi_monuments")])
        monuments_router.delete_monument("mon-1", "u1", db)
        self.assertIn(("monuments", "delete", None), db.writes)


class CreationProjetTest(unittest.TestCase):
    BODY = projets_router.CreateProjetRequest(titre="Toiture")

    def test_troisieme_projet_refuse_au_gratuit_et_rien_ecrit(self):
        db = _db(
            projets=[
                {"id": "prj-1", "monument_id": "mon-1"},
                {"id": "prj-2", "monument_id": "mon-1"},
            ]
        )
        _refus(self, projets_router.create_projet, "mon-1", self.BODY, "u1", db)
        self.assertEqual(db.writes, [])

    def test_deuxieme_projet_autorise_au_gratuit(self):
        db = _db()
        with patch.object(projets_router, "get_projet_role", return_value="owner"):
            created = projets_router.create_projet("mon-1", self.BODY, "u1", db)
        self.assertEqual(created["monument_id"], "mon-1")

    def test_veille_ne_plafonne_pas(self):
        db = _db(
            projets=[{"id": f"prj-{i}", "monument_id": "mon-1"} for i in range(7)],
            subscriptions=[_abonnement("u1", "veille")],
        )
        with patch.object(projets_router, "get_projet_role", return_value="owner"):
            projets_router.create_projet("mon-1", self.BODY, "u1", db)


class SuppressionProjetTest(unittest.TestCase):
    def test_refusee_au_gratuit_et_rien_supprime(self):
        db = _db()
        _refus(self, projets_router.delete_projet, "prj-1", "u1", db)
        self.assertEqual(db.writes, [])

    def test_autorisee_avec_veille(self):
        db = _db(subscriptions=[_abonnement("u1", "veille")])
        projets_router.delete_projet("prj-1", "u1", db)
        self.assertIn(("projets", "delete", None), db.writes)


class FicheAideAVenirTest(unittest.TestCase):
    """GET /aides/{id} est le seul chemin vers la fiche complète d'une aide,
    donc la seule porte par laquelle le nom d'une aide « Disponibles bientôt »,
    masqué dans le diagnostic, pourrait encore sortir."""

    def _aides(self, ouverture: date | None) -> dict[str, Aide]:
        aide = Aide.model_validate(
            {
                "slug": "aide-a-venir",
                "nom": "Appel à projets 2027",
                "organisme": "Région",
                "categorie": "region",
                "type": "subvention",
                "description": "d",
                "conditions": [],
                "hard_filters": {},
                "calendrier": {"permanent": False, "date_ouverture": ouverture},
            }
        )
        return {"aide-a-venir": aide}

    def test_gratuit_ne_peut_pas_ouvrir_la_fiche_d_une_aide_a_venir(self):
        futur = date.today() + timedelta(days=60)
        with (
            patch("routers.aides.load_all_aides", return_value=self._aides(futur)),
            patch("routers.aides.billing.offre_du_compte", return_value=GRATUIT),
        ):
            _refus(self, get_aide, "aide-a-venir", "u1", _db())

    def test_veille_ouvre_la_fiche(self):
        futur = date.today() + timedelta(days=60)
        with (
            patch("routers.aides.load_all_aides", return_value=self._aides(futur)),
            patch("routers.aides.billing.offre_du_compte", return_value=VEILLE),
        ):
            aide = get_aide("aide-a-venir", "u1", _db())
        self.assertEqual(aide["nom"], "Appel à projets 2027")

    def test_aide_deja_ouverte_reste_gratuite(self):
        """Le détail d'une aide déposable aujourd'hui n'est plus payant."""
        with (
            patch("routers.aides.load_all_aides", return_value=self._aides(None)),
            patch("routers.aides.billing.offre_du_compte", return_value=GRATUIT),
        ):
            aide = get_aide("aide-a-venir", "u1", _db())
        self.assertEqual(aide["nom"], "Appel à projets 2027")

    def test_un_dossier_deja_ouvert_leve_le_masque(self):
        """`disponibilite` range aussi en « bientôt » une aide dont la date
        limite est passée. Sans cette exemption, un dossier ouvert en juin
        perdrait le nom de son aide au lendemain de la date limite."""
        passe = date.today() - timedelta(days=10)
        aides = {
            "aide-a-venir": Aide.model_validate(
                {
                    "slug": "aide-a-venir",
                    "nom": "Appel à projets 2026",
                    "organisme": "Région",
                    "categorie": "region",
                    "type": "subvention",
                    "description": "d",
                    "conditions": [],
                    "hard_filters": {},
                    "calendrier": {"permanent": False, "date_limite": passe},
                }
            )
        }
        db = _db(dossiers=[{"id": "d1", "user_id": "u1", "aide_id": "aide-a-venir"}])
        with (
            patch("routers.aides.load_all_aides", return_value=aides),
            patch("routers.aides.billing.offre_du_compte", return_value=GRATUIT),
        ):
            aide = get_aide("aide-a-venir", "u1", db)
        self.assertEqual(aide["nom"], "Appel à projets 2026")

    def test_le_dossier_d_un_autre_compte_ne_leve_rien(self):
        futur = date.today() + timedelta(days=60)
        db = _db(dossiers=[{"id": "d1", "user_id": "autre", "aide_id": "aide-a-venir"}])
        with (
            patch("routers.aides.load_all_aides", return_value=self._aides(futur)),
            patch("routers.aides.billing.offre_du_compte", return_value=GRATUIT),
        ):
            _refus(self, get_aide, "aide-a-venir", "u1", db)


if __name__ == "__main__":
    unittest.main()
