"""Cloisonnement du partage : équipe du monument vs équipe d'un projet.

Ce fichier garde la frontière que tout le reste suppose : un collaborateur
invité sur UN chantier ne doit jamais voir les autres, ni les documents du
monument, ni son équipe — mais doit lire la fiche sanitaire du bien.
"""

import unittest

from fastapi import HTTPException

from routers.projet_sharing import _require_target_projet_member, create_invitation, list_members
from services.project_access import (
    best_document_role,
    max_role,
    projet_role_depuis,
    require_monument_read,
)


class _Resp:
    def __init__(self, data) -> None:
        self.data = data


class _FakeQuery:
    """Rend un DICT après maybe_single()/single(), une LISTE sinon."""

    def __init__(self, data) -> None:
        self._data = data
        self._single = False
        self._op = "select"
        self._row: dict | None = None

    def select(self, *_a, **_k) -> "_FakeQuery":
        return self

    def insert(self, row, *_a, **_k) -> "_FakeQuery":
        self._op = "insert"
        self._row = row
        return self

    def delete(self, *_a, **_k) -> "_FakeQuery":
        self._op = "delete"
        return self

    def eq(self, *_a, **_k) -> "_FakeQuery":
        return self

    def neq(self, *_a, **_k) -> "_FakeQuery":
        return self

    def in_(self, *_a, **_k) -> "_FakeQuery":
        return self

    def maybe_single(self) -> "_FakeQuery":
        self._single = True
        return self

    def single(self) -> "_FakeQuery":
        self._single = True
        return self

    def execute(self):
        if self._op == "insert":
            return _Resp([{**(self._row or {}), "id": "inv-1", "created_at": "2026-01-01"}])
        if self._op == "delete":
            return _Resp([])
        if self._single:
            return _Resp(
                self._data[0] if isinstance(self._data, list) and self._data else self._data
            )
        if self._data is None:
            return _Resp([])
        return _Resp(self._data if isinstance(self._data, list) else [self._data])


class _FakeSupabase:
    def __init__(self, tables: dict) -> None:
        self._tables = tables

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(self._tables.get(name))


PROJET = {"id": "p1", "monument_id": "m1", "user_id": "chef", "titre": "Toiture"}


class MaxRoleTests(unittest.TestCase):
    """La règle qui articule les deux appartenances : on ne restreint jamais."""

    def test_rend_le_plus_eleve(self) -> None:
        self.assertEqual(max_role("member", "co_owner"), "co_owner")
        self.assertEqual(max_role("co_owner", "member"), "co_owner")
        self.assertEqual(max_role("owner", "co_owner"), "owner")

    def test_none_est_absorbe(self) -> None:
        self.assertEqual(max_role(None, "member"), "member")
        self.assertEqual(max_role("member", None), "member")
        self.assertIsNone(max_role(None, None))


class ProjetRoleDepuisTests(unittest.TestCase):
    def test_appartenance_propre_seule(self) -> None:
        role = projet_role_depuis(PROJET, None, {"p1": "member"}, "u1")
        self.assertEqual(role, "member")

    def test_role_du_monument_seul(self) -> None:
        self.assertEqual(projet_role_depuis(PROJET, "co_owner", {}, "u1"), "co_owner")

    def test_le_monument_ne_degrade_pas_le_projet(self) -> None:
        self.assertEqual(projet_role_depuis(PROJET, "member", {"p1": "co_owner"}, "u1"), "co_owner")

    def test_le_projet_ne_degrade_pas_le_monument(self) -> None:
        self.assertEqual(projet_role_depuis(PROJET, "owner", {"p1": "member"}, "u1"), "owner")

    def test_le_createur_garde_co_owner(self) -> None:
        self.assertEqual(projet_role_depuis(PROJET, None, {}, "chef"), "co_owner")

    def test_etranger_n_a_aucun_role(self) -> None:
        self.assertIsNone(projet_role_depuis(PROJET, None, {}, "inconnu"))


class RequireMonumentReadTests(unittest.TestCase):
    """`None` n'est pas un refus ici : c'est l'accès restreint « fiche seule »."""

    def test_membre_du_monument_recoit_son_role(self) -> None:
        supabase = _FakeSupabase({"project_members": {"role": "co_owner"}})
        self.assertEqual(require_monument_read(supabase, "m1", "u1"), "co_owner")  # type: ignore[arg-type]

    def test_membre_d_un_projet_recoit_none(self) -> None:
        supabase = _FakeSupabase(
            {
                "project_members": None,
                "monuments": None,
                "projet_members": [{"projet_id": "p1"}],
                "projets": [{"id": "p1", "monument_id": "m1"}],
            }
        )
        self.assertIsNone(require_monument_read(supabase, "m1", "u1"))  # type: ignore[arg-type]

    def test_membre_d_un_projet_d_un_AUTRE_monument_est_refuse(self) -> None:
        supabase = _FakeSupabase(
            {
                "project_members": None,
                "monuments": None,
                "projet_members": [{"projet_id": "p9"}],
                "projets": [{"id": "p9", "monument_id": "m9"}],
            }
        )
        with self.assertRaises(HTTPException) as ctx:
            require_monument_read(supabase, "m1", "u1")  # type: ignore[arg-type]
        self.assertEqual(ctx.exception.status_code, 404)

    def test_etranger_est_refuse(self) -> None:
        supabase = _FakeSupabase({"project_members": None, "monuments": None, "projet_members": []})
        with self.assertRaises(HTTPException) as ctx:
            require_monument_read(supabase, "m1", "u1")  # type: ignore[arg-type]
        self.assertEqual(ctx.exception.status_code, 404)


