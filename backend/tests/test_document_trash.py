"""Helpers purs de la corbeille + élargissement de la vue « Mes documents »."""

import unittest

from fastapi import HTTPException

from routers.documents import (
    _filter_visible,
    _should_auto_trash,
    delete_document,
    list_documents,
    remove_document_from_project,
    restore_document,
    trash_document,
    unlink_from_dossier,
)
from services.project_access import best_document_role


class ShouldAutoTrashTests(unittest.TestCase):
    def test_all_empty_trashes(self):
        self.assertTrue(_should_auto_trash([], [], []))
        self.assertTrue(_should_auto_trash(None, None, None))

    def test_any_link_keeps(self):
        self.assertFalse(_should_auto_trash(["m1"], [], []))
        self.assertFalse(_should_auto_trash([], ["p1"], []))
        self.assertFalse(_should_auto_trash([], [], ["d1"]))
        self.assertFalse(_should_auto_trash(["m1"], ["p1"], ["d1"]))


class BestDocumentRoleTests(unittest.TestCase):
    """Le rôle d'un viewer sur un document couvre ses deux rattachements."""

    MONUMENTS = {"m1": "member", "m2": "owner", "m3": "co_owner"}
    PROJETS = {"p1": "member", "p2": "co_owner"}

    def test_picks_highest_among_monuments(self):
        self.assertEqual(
            best_document_role(["m1", "m3"], [], self.MONUMENTS, self.PROJETS), "co_owner"
        )
        self.assertEqual(
            best_document_role(["m1", "m2"], [], self.MONUMENTS, self.PROJETS), "owner"
        )

    def test_un_projet_suffit_sans_acces_au_monument(self):
        # Le cas du collaborateur invité sur le seul chantier : il ne connaît
        # pas le monument, mais la pièce déposée sur son projet lui est visible.
        self.assertEqual(best_document_role([], ["p2"], {}, self.PROJETS), "co_owner")

    def test_retient_le_plus_eleve_des_deux_portees(self):
        self.assertEqual(
            best_document_role(["m1"], ["p2"], self.MONUMENTS, self.PROJETS), "co_owner"
        )
        self.assertEqual(best_document_role(["m2"], ["p1"], self.MONUMENTS, self.PROJETS), "owner")

    def test_none_when_no_membership(self):
        self.assertIsNone(best_document_role(["mX"], ["pX"], self.MONUMENTS, self.PROJETS))
        self.assertIsNone(best_document_role([], [], self.MONUMENTS, self.PROJETS))


class FilterVisibleTests(unittest.TestCase):
    def _row(self, **over):
        base = dict(
            id="d1",
            user_id="u2",
            monument_ids=["m1"],
            visibility="team",
            allowed_user_ids=[],
        )
        base.update(over)
        return base

    def test_uploader_sees_own_even_without_role(self):
        rows = [self._row(user_id="u1", monument_ids=[])]
        self.assertEqual(len(_filter_visible(rows, "u1", {}, {})), 1)

    def test_member_sees_team_not_responsables(self):
        roles = {"m1": "member"}
        team = self._row(visibility="team")
        resp = self._row(visibility="responsables")
        out = _filter_visible([team, resp], "u1", roles, {})
        self.assertEqual([r["visibility"] for r in out], ["team"])

    def test_non_member_excluded(self):
        rows = [self._row(visibility="team", monument_ids=["mX"])]
        self.assertEqual(_filter_visible(rows, "u1", {}, {}), [])

    def test_membre_du_projet_voit_une_piece_du_chantier(self):
        rows = [self._row(monument_ids=[], projet_ids=["p1"])]
        self.assertEqual(len(_filter_visible(rows, "u1", {}, {"p1": "member"})), 1)


