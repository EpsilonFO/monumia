"""Tests des droits d'accès payants et du webhook Stripe.

Deux familles de risques sont couvertes ici, parce qu'elles coûtent de l'argent
ou de la confiance :

  • un accès accordé à tort (contenu payant offert) ou refusé à tort (client qui
    a payé et ne voit rien) ;
  • un webhook qui encaisse sans débloquer — signature acceptée à tort, ou
    événement rejoué qui saute le traitement.

Les fakes miment supabase-py comme dans test_refresh_cookie.py : chaînage
fluide, `execute()` qui rend une réponse préparée.
"""

import base64
import hashlib
import hmac
import json
import time
import unittest

from fastapi.testclient import TestClient

from db import get_supabase
from main import app
from routers import aides as aides_router
from services import stripe_billing as billing

WEBHOOK_SECRET = "whsec_test_secret"


def _fake_jwt(sub: str = "user-1") -> str:
    def b64(payload: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()

    header = b64({"alg": "ES256", "kid": "test-key", "typ": "JWT"})
    return f"{header}.{b64({'sub': sub, 'aud': 'authenticated'})}.c2ln"


class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    """Requête fluide qui renvoie toujours la même réponse, et note les écrits."""

    def __init__(self, table: str, rows, writes: list, raise_on_insert: Exception | None = None):
        self._table = table
        self._rows = rows
        self._writes = writes
        self._raise_on_insert = raise_on_insert
        self._payload = None
        self._op = "select"

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def single(self):
        return self

    def maybe_single(self):
        return self

    def insert(self, payload, *a, **k):
        self._op, self._payload = "insert", payload
        return self

    def upsert(self, payload, *a, **k):
        self._op, self._payload = "upsert", payload
        return self

    def update(self, payload, *a, **k):
        self._op, self._payload = "update", payload
        return self

    def delete(self, *a, **k):
        self._op = "delete"
        return self

    def execute(self):
        if self._op in {"insert", "upsert", "update", "delete"}:
            self._writes.append((self._table, self._op, self._payload))
            if self._op == "insert" and self._raise_on_insert is not None:
                raise self._raise_on_insert
            return _Resp([self._payload] if self._payload else [])
        return _Resp(self._rows)


class _FakeSupabase:
    """Base factice pilotée par un dict {table: lignes}."""

    def __init__(self, tables: dict, insert_errors: dict | None = None):
        self.tables = tables
        self.insert_errors = insert_errors or {}
        self.writes: list = []

    def table(self, name):
        return _Query(name, self.tables.get(name, []), self.writes, self.insert_errors.get(name))


def _base_tables(**overrides) -> dict:
    tables = {
        "users": {"id": "user-1", "has_aides_access": False},
        "subscriptions": [],
        "monument_unlocks": [],
        "project_members": [],
        "monuments": [{"id": "projet-1"}],
        "stripe_events": [],
    }
    tables.update(overrides)
    return tables


# ---------------------------------------------------------------------------
# Droits d'accès
# ---------------------------------------------------------------------------


class AccessRulesTest(unittest.TestCase):
    def test_aucun_droit_par_defaut(self):
        """Un compte neuf n'a accès à aucun projet."""
        db = _FakeSupabase(_base_tables())
        snapshot = billing.access_snapshot(db, "user-1")
        self.assertFalse(snapshot["allAccess"])
        self.assertEqual(snapshot["unlockedMonumentIds"], [])
        self.assertIsNone(snapshot["subscription"])
        self.assertFalse(billing.has_monument_access(db, "user-1", "projet-1"))

    def test_flag_manuel_ouvre_tout(self):
        """has_aides_access reste la porte de service (beta, démos)."""
        db = _FakeSupabase(_base_tables(users={"id": "user-1", "has_aides_access": True}))
        snapshot = billing.access_snapshot(db, "user-1")
        self.assertTrue(snapshot["allAccess"])
        self.assertTrue(billing.has_monument_access(db, "user-1", "projet-1"))

    def test_abonnement_actif_ouvre_tout(self):
        db = _FakeSupabase(
            _base_tables(
                subscriptions=[
                    {
                        "stripe_subscription_id": "sub_1",
                        "status": "active",
                        "current_period_end": "2026-09-06T00:00:00+00:00",
                        "cancel_at_period_end": False,
                    }
                ]
            )
        )
        snapshot = billing.access_snapshot(db, "user-1")
        self.assertTrue(snapshot["allAccess"])
        self.assertEqual(snapshot["subscription"]["status"], "active")
        # Inutile d'énumérer les projets quand tout est ouvert.
        self.assertEqual(snapshot["unlockedMonumentIds"], [])

    def test_impaye_conserve_l_acces_le_temps_des_relances(self):
        """past_due = carte expirée en cours de relance, pas un resquilleur."""
        self.assertIn("past_due", billing.ACTIVE_SUBSCRIPTION_STATUSES)
        self.assertNotIn("canceled", billing.ACTIVE_SUBSCRIPTION_STATUSES)
        self.assertNotIn("unpaid", billing.ACTIVE_SUBSCRIPTION_STATUSES)

    def test_deblocage_a_l_unite_ne_vaut_que_pour_son_projet(self):
        db = _FakeSupabase(
            _base_tables(monument_unlocks=[{"monument_id": "projet-1", "id": "unlock-1"}])
        )
        snapshot = billing.access_snapshot(db, "user-1")
        self.assertFalse(snapshot["allAccess"])
        self.assertEqual(snapshot["unlockedMonumentIds"], ["projet-1"])

    def test_projet_paye_par_le_proprietaire_profite_a_l_equipe(self):
        """Le déblocage porte sur le projet : un invité ne repaie pas."""
        db = _FakeSupabase(
            {
                "users": {"id": "user-2", "has_aides_access": False},
                "subscriptions": [],
                # Payé par user-1, mais c'est user-2 qui consulte.
                "monument_unlocks": [{"monument_id": "projet-1", "id": "unlock-1"}],
                "project_members": [{"monument_id": "projet-1"}],
                "monuments": [],
            }
        )
        self.assertTrue(billing.has_monument_access(db, "user-2", "projet-1"))
        self.assertEqual(billing.unlocked_monument_ids(db, "user-2"), ["projet-1"])

    def test_un_deblocage_etranger_ne_fuite_pas(self):
        """Un projet dont on n'est pas membre n'apparaît jamais comme débloqué."""
        db = _FakeSupabase(
            {
                "users": {"id": "user-3", "has_aides_access": False},
                "subscriptions": [],
                "monument_unlocks": [{"monument_id": "projet-1", "id": "unlock-1"}],
                # Ni membre, ni propriétaire d'aucun projet.
                "project_members": [],
                "monuments": [],
            }
        )
        self.assertEqual(billing.unlocked_monument_ids(db, "user-3"), [])


class _FilteringQuery:
    """Requête qui applique réellement `eq` / `in_`.

    Le fake principal ignore les filtres, ce qui suffit tant qu'un test ne parle
    que d'un utilisateur. Dès qu'il faut distinguer le collaborateur qui regarde
    du propriétaire qui paie, il faut filtrer pour de vrai.
    """

    def __init__(self, rows: list):
        self._rows = rows
        self._single = False

    def select(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def eq(self, column, value):
        self._rows = [r for r in self._rows if r.get(column) == value]
        return self

    def in_(self, column, values):
        allowed = set(values)
        self._rows = [r for r in self._rows if r.get(column) in allowed]
        return self

    def maybe_single(self):
        self._single = True
        return self

    def single(self):
        self._single = True
        return self

    def execute(self):
        if self._single:
            return _Resp(self._rows[0] if self._rows else None)
        return _Resp(list(self._rows))


class _FilteringSupabase:
    def __init__(self, tables: dict):
        self.tables = tables

    def table(self, name):
        return _FilteringQuery(list(self.tables.get(name, [])))


def _team_tables(**overrides) -> dict:
    """Projet `projet-1` appartenant à `owner`, avec `collab` comme membre."""
    tables = {
        "users": [
            {"id": "owner", "has_aides_access": False},
            {"id": "collab", "has_aides_access": False},
        ],
        "subscriptions": [],
        "monument_unlocks": [],
        "monuments": [{"id": "projet-1", "user_id": "owner"}],
        "project_members": [{"monument_id": "projet-1", "user_id": "collab"}],
    }
    tables.update(overrides)
    return tables


_ABONNEMENT_OWNER = [
    {
        "user_id": "owner",
        "stripe_subscription_id": "sub_1",
        "status": "active",
        "current_period_end": "2026-09-06T00:00:00+00:00",
        "cancel_at_period_end": False,
    }
]


class OwnerCoverageTest(unittest.TestCase):
    """L'abonnement du propriétaire couvre son projet, donc son équipe.

    Régression vécue : un collaborateur invité sur le projet d'un abonné voyait
    les aides caviardées, même promu chef de projet adjoint. Le déblocage à
    l'unité était bien partagé (il porte sur le projet), mais l'abonnement vit
    sur la ligne de l'abonné — et n'était lu que pour le spectateur.
    """

    def test_abonnement_du_proprietaire_couvre_l_equipe(self):
        db = _FilteringSupabase(_team_tables(subscriptions=_ABONNEMENT_OWNER))
        self.assertTrue(billing.has_monument_access(db, "collab", "projet-1"))
        self.assertEqual(billing.unlocked_monument_ids(db, "collab"), ["projet-1"])

    def test_le_collaborateur_ne_devient_pas_abonne_pour_autant(self):
        """Le projet est couvert, pas le compte : ses autres projets restent fermés."""
        db = _FilteringSupabase(_team_tables(subscriptions=_ABONNEMENT_OWNER))
        snapshot = billing.access_snapshot(db, "collab")
        self.assertFalse(snapshot["allAccess"])
        self.assertIsNone(snapshot["subscription"])
        self.assertEqual(snapshot["unlockedMonumentIds"], ["projet-1"])

    def test_octroi_manuel_du_proprietaire_couvre_aussi(self):
        db = _FilteringSupabase(
            _team_tables(
                users=[
                    {"id": "owner", "has_aides_access": True},
                    {"id": "collab", "has_aides_access": False},
                ]
            )
        )
        self.assertTrue(billing.has_monument_access(db, "collab", "projet-1"))

    def test_proprietaire_non_payant_laisse_le_projet_ferme(self):
        db = _FilteringSupabase(_team_tables())
        self.assertFalse(billing.has_monument_access(db, "collab", "projet-1"))
        self.assertEqual(billing.unlocked_monument_ids(db, "collab"), [])

    def test_projet_d_un_abonne_dont_on_n_est_pas_membre_ne_fuite_pas(self):
        """Le cœur du risque : la couverture ne doit pas ouvrir un projet étranger."""
        db = _FilteringSupabase(_team_tables(subscriptions=_ABONNEMENT_OWNER, project_members=[]))
        self.assertEqual(billing.unlocked_monument_ids(db, "collab"), [])


# ---------------------------------------------------------------------------
# Redaction serveur
# ---------------------------------------------------------------------------


class RedactionTest(unittest.TestCase):
    def _aide(self) -> dict:
        return {
            "id": "aide-1",
            "nom": "Subvention DRAC pour monuments classés",
            "nomCourt": "DRAC — MH classés",
            "organisme": "DRAC Normandie",
            "description": "Aide de l'État aux travaux de restauration.",
            "urlOfficielle": "https://exemple.gouv.fr",
            "montantMax": 40000,
            "tauxMax": 40,
            "dateLimite": "2026-12-31",
            "categorie": "etat_drac",
        }

    def test_l_identite_du_financeur_part_le_montant_reste(self):
        redacted = aides_router.redact_locked_aide(self._aide())

        # Ce qu'on vend : impossible de savoir à qui s'adresser.
        self.assertEqual(redacted["nom"], aides_router.LOCKED_AIDE_LABEL)
        self.assertEqual(redacted["nomCourt"], aides_router.LOCKED_AIDE_LABEL)
        self.assertIsNone(redacted["organisme"])
        self.assertIsNone(redacted["urlOfficielle"])
        self.assertNotIn("DRAC", json.dumps(redacted, ensure_ascii=False))

        # L'argumentaire de vente, lui, reste entier.
        self.assertEqual(redacted["montantMax"], 40000)
        self.assertEqual(redacted["tauxMax"], 40)
        self.assertEqual(redacted["dateLimite"], "2026-12-31")
        self.assertEqual(redacted["categorie"], "etat_drac")
        self.assertEqual(redacted["id"], "aide-1")
        self.assertTrue(redacted["locked"])

    def test_projet_debloque_renvoie_le_diagnostic_intact(self):
        db = _FakeSupabase(
            _base_tables(monument_unlocks=[{"monument_id": "projet-1", "id": "unlock-1"}])
        )
        result = {"aidesEligibles": [{"aide": self._aide()}]}
        out = aides_router.redact_diagnostic_if_locked(result, db, "user-1", "projet-1")
        self.assertEqual(out["aidesEligibles"][0]["aide"]["organisme"], "DRAC Normandie")

    def test_projet_verrouille_masque_tous_les_seaux(self):
        db = _FakeSupabase(_base_tables())
        result = {
            "aidesEligibles": [{"aide": self._aide()}],
            "aidesPotentiellementEligibles": [{"aide": self._aide()}],
            "aidesAtteignables": [{"aide": self._aide()}],
            "aidesNonEligibles": [{"aide": self._aide()}],
        }
        out = aides_router.redact_diagnostic_if_locked(result, db, "user-1", "projet-1")
        for bucket in aides_router._DIAGNOSTIC_BUCKETS:
            self.assertEqual(out[bucket][0]["aide"]["nomCourt"], aides_router.LOCKED_AIDE_LABEL)


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------


def _sign(payload: bytes, secret: str = WEBHOOK_SECRET) -> str:
    """En-tête Stripe-Signature authentique (HMAC-SHA256 de « t.payload »)."""
    timestamp = int(time.time())
    signature = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={signature}"


def _checkout_event(event_id: str = "evt_1") -> dict:
    # `"object": "event"` fait partie de l'enveloppe réelle de Stripe, et
    # `construct_event` le lit pour écarter les notifications « thin » v2 : un
    # fixture qui l'omet ne teste pas le même chemin que la production.
    return {
        "id": event_id,
        "object": "event",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_1",
                "mode": "payment",
                "payment_status": "paid",
                "amount_total": 14900,
                "currency": "eur",
                "payment_intent": "pi_1",
                "client_reference_id": "user-1",
                "metadata": {
                    "user_id": "user-1",
                    "monument_id": "projet-1",
                    "plan": "dossier",
                },
            }
        },
    }


