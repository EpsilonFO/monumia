"""Tests de GET /auth/oauth/profile-status.

Distingue un utilisateur Google déjà onboardé (ligne users existante → profil)
d'un nouveau venu (pas de ligne → prefill depuis les métadonnées Google).
"""

import unittest
from types import SimpleNamespace

from routers.auth import oauth_profile_status


class _Resp:
    def __init__(self, data):
        self.data = data


class _UsersQuery:
    """Mime le chaînage fluent supabase-py ; répond depuis une file de réponses."""

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

    def execute(self):
        return self._responses.pop(0)


class _FakeSupabase:
    def __init__(self, users_responses):
        self._users = _UsersQuery(list(users_responses))

    def table(self, name):
        assert name == "users", f"table inattendue : {name}"
        return self._users


# Ligne users sans commune (segment prive) : _get_profile ne touche pas la
# table communes, le fake reste simple.
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


def _auth_user(metadata=None):
    return SimpleNamespace(id="user-1", email="marie@exemple.fr", user_metadata=metadata or {})


class OauthProfileStatusTest(unittest.TestCase):
    def test_profil_existant_renvoie_le_user(self):
        supabase = _FakeSupabase([_Resp({"id": "user-1"}), _Resp(dict(PROFILE_ROW))])
        result = oauth_profile_status(auth_user=_auth_user(), supabase=supabase)
        self.assertTrue(result["exists"])
        self.assertEqual(result["user"]["prenom"], "Marie")

    def test_profil_absent_prefill_depuis_given_family_name(self):
        supabase = _FakeSupabase([_Resp(None)])
        result = oauth_profile_status(
            auth_user=_auth_user({"given_name": "Marie", "family_name": "Dupont"}),
            supabase=supabase,
        )
        self.assertFalse(result["exists"])
        self.assertEqual(
            result["prefill"],
            {"email": "marie@exemple.fr", "prenom": "Marie", "nom": "Dupont"},
        )

    def test_prefill_fallback_full_name(self):
        supabase = _FakeSupabase([_Resp(None)])
        result = oauth_profile_status(
            auth_user=_auth_user({"full_name": "Marie Dupont"}), supabase=supabase
        )
        self.assertEqual(result["prefill"]["prenom"], "Marie")
        self.assertEqual(result["prefill"]["nom"], "Dupont")

    def test_prefill_sans_metadata(self):
        supabase = _FakeSupabase([_Resp(None)])
        result = oauth_profile_status(auth_user=_auth_user(), supabase=supabase)
        self.assertEqual(
            result["prefill"],
            {"email": "marie@exemple.fr", "prenom": "", "nom": ""},
        )

    def test_maybe_single_renvoyant_none_directement(self):
        # Certaines versions de supabase-py renvoient None (pas de réponse) sur 0 ligne.
        supabase = _FakeSupabase([None])
        result = oauth_profile_status(auth_user=_auth_user(), supabase=supabase)
        self.assertFalse(result["exists"])


if __name__ == "__main__":
    unittest.main()