# ---------------------------------------------------------------------------
# Fake Supabase pour les tests d'endpoints (Task 4)
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    """Chaînage fluent bouchonné.

    Le vrai client renvoie un DICT (ou None) après `maybe_single()` / `single()`,
    et une LISTE sinon. Le faux doit faire la même différence : plusieurs gardes
    lisent la même table dans les deux modes (rôle unitaire vs périmètre complet
    de l'utilisateur), et un faux qui rendrait toujours un dict les casserait.
    """

    @staticmethod
    def _coerce(data, single: bool):
        if single:
            return data
        if data is None:
            return []
        return data if isinstance(data, list) else [data]

    def __init__(self, response, updated):
        self._response = response
        self._updated = updated
        self._mode = None
        self._single = False

    def select(self, *a, **k):
        return self

    def update(self, row, *a, **k):
        self._updated.append(row)
        self._mode = "update"
        return self

    def eq(self, *a, **k):
        return self

    def contains(self, *a, **k):
        # Le balayage des checklists (détachement à la suppression) interroge
        # les dossiers par `contains` ; ces fakes n'en fournissent aucun → no-op.
        return self

    def in_(self, *a, **k):
        return self

    def single(self):
        self._single = True
        return self

    def maybe_single(self):
        self._single = True
        return self

    def execute(self):
        if self._mode == "update":
            return _Resp([{**self._updated[-1], "id": "d1"}])
        return _Resp(self._coerce(self._response.data, self._single))


class _FakeSupabase:
    def __init__(self, responses):
        self._responses = responses
        self.updated: list = []

    def table(self, name):
        return _Query(self._responses.get(name, _Resp(None)), self.updated)


def _fake(*, doc, caller_role="owner", dossier=None):
    return _FakeSupabase(
        {
            "documents": _Resp(doc),
            "project_members": _Resp(
                {"monument_id": "m1", "role": caller_role} if caller_role else None
            ),
            "monuments": _Resp(None),
            "dossiers": _Resp(dossier),
            "projets": _Resp({"id": "p1", "monument_id": "m1", "user_id": "u9"}),
            "projet_members": _Resp(None),
        }
    )


class TrashEndpointTests(unittest.TestCase):
    DOC = {"id": "d1", "user_id": "u1", "monument_ids": ["m1"], "dossiers_utilises": ["x"]}

    def test_trash_detaches_all_and_sets_flag(self):
        fake = _fake(doc=self.DOC, caller_role="member")  # uploader u1
        trash_document("d1", user_id="u1", supabase=fake)
        patch = fake.updated[0]
        self.assertEqual(patch["monument_ids"], [])
        self.assertEqual(patch["dossiers_utilises"], [])
        self.assertIsNotNone(patch["trashed_at"])

    def test_trash_forbidden_for_plain_member_non_uploader(self):
        doc = {**self.DOC, "user_id": "u2"}
        fake = _fake(doc=doc, caller_role="member")  # caller u1 != auteur
        with self.assertRaises(HTTPException) as ctx:
            trash_document("d1", user_id="u1", supabase=fake)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_restore_clears_flag_for_uploader(self):
        doc = {**self.DOC, "trashed_at": "2026-01-01T00:00:00Z"}
        fake = _fake(doc=doc, caller_role="member")
        restore_document("d1", user_id="u1", supabase=fake)
        self.assertIsNone(fake.updated[0]["trashed_at"])

    def test_restore_forbidden_for_non_uploader(self):
        doc = {**self.DOC, "user_id": "u2", "trashed_at": "2026-01-01T00:00:00Z"}
        fake = _fake(doc=doc, caller_role="owner")
        with self.assertRaises(HTTPException) as ctx:
            restore_document("d1", user_id="u1", supabase=fake)
        self.assertEqual(ctx.exception.status_code, 403)