class ListMembersTests(unittest.TestCase):
    def _supabase(self, herites, propres) -> _FakeSupabase:
        return _FakeSupabase(
            {
                "projets": PROJET,
                "project_members": herites,
                "projet_members": propres,
                "users": [],
                "project_invitations": [],
            }
        )

    def test_distingue_les_membres_herites_des_invites_du_projet(self) -> None:
        supabase = self._supabase(
            herites=[{"user_id": "chef", "role": "owner", "joined_at": "2026-01-01"}],
            propres=[{"user_id": "couvreur", "role": "member", "joined_at": "2026-02-01"}],
        )
        out = list_members(projet_id="p1", user_id="chef", supabase=supabase)  # type: ignore[arg-type]
        par_id = {m["user_id"]: m for m in out["members"]}
        self.assertEqual(par_id["chef"]["source"], "monument")
        self.assertEqual(par_id["couvreur"]["source"], "projet")

    def test_un_membre_present_des_deux_cotes_n_apparait_qu_une_fois(self) -> None:
        """Le droit hérité prime : il est plus large et non révocable ici."""
        supabase = self._supabase(
            herites=[{"user_id": "chef", "role": "owner", "joined_at": "2026-01-01"}],
            propres=[{"user_id": "chef", "role": "member", "joined_at": "2026-02-01"}],
        )
        out = list_members(projet_id="p1", user_id="chef", supabase=supabase)  # type: ignore[arg-type]
        self.assertEqual([m["user_id"] for m in out["members"]], ["chef"])
        self.assertEqual(out["members"][0]["source"], "monument")


class InviteGuardTests(unittest.TestCase):
    def test_refuse_un_membre_de_l_equipe_du_monument(self) -> None:
        """Il a déjà accès : la ligne serait trompeuse et n'ajouterait rien."""
        supabase = _FakeSupabase(
            {
                "projets": PROJET,
                "monuments": {"id": "m1", "nom": "Église Saint-Pierre"},
                "project_members": [{"user_id": "chef", "role": "owner"}],
                "projet_members": None,
                "users": {"id": "archi"},
            }
        )
        with self.assertRaises(HTTPException) as ctx:
            create_invitation(
                projet_id="p1",
                body=type("B", (), {"email": "archi@x.fr", "message": None})(),
                request=None,  # type: ignore[arg-type]
                user_id="chef",
                supabase=supabase,  # type: ignore[arg-type]
            )
        self.assertEqual(ctx.exception.status_code, 409)


class TargetMemberGuardTests(unittest.TestCase):
    def test_refuse_de_gerer_un_membre_herite(self) -> None:
        """Son droit vient du monument : le retirer d'ici ne le lui ôterait pas."""
        supabase = _FakeSupabase({"projet_members": None})
        with self.assertRaises(HTTPException) as ctx:
            _require_target_projet_member(supabase, "p1", "chef")  # type: ignore[arg-type]
        self.assertEqual(ctx.exception.status_code, 404)

    def test_accepte_un_membre_propre(self) -> None:
        supabase = _FakeSupabase({"projet_members": {"role": "member"}})
        self.assertEqual(
            _require_target_projet_member(supabase, "p1", "couvreur"),  # type: ignore[arg-type]
            "member",
        )


class CloisonnementDocumentsTests(unittest.TestCase):
    """Un membre projet-seulement ne doit rien voir des pièces du monument."""

    def test_ne_voit_pas_une_piece_du_monument(self) -> None:
        role = best_document_role(["m1"], [], {}, {"p1": "member"})
        self.assertIsNone(role)

    def test_voit_une_piece_de_son_projet(self) -> None:
        role = best_document_role([], ["p1"], {}, {"p1": "member"})
        self.assertEqual(role, "member")

    def test_ne_voit_pas_une_piece_d_un_autre_projet(self) -> None:
        self.assertIsNone(best_document_role([], ["p2"], {}, {"p1": "member"}))


if __name__ == "__main__":
    unittest.main()