class WebhookTest(unittest.TestCase):
    def setUp(self):
        self.db = _FakeSupabase(_base_tables())
        app.dependency_overrides[get_supabase] = lambda: self.db
        self.client = TestClient(app)
        self._old_secret = billing.os.environ.get("STRIPE_WEBHOOK_SECRET")
        billing.os.environ["STRIPE_WEBHOOK_SECRET"] = WEBHOOK_SECRET

    def tearDown(self):
        app.dependency_overrides.clear()
        if self._old_secret is None:
            billing.os.environ.pop("STRIPE_WEBHOOK_SECRET", None)
        else:
            billing.os.environ["STRIPE_WEBHOOK_SECRET"] = self._old_secret

    def _post(self, event: dict, signature: str | None = None):
        payload = json.dumps(event).encode()
        return self.client.post(
            "/billing/webhook",
            content=payload,
            headers={"stripe-signature": signature or _sign(payload)},
        )

    def test_signature_absente_refusee(self):
        payload = json.dumps(_checkout_event()).encode()
        res = self.client.post("/billing/webhook", content=payload)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.db.writes, [])

    def test_signature_forgee_refusee(self):
        """Un corps signé avec une autre clé ne doit rien débloquer."""
        payload = json.dumps(_checkout_event()).encode()
        res = self.client.post(
            "/billing/webhook",
            content=payload,
            headers={"stripe-signature": _sign(payload, "whsec_mauvaise_cle")},
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.db.writes, [])

    def test_corps_altere_apres_signature_refuse(self):
        """La signature porte sur le corps : le modifier l'invalide."""
        original = json.dumps(_checkout_event()).encode()
        signature = _sign(original)
        falsifie = original.replace(b'"projet-1"', b'"projet-du-voisin"')
        res = self.client.post(
            "/billing/webhook", content=falsifie, headers={"stripe-signature": signature}
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.db.writes, [])

    def test_paiement_valide_enregistre_le_deblocage(self):
        res = self._post(_checkout_event())
        self.assertEqual(res.status_code, 200)

        unlocks = [w for w in self.db.writes if w[0] == "monument_unlocks"]
        self.assertEqual(len(unlocks), 1)
        row = unlocks[0][2]
        self.assertEqual(row["user_id"], "user-1")
        self.assertEqual(row["monument_id"], "projet-1")
        self.assertEqual(row["stripe_checkout_session_id"], "cs_test_1")
        self.assertEqual(row["amount_cents"], 14900)

    def test_paiement_en_attente_ne_debloque_pas(self):
        """Un virement SEPA annoncé mais non encaissé n'ouvre rien."""
        event = _checkout_event()
        event["data"]["object"]["payment_status"] = "unpaid"
        res = self._post(event)
        self.assertEqual(res.status_code, 200)
        self.assertEqual([w for w in self.db.writes if w[0] == "monument_unlocks"], [])

    def test_evenement_rejoue_traite_une_seule_fois(self):
        """Stripe livre « au moins une fois » : le second passage ne fait rien."""
        self.assertEqual(self._post(_checkout_event()).status_code, 200)

        # Le journal rejette désormais cet id (violation d'unicité Postgres).
        self.db.insert_errors["stripe_events"] = Exception(
            'duplicate key value violates unique constraint "stripe_events_pkey"'
        )
        res = self._post(_checkout_event())
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["duplicate"])
        self.assertEqual(len([w for w in self.db.writes if w[0] == "monument_unlocks"]), 1)

    def test_echec_d_ecriture_libere_le_verrou_pour_le_retry(self):
        """Sinon la nouvelle tentative de Stripe passerait pour un doublon et
        le paiement resterait sans effet, définitivement."""
        self.db.insert_errors["monument_unlocks"] = Exception("connexion perdue")
        res = self._post(_checkout_event())

        # 500 : Stripe doit réessayer, l'argent est encaissé sans l'accès.
        self.assertEqual(res.status_code, 500)
        # Et le verrou d'idempotence a bien été retiré pour que ce retry passe.
        self.assertIn(("stripe_events", "delete", None), self.db.writes)

    def test_abonnement_reflete_dans_la_base(self):
        event = {
            "id": "evt_sub",
            "object": "event",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_1",
                    "customer": "cus_1",
                    "status": "active",
                    "cancel_at_period_end": True,
                    "metadata": {"user_id": "user-1"},
                    "items": {
                        "data": [
                            {"price": {"id": "price_1"}, "current_period_end": 1790000000},
                        ]
                    },
                }
            },
        }
        self.assertEqual(self._post(event).status_code, 200)

        rows = [w for w in self.db.writes if w[0] == "subscriptions"]
        self.assertEqual(len(rows), 1)
        row = rows[0][2]
        self.assertEqual(row["user_id"], "user-1")
        self.assertEqual(row["status"], "active")
        self.assertEqual(row["stripe_price_id"], "price_1")
        self.assertTrue(row["cancel_at_period_end"])
        # `current_period_end` a migré de l'abonnement vers ses lignes : la
        # lecture doit suivre, sinon la date de fin est perdue.
        self.assertTrue(row["current_period_end"].startswith("2026-"))


if __name__ == "__main__":
    unittest.main()
