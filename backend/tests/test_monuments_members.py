"""Test de la fonction pure d'indexation des membres pour la liste des projets."""

import unittest

from routers.monuments import build_members_index


class BuildMembersIndexTests(unittest.TestCase):
    def test_groups_members_by_monument_with_profile(self):
        member_rows = [
            {"monument_id": "m1", "user_id": "u1", "role": "owner"},
            {"monument_id": "m1", "user_id": "u2", "role": "member"},
            {"monument_id": "m2", "user_id": "u1", "role": "owner"},
        ]
        profiles = {
            "u1": {"prenom": "Anne", "nom": "Roy"},
            "u2": {"prenom": "Léo", "nom": "Bon"},
        }
        index = build_members_index(member_rows, profiles)
        self.assertEqual(
            index["m1"],
            [
                {"user_id": "u1", "prenom": "Anne", "nom": "Roy", "role": "owner"},
                {"user_id": "u2", "prenom": "Léo", "nom": "Bon", "role": "member"},
            ],
        )
        self.assertEqual(len(index["m2"]), 1)

    def test_missing_profile_falls_back_to_empty_names(self):
        index = build_members_index([{"monument_id": "m1", "user_id": "u9", "role": "member"}], {})
        self.assertEqual(
            index["m1"], [{"user_id": "u9", "prenom": "", "nom": "", "role": "member"}]
        )

    def test_empty(self):
        self.assertEqual(build_members_index([], {}), {})


if __name__ == "__main__":
    unittest.main()