class UnlinkAutoTrashTests(unittest.TestCase):
    def test_unlink_last_dossier_no_project_trashes(self):
        doc = {"id": "d1", "user_id": "u1", "monument_ids": [], "dossiers_utilises": ["dz"]}
        fake = _fake(
            doc=doc,
            caller_role="member",
            dossier={"id": "dz", "projet_id": "p1", "monument_id": "m1"},
        )
        unlink_from_dossier("d1", "dz", user_id="u1", supabase=fake)
        patch = fake.updated[0]
        self.assertEqual(patch["dossiers_utilises"], [])
        self.assertIsNotNone(patch["trashed_at"])

    def test_unlink_with_remaining_project_keeps(self):
        doc = {"id": "d1", "user_id": "u1", "monument_ids": ["m1"], "dossiers_utilises": ["dz"]}
        fake = _fake(
            doc=doc,
            caller_role="member",
            dossier={"id": "dz", "projet_id": "p1", "monument_id": "m1"},
        )
        unlink_from_dossier("d1", "dz", user_id="u1", supabase=fake)
        self.assertNotIn("trashed_at", fake.updated[0])


class RemoveFromProjectTests(unittest.TestCase):
    def test_remove_one_of_two_keeps(self):
        doc = {"id": "d1", "user_id": "u1", "monument_ids": ["m1", "m2"], "dossiers_utilises": []}
        fake = _fake(doc=doc, caller_role="owner")
        remove_document_from_project("d1", "m1", user_id="u1", supabase=fake)
        patch = fake.updated[0]
        self.assertEqual(patch["monument_ids"], ["m2"])
        self.assertNotIn("trashed_at", patch)

    def test_remove_last_project_trashes(self):
        doc = {"id": "d1", "user_id": "u1", "monument_ids": ["m1"], "dossiers_utilises": []}
        fake = _fake(doc=doc, caller_role="owner")
        remove_document_from_project("d1", "m1", user_id="u1", supabase=fake)
        patch = fake.updated[0]
        self.assertEqual(patch["monument_ids"], [])
        self.assertIsNotNone(patch["trashed_at"])

    def test_remove_forbidden_for_plain_member_non_uploader(self):
        doc = {"id": "d1", "user_id": "u2", "monument_ids": ["m1"], "dossiers_utilises": []}
        fake = _fake(doc=doc, caller_role="member")
        with self.assertRaises(HTTPException) as ctx:
            remove_document_from_project("d1", "m1", user_id="u1", supabase=fake)
        self.assertEqual(ctx.exception.status_code, 403)


class ModifyHiddenDocViewGateTests(unittest.TestCase):
    """Bug : un adjoint (co_owner) SANS accès à un document « personnes choisies »
    pouvait quand même le supprimer / déplacer / remplacer. Désormais : aucune
    action sans droit de consultation (côté serveur, défense en profondeur)."""

    # Doc custom dont u1 (le co_owner appelant) est exclu ; auteur = u2.
    HIDDEN = {
        "id": "d1",
        "user_id": "u2",
        "monument_ids": ["m1"],
        "dossiers_utilises": ["dz"],
        "visibility": "custom",
        "allowed_user_ids": ["u9"],
    }

    def test_delete_forbidden_for_co_owner_without_view(self):
        fake = _fake(doc=self.HIDDEN, caller_role="co_owner")
        with self.assertRaises(HTTPException) as ctx:
            delete_document("d1", user_id="u1", supabase=fake)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_trash_forbidden_for_co_owner_without_view(self):
        fake = _fake(doc=self.HIDDEN, caller_role="co_owner")
        with self.assertRaises(HTTPException) as ctx:
            trash_document("d1", user_id="u1", supabase=fake)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_remove_from_project_forbidden_for_co_owner_without_view(self):
        fake = _fake(doc=self.HIDDEN, caller_role="co_owner")
        with self.assertRaises(HTTPException) as ctx:
            remove_document_from_project("d1", "m1", user_id="u1", supabase=fake)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_unlink_forbidden_for_co_owner_without_view(self):
        fake = _fake(
            doc=self.HIDDEN,
            caller_role="co_owner",
            dossier={"id": "dz", "projet_id": "p1", "monument_id": "m1"},
        )
        with self.assertRaises(HTTPException) as ctx:
            unlink_from_dossier("d1", "dz", user_id="u1", supabase=fake)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_owner_still_acts_on_hidden_doc(self):
        # le chef de projet voit toujours tout → il garde la main (détache de m1).
        fake = _fake(doc=self.HIDDEN, caller_role="owner")
        remove_document_from_project("d1", "m1", user_id="u1", supabase=fake)
        self.assertEqual(fake.updated[0]["monument_ids"], [])


