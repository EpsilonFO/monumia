"""Tests du cookie httpOnly portant le refresh token.

Utilise TestClient + dependency_overrides : les fakes miment supabase-py
(même approche fluent-query que test_oauth_profile_status.py).
"""

import unittest
from types import SimpleNamespace

from fastapi.testclient import TestClient

from db import get_anon_supabase, get_supabase
from main import app

PROFILE_ROW = {
    "id": "user-1",
    "email": "marie@exemple.fr",
    "prenom": "Marie",
    "nom": "Dupont",
    "segment": "prive",
    "telephone": None,
    "prive_type_proprietaire": "personne_physique",
    "prive_regime_fiscal": None,
    "btp": None,
    "onboarding_complete": True,
    "notification_preferences": {},
    "created_at": "2026-01-01T00:00:00Z",
    "has_aides_access": False,
    "account_type": "proprietaire",
    "metier": None,
}


class _Resp:
    def __init__(self, data):
        self.data = data


class _UsersQuery:
    def __init__(self, responses):
        self._responses = responses

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def single(self):
        return self

    def maybe_single(self):
        return self

    def insert(self, *a, **k):
        return self

    def execute(self):
        return self._responses.pop(0)


class _FakeSupabase:
    def __init__(self, users_responses):
        self._users = _UsersQuery(list(users_responses))

    def table(self, name):
        return self._users


def _session(access="at-1", refresh="rt-1"):
    return SimpleNamespace(
        access_token=access,
        refresh_token=refresh,
        user=SimpleNamespace(id="user-1"),
    )


class _FakeAnonAuth:
    def __init__(self):
        self.signed_out = False

    def sign_in_with_password(self, creds):
        return SimpleNamespace(user=SimpleNamespace(id="user-1"), session=_session())

    def sign_up(self, creds):
        return SimpleNamespace(user=SimpleNamespace(id="user-1"), session=_session())

    def refresh_session(self, token):
        if token != "rt-1":
            raise ValueError("invalid refresh token")
        return SimpleNamespace(user=SimpleNamespace(id="user-1"), session=_session("at-2", "rt-2"))

    def sign_out(self):
        self.signed_out = True


class _FakeAnon:
    def __init__(self):
        self.auth = _FakeAnonAuth()


class RefreshCookieTest(unittest.TestCase):
    def setUp(self):
        self.anon = _FakeAnon()
        app.dependency_overrides[get_anon_supabase] = lambda: self.anon
        app.dependency_overrides[get_supabase] = lambda: _FakeSupabase([_Resp(dict(PROFILE_ROW))])
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_login_pose_le_cookie_et_ne_renvoie_plus_le_refresh_token(self):
        res = self.client.post(
            "/auth/login", json={"email": "marie@exemple.fr", "password": "Motdepasse1"}
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["access_token"], "at-1")
        self.assertNotIn("refresh_token", body)
        cookie = res.headers.get("set-cookie", "")
        self.assertIn("monumia_refresh=rt-1", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Path=/auth", cookie)
        self.assertIn("SameSite=lax", cookie)

    def test_register_pose_le_cookie_et_ne_renvoie_plus_le_refresh_token(self):
        # insert du profil puis _get_profile : deux réponses users
        app.dependency_overrides[get_supabase] = lambda: _FakeSupabase(
            [_Resp(None), _Resp(dict(PROFILE_ROW))]
        )
        res = self.client.post(
            "/auth/register",
            json={
                "email": "marie@exemple.fr",
                "password": "Motdepasse1",
                "prenom": "Marie",
                "nom": "Dupont",
                "segment": "prive",
            },
        )
        self.assertEqual(res.status_code, 201)
        self.assertNotIn("refresh_token", res.json())
        self.assertIn("monumia_refresh=rt-1", res.headers.get("set-cookie", ""))


if __name__ == "__main__":
    unittest.main()
