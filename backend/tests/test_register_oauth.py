"""Tests de POST /auth/register-oauth : création du profil applicatif pour un
utilisateur auth créé par Google (email lu depuis le token, jamais du client),
et idempotence en cas de double soumission."""

import unittest
from types import SimpleNamespace

from fastapi import BackgroundTasks

from routers.auth import RegisterOauthRequest, register_oauth


class _Resp:
    def __init__(self, data):
        self.data = data


class _RaiseOnExecute:
    """Sentinel : quand cette valeur est dépilée par execute(), lève une exception."""


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
        resp = self._responses.pop(0)
        if isinstance(resp, _RaiseOnExecute):
            raise Exception("UNIQUE constraint failed: users_pkey")
        return resp


class _AbonnementsQuery:
    """L'octroi de l'offre de création : on ne capture que ce qui est upserté."""

    def __init__(self, upserts):
        self._upserts = upserts

    def upsert(self, row, *a, **k):
        self._upserts.append(row)
        return self

    def execute(self):
        return _Resp(None)


class _FakeSupabase:
    def __init__(self, users_responses):
        self.inserted = []
        self.abonnements = []
        self._users = _UsersQuery(list(users_responses), self.inserted)

    def table(self, name):
        if name == "subscriptions":
            return _AbonnementsQuery(self.abonnements)
        assert name == "users", f"table inattendue : {name}"
        return self._users


PROFILE_ROW = {
    "id": "user-1",
    "email": "marie@exemple.fr",
    "prenom": "Marie",
    "nom": "Dupont",
    "telephone": None,
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
        body = RegisterOauthRequest(prenom="Marie", nom="Dupont")
        result = register_oauth(
            body, background_tasks=BackgroundTasks(), auth_user=AUTH_USER, supabase=supabase
        )

        self.assertEqual(len(supabase.inserted), 1)
        row = supabase.inserted[0]
        self.assertEqual(row["id"], "user-1")
        self.assertEqual(row["email"], "marie@exemple.fr")  # depuis le token
        self.assertFalse(row["onboarding_complete"])
        self.assertIn("notification_preferences", row)
        self.assertEqual(result["user"]["prenom"], "Marie")

    def test_creation_quand_maybe_single_renvoie_data_none(self):
        # 1) maybe_single renvoie _Resp(None) (.data is None, pas None brut)
        # 2) insert 3) single de _get_profile
        supabase = _FakeSupabase([_Resp(None), _Resp(None), _Resp(dict(PROFILE_ROW))])
        body = RegisterOauthRequest(prenom="Marie", nom="Dupont")
        result = register_oauth(
            body, background_tasks=BackgroundTasks(), auth_user=AUTH_USER, supabase=supabase
        )

        self.assertEqual(len(supabase.inserted), 1)
        self.assertEqual(result["user"]["prenom"], "Marie")

    def test_idempotent_si_profil_deja_cree(self):
        # 1) maybe_single trouve la ligne 2) single de _get_profile
        supabase = _FakeSupabase([_Resp({"id": "user-1"}), _Resp(dict(PROFILE_ROW))])
        body = RegisterOauthRequest(prenom="Marie", nom="Dupont")
        result = register_oauth(
            body, background_tasks=BackgroundTasks(), auth_user=AUTH_USER, supabase=supabase
        )

        self.assertEqual(supabase.inserted, [])  # pas de second insert
        self.assertEqual(result["user"]["email"], "marie@exemple.fr")

    def test_insert_concurrent_retombe_sur_le_profil(self):
        # Simule une course : maybe_single ne voit rien (None brut), insert lève
        # une violation d'unicité, _get_profile retombe sur la ligne existante.
        # File : 1) maybe_single 2) insert (_RaiseOnExecute) 3) single _get_profile
        supabase = _FakeSupabase([None, _RaiseOnExecute(), _Resp(dict(PROFILE_ROW))])
        body = RegisterOauthRequest(prenom="Marie", nom="Dupont")
        result = register_oauth(
            body, background_tasks=BackgroundTasks(), auth_user=AUTH_USER, supabase=supabase
        )

        self.assertEqual(result["user"]["prenom"], "Marie")


COLLAB_ROW = {
    "id": "user-1",
    "email": "marie@exemple.fr",
    "prenom": "Marie",
    "nom": "Dupont",
    "telephone": None,
    "onboarding_complete": True,
    "notification_preferences": {},
    "created_at": "2026-01-01T00:00:00Z",
    "account_type": "collaborateur",
    "metier": "architecte",
}


class RegisterCollaboratorOauthTest(unittest.TestCase):
    def test_creation_collaborateur(self):
        from routers.auth import RegisterCollaboratorOauthRequest, register_collaborator_oauth

        supabase = _FakeSupabase([None, _Resp(None), _Resp(dict(COLLAB_ROW))])
        body = RegisterCollaboratorOauthRequest(prenom="Marie", nom="Dupont", metier="architecte")
        result = register_collaborator_oauth(
            body, background_tasks=BackgroundTasks(), auth_user=AUTH_USER, supabase=supabase
        )

        row = supabase.inserted[0]
        self.assertEqual(row["account_type"], "collaborateur")
        self.assertEqual(row["metier"], "architecte")
        self.assertTrue(row["onboarding_complete"])
        self.assertEqual(row["email"], "marie@exemple.fr")  # email depuis le token
        self.assertIsNone(row["telephone"])
        self.assertEqual(result["user"]["accountType"], "collaborateur")

    def test_idempotent(self):
        from routers.auth import RegisterCollaboratorOauthRequest, register_collaborator_oauth

        supabase = _FakeSupabase([_Resp({"id": "user-1"}), _Resp(dict(COLLAB_ROW))])
        body = RegisterCollaboratorOauthRequest(prenom="Marie", nom="Dupont", metier="architecte")
        result = register_collaborator_oauth(
            body, background_tasks=BackgroundTasks(), auth_user=AUTH_USER, supabase=supabase
        )

        self.assertEqual(supabase.inserted, [])
        self.assertEqual(result["user"]["accountType"], "collaborateur")


if __name__ == "__main__":
    unittest.main()
