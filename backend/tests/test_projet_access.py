"""`require_projet_access` : la porte d'entrée de tout ce qui touche un projet.

Un projet n'a pas de partage propre — il hérite des droits de son monument.
On vérifie donc les trois issues : 404 (projet inexistant), délégation à
`require_project_access` (403 pour un rôle insuffisant, 404 pour un non-membre)
et le tuple `(ligne, rôle)` rendu au chemin nominal.
"""

import unittest

from fastapi import HTTPException

from services.project_access import require_projet_access


class _Resp:
    def __init__(self, data) -> None:
        self.data = data


class _FakeQuery:
    """Mime le chaînage fluent de supabase-py ; renvoie une réponse fixe."""

    def __init__(self, response) -> None:
        self._response = response

    def select(self, *_a, **_k) -> "_FakeQuery":
        return self

    def eq(self, *_a, **_k) -> "_FakeQuery":
        return self

    def maybe_single(self) -> "_FakeQuery":
        return self

    def execute(self):
        return self._response


class _FakeSupabase:
    def __init__(self, responses_by_table: dict) -> None:
        self._responses = responses_by_table

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(self._responses.get(name, _Resp(None)))


PROJET = {"id": "p1", "monument_id": "m1", "user_id": "u1", "travaux_envisages": ["toiture"]}
# Projet créé par quelqu'un d'autre : sans quoi la règle « le créateur garde au
# moins co_owner » masquerait les tests de rôle insuffisant.
PROJET_AUTRUI = {**PROJET, "user_id": "u9"}


class RequireProjetAccessTests(unittest.TestCase):
    def test_projet_inexistant_renvoie_404(self) -> None:
        supabase = _FakeSupabase({"projets": _Resp(None)})
        with self.assertRaises(HTTPException) as ctx:
            require_projet_access(supabase, "p1", "u1")  # type: ignore[arg-type]
        self.assertEqual(ctx.exception.status_code, 404)

    def test_maybe_single_renvoyant_none_ne_plante_pas(self) -> None:
        """maybe_single() peut rendre None, pas seulement un `.data` vide."""
        supabase = _FakeSupabase({"projets": None})
        with self.assertRaises(HTTPException) as ctx:
            require_projet_access(supabase, "p1", "u1")  # type: ignore[arg-type]
        self.assertEqual(ctx.exception.status_code, 404)

    def test_rend_la_ligne_et_le_role(self) -> None:
        supabase = _FakeSupabase(
            {
                "projets": _Resp(PROJET),
                "project_members": _Resp({"role": "co_owner"}),
            }
        )
        projet, role = require_projet_access(supabase, "p1", "u1")  # type: ignore[arg-type]
        self.assertEqual(projet, PROJET)
        self.assertEqual(role, "co_owner")

    def test_role_insuffisant_renvoie_403(self) -> None:
        supabase = _FakeSupabase(
            {
                "projets": _Resp(PROJET_AUTRUI),
                "project_members": _Resp({"role": "member"}),
            }
        )
        with self.assertRaises(HTTPException) as ctx:
            require_projet_access(supabase, "p1", "u1", "co_owner")  # type: ignore[arg-type]
        self.assertEqual(ctx.exception.status_code, 403)

    def test_appartenance_propre_au_projet_sans_role_sur_le_monument(self) -> None:
        """Le cas central : invité sur le seul chantier, rien sur le monument."""
        supabase = _FakeSupabase(
            {
                "projets": _Resp(PROJET_AUTRUI),
                "project_members": _Resp(None),
                "monuments": _Resp(None),
                "projet_members": _Resp({"role": "member"}),
            }
        )
        _, role = require_projet_access(supabase, "p1", "u1")  # type: ignore[arg-type]
        self.assertEqual(role, "member")

    def test_le_role_du_monument_l_emporte_s_il_est_plus_eleve(self) -> None:
        """On ne RESTREINT jamais un droit déjà acquis un cran plus haut."""
        supabase = _FakeSupabase(
            {
                "projets": _Resp(PROJET_AUTRUI),
                "project_members": _Resp({"role": "owner"}),
                "projet_members": _Resp({"role": "member"}),
            }
        )
        _, role = require_projet_access(supabase, "p1", "u1")  # type: ignore[arg-type]
        self.assertEqual(role, "owner")

    def test_le_createur_du_projet_garde_l_acces(self) -> None:
        """Défense en profondeur : sa ligne d'appartenance peut manquer."""
        supabase = _FakeSupabase(
            {
                "projets": _Resp(PROJET),
                "project_members": _Resp(None),
                "monuments": _Resp(None),
                "projet_members": _Resp(None),
            }
        )
        _, role = require_projet_access(supabase, "p1", "u1", "co_owner")  # type: ignore[arg-type]
        self.assertEqual(role, "co_owner")

    def test_non_membre_du_monument_renvoie_404(self) -> None:
        """Délégation : le 404 vient de `require_project_access`, pas du projet."""
        supabase = _FakeSupabase(
            {
                "projets": _Resp(PROJET),
                "project_members": _Resp(None),
                "monuments": _Resp(None),
            }
        )
        with self.assertRaises(HTTPException) as ctx:
            require_projet_access(supabase, "p1", "u2")  # type: ignore[arg-type]
        self.assertEqual(ctx.exception.status_code, 404)

    def test_proprietaire_sans_ligne_membre_garde_l_acces(self) -> None:
        """Défense en profondeur héritée de get_project_role."""
        supabase = _FakeSupabase(
            {
                "projets": _Resp(PROJET),
                "project_members": _Resp(None),
                "monuments": _Resp({"id": "m1"}),
            }
        )
        _, role = require_projet_access(supabase, "p1", "u1", "owner")  # type: ignore[arg-type]
        self.assertEqual(role, "owner")


if __name__ == "__main__":
    unittest.main()