# ---------------------------------------------------------------------------
# Fake Supabase étendu pour list_documents (Fix 5 — tests d'endpoint)
# ---------------------------------------------------------------------------


class _NotProxy:
    """Proxy pour `supabase.table(...).not_.is_(col, val)` — retourne la query parente."""

    def __init__(self, query):
        self._query = query

    def is_(self, *a, **k):
        return self._query


class _ListQuery:
    """Fake query chaînable couvrant tous les appels de list_documents."""

    def __init__(self, response):
        self._response = response

    # Chainable stubs — tous retournent self
    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def contains(self, *a, **k):
        # Le balayage des checklists (détachement à la suppression) interroge
        # les dossiers par `contains` ; ces fakes n'en fournissent aucun → no-op.
        return self

    def order(self, *a, **k):
        return self

    def is_(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def or_(self, *a, **k):
        return self

    def maybe_single(self, *a, **k):
        return self

    @property
    def not_(self):
        return _NotProxy(self)

    def execute(self):
        return self._response


class _ListFakeSupabase:
    """Fake Supabase dont chaque table a une réponse fixe configurée à la construction."""

    def __init__(self, responses: dict):
        self._responses = responses

    def table(self, name: str):
        return _ListQuery(self._responses.get(name, _Resp([])))


class ListDocumentsTests(unittest.TestCase):
    # Un document « team » (visible par les membres) et un « responsables » (owner/co_owner seulement).
    TEAM_DOC = {
        "id": "doc-team",
        "user_id": "u99",
        "monument_ids": ["m1"],
        "visibility": "team",
        "allowed_user_ids": [],
        "dossiers_utilises": [],
    }
    RESP_DOC = {
        "id": "doc-resp",
        "user_id": "u99",
        "monument_ids": ["m1"],
        "visibility": "responsables",
        "allowed_user_ids": [],
        "dossiers_utilises": [],
    }
    TRASHED_DOC = {
        "id": "doc-trash",
        "user_id": "u1",
        "monument_ids": [],
        "visibility": "team",
        "allowed_user_ids": [],
        "dossiers_utilises": [],
        "trashed_at": "2026-01-01T00:00:00Z",
    }

    def _make_fake(self, docs, pm_data, monuments_data=None):
        """Construit un _ListFakeSupabase avec les réponses voulues."""
        return _ListFakeSupabase(
            {
                "documents": _Resp(docs),
                "project_members": _Resp(pm_data),
                "monuments": _Resp(monuments_data or []),
            }
        )

    def test_trashed_returns_caller_trashed_docs(self):
        """trashed=True → retourne les documents dans la corbeille de l'appelant."""
        fake = self._make_fake(
            docs=[self.TRASHED_DOC],
            pm_data=[{"monument_id": "m1", "role": "member"}],
        )
        result = list_documents(
            monument_id=None, projet_id=None, type=None, trashed=True, user_id="u1", supabase=fake
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "doc-trash")

    def test_non_trashed_member_sees_team_not_responsables(self):
        """trashed=False + rôle member → doc team inclus, doc responsables exclu."""
        # project_members renvoie une liste (itérée par my_scope_roles)
        fake = self._make_fake(
            docs=[self.TEAM_DOC, self.RESP_DOC],
            pm_data=[{"monument_id": "m1", "role": "member"}],
            monuments_data=[],  # pas owner de monument
        )
        result = list_documents(
            monument_id=None, projet_id=None, type=None, trashed=False, user_id="u1", supabase=fake
        )
        ids = [r["id"] for r in result]
        self.assertIn("doc-team", ids)
        self.assertNotIn("doc-resp", ids)
