"""Tests de POST /auth/register-oauth : création du profil applicatif pour un
utilisateur auth créé par Google (email lu depuis le token, jamais du client),
et idempotence en cas de double soumission."""

import unittest
from types import SimpleNamespace

from routers.auth import RegisterOauthRequest, register_oauth


class _Resp:
    def __init__(self, data):
        self.data = data


class _UsersQuery:
    """Mime le chaînage fluent supabase-py ; capture les insert, répond en file."""

    def __init__(self, responses, inserted):
        self._responses = responses
        self._inserted = inserted

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def single(self):
        return self

    def maybe_single(self):
        return self

    def insert(self, row):
        self._inserted.append(row)
        return self

    def execute(self):
        return self._responses.pop(0)


class _FakeSupabase:
    def __init__(self, users_responses):
        self.inserted = []
        self._users = _UsersQuery(list(users_responses), self.inserted)

    def table(self, name):
        assert name == "users", f"table inattendue : {name}"
        return self._users


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
    "onboarding_complete": False,
    "notification_preferences": {},
    "created_at": "2026-01-01T00:00:00Z",
    "account_type": "proprietaire",
}

AUTH_USER = SimpleNamespace(id="user-1", email="marie@exemple.fr", user_metadata={})


class RegisterOauthTest(unittest.TestCase):
    def test_creation_du_profil(self):
        # 1) maybe_single (pas de ligne) 2) insert 3) single de _get_profile
        supabase = _FakeSupabase([None, _Resp(None), _Resp(dict(PROFILE_ROW))])
        body = RegisterOauthRequest(
            prenom="Marie",
            nom="Dupont",
            segment="prive",
            prive_type_proprietaire="personne_physique",
        )
        result = register_oauth(body, auth_user=AUTH_USER, supabase=supabase)

        self.assertEqual(len(supabase.inserted), 1)
        row = supabase.inserted[0]
        self.assertEqual(row["id"], "user-1")
        self.assertEqual(row["email"], "marie@exemple.fr")  # depuis le token
        self.assertEqual(row["segment"], "prive")
        self.assertFalse(row["onboarding_complete"])
        self.assertIn("notification_preferences", row)
        self.assertEqual(result["user"]["prenom"], "Marie")

    def test_idempotent_si_profil_deja_cree(self):
        # 1) maybe_single trouve la ligne 2) single de _get_profile
        supabase = _FakeSupabase(
            [_Resp({"id": "user-1"}), _Resp(dict(PROFILE_ROW))]
        )
        body = RegisterOauthRequest(prenom="Marie", nom="Dupont", segment="prive")
        result = register_oauth(body, auth_user=AUTH_USER, supabase=supabase)

        self.assertEqual(supabase.inserted, [])  # pas de second insert
        self.assertEqual(result["user"]["email"], "marie@exemple.fr")


if __name__ == "__main__":
    unittest.main()
