"""Endpoint de reprise des pièces et détachement d'un document."""

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from routers.dossiers import UpdateChecklistItemRequest, update_checklist_item


class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, store, table):
        self._store = store
        self._table = table
        self._update = None

    def select(self, *a, **k):
        return self

    def update(self, values, *a, **k):
        self._update = values
        return self

    def eq(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def is_(self, *a, **k):
        return self

    def or_(self, *a, **k):
        return self

    def single(self):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        if self._update is not None:
            self._store.updates.setdefault(self._table, []).append(self._update)
            return _Resp([self._store.rows.get(self._table)])
        return _Resp(self._store.rows.get(self._table))


class _FakeSupabase:
    def __init__(self, rows):
        self.rows = rows
        self.updates: dict[str, list] = {}

    def table(self, name):
        return _Query(self, name)


_DOSSIER = {
    "id": "d1",
    "monument_id": "p1",
    "user_id": "u1",
    "checklist": [
        {
            "id": "i1",
            "label": "RIB",
            "description": "",
            "obligatoire": True,
            "categorie": "document",
            "ordre": 1,
            "statut": "manquant",
            "pieceId": "rib",
        }
    ],
}


class ReprendrePiecesTests(unittest.TestCase):
    def test_endpoint_applique_la_reprise(self) -> None:
        from routers.dossiers import reprendre_pieces

        supabase = _FakeSupabase({"dossiers": _DOSSIER})

        reprise = [{**_DOSSIER["checklist"][0], "statut": "repris", "documentId": "doc1"}]
        with (
            patch("routers.dossiers.require_project_access", return_value=None),
            patch("routers.dossiers.apply_reuse", return_value=(reprise, 1)) as faux,
        ):
            reprendre_pieces("d1", user_id="u1", supabase=supabase)

        faux.assert_called_once()
        ecrit = supabase.updates["dossiers"][0]
        self.assertEqual(ecrit["checklist"][0]["statut"], "repris")
        # Un item « repris » ne compte pas dans la progression.
        self.assertEqual(ecrit["progression_pourcentage"], 0)


class DetachementSchemaTests(unittest.TestCase):
    def test_detacher_absent_par_defaut(self) -> None:
        body = UpdateChecklistItemRequest(statut="fourni", document_id="doc1")
        self.assertFalse(body.detacher)


# ---------------------------------------------------------------------------
# Faux client supabase pour `update_checklist_item` : contrairement au faux
# client ci-dessus (une seule ligne fixe par table), celui-ci adresse les
# lignes par id (documents, dossiers) ou par monument (project_members), pour
# pouvoir distinguer le document déjà attaché du document qu'on tente de
# rattacher, et simuler un appelant membre d'un projet mais pas d'un autre.
# ---------------------------------------------------------------------------


class _Table:
    def __init__(self, db, name):
        self._db = db
        self._name = name
        self._filters: dict[str, str] = {}
        self._update_values = None

    def select(self, *a, **k):
        return self

    def update(self, values, *a, **k):
        self._update_values = values
        return self

    def eq(self, field, value, *a, **k):
        self._filters[field] = value
        return self

    def in_(self, *a, **k):
        return self

    def is_(self, *a, **k):
        return self

    def or_(self, *a, **k):
        return self

    def single(self):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        if self._update_values is not None:
            self._db.updates.setdefault(self._name, []).append(
                {"id": self._filters.get("id"), "values": self._update_values}
            )
            return _Resp(None)
        return _Resp(self._db.lookup(self._name, self._filters))


class _Db:
    """dossier : une seule ligne. documents : par id. project_members : par
    monument (une seule ligne « le rôle de l'appelant sur ce monument »)."""

    def __init__(self, *, dossier, documents=None, roles=None):
        self.dossier = dossier
        self.documents = documents or {}
        self.roles = roles or {}
        self.updates: dict[str, list] = {}

    def table(self, name):
        return _Table(self, name)

    def lookup(self, table, filters):
        if table == "dossiers":
            return self.dossier if filters.get("id") == self.dossier["id"] else None
        if table == "documents":
            return self.documents.get(filters.get("id"))
        if table == "project_members":
            role = self.roles.get(filters.get("monument_id"))
            return {"role": role} if role else None
        return None  # "monuments" (repli de get_project_role) : jamais utilisé ici


def _dossier(item: dict) -> dict:
    return {"id": "d1", "monument_id": "mon-1", "checklist": [item]}


class DetachementTests(unittest.TestCase):
    def test_detacher_vide_le_document_et_purge_les_marqueurs(self) -> None:
        item = {
            "id": "i1",
            "statut": "repris",
            "documentId": "docA",
            "origine": "repris",
            "perime": False,
            "pieceId": "rib",
        }
        db = _Db(
            dossier=_dossier(item),
            documents={"docA": {"user_id": "u1"}},  # l'appelant est l'auteur
            roles={"mon-1": "member"},
        )
        body = UpdateChecklistItemRequest(statut="manquant", detacher=True)

        update_checklist_item("d1", "i1", body, user_id="u1", supabase=db)

        ecrit = db.updates["dossiers"][0]["values"]["checklist"][0]
        self.assertIsNone(ecrit["documentId"])
        self.assertNotIn("origine", ecrit)
        self.assertNotIn("perime", ecrit)
        self.assertNotIn("documents", db.updates)  # pas de réécriture de piece_id


class ConfirmationRepriseTests(unittest.TestCase):
    """Confirmer une pièce reprise n'est pas un remplacement : la garde
    auteur/chef-de-projet ne doit pas s'appliquer, sinon le bouton de
    confirmation échouerait dès que le document a été repris chez un tiers."""

    def _item(self) -> dict:
        return {
            "id": "i1",
            "statut": "repris",
            "documentId": "docA",
            "origine": "repris",
            "perime": False,
            "pieceId": "rib",
        }

    def test_membre_non_auteur_peut_confirmer(self) -> None:
        db = _Db(
            dossier=_dossier(self._item()),
            documents={"docA": {"user_id": "u2"}},  # document d'un tiers
            roles={"mon-1": "member"},
        )
        body = UpdateChecklistItemRequest(statut="fourni")  # ni document_id, ni detacher

        update_checklist_item("d1", "i1", body, user_id="u1", supabase=db)

        ecrit = db.updates["dossiers"][0]["values"]["checklist"][0]
        self.assertEqual(ecrit["statut"], "fourni")
        self.assertEqual(ecrit["documentId"], "docA")  # document conservé
        self.assertNotIn("origine", ecrit)
        self.assertNotIn("perime", ecrit)

    def test_membre_non_auteur_ne_peut_toujours_pas_rejeter(self) -> None:
        # Le rejet retire bien le document : la garde s'applique, contrairement
        # à la confirmation.
        db = _Db(
            dossier=_dossier(self._item()),
            documents={"docA": {"user_id": "u2"}},
            roles={"mon-1": "member"},
        )
        body = UpdateChecklistItemRequest(statut="manquant", detacher=True)

        with self.assertRaises(HTTPException) as ctx:
            update_checklist_item("d1", "i1", body, user_id="u1", supabase=db)
        self.assertEqual(ctx.exception.status_code, 403)


class EstampillageTests(unittest.TestCase):
    def test_rattacher_un_document_visible_estampille_piece_id(self) -> None:
        item = {"id": "i1", "statut": "manquant", "pieceId": "rib"}
        db = _Db(
            dossier=_dossier(item),
            documents={
                "docNew": {
                    "user_id": "u2",
                    "visibility": "team",
                    "allowed_user_ids": [],
                    "monument_ids": ["mon-1"],
                }
            },
            roles={"mon-1": "member"},
        )
        body = UpdateChecklistItemRequest(statut="fourni", document_id="docNew")

        update_checklist_item("d1", "i1", body, user_id="u1", supabase=db)

        estampille = db.updates["documents"][0]
        self.assertEqual(estampille["id"], "docNew")
        self.assertEqual(estampille["values"], {"piece_id": "rib"})

    def test_pas_destampillage_sans_pieceid(self) -> None:
        item = {"id": "i1", "statut": "manquant"}  # pas de pieceId
        db = _Db(dossier=_dossier(item), documents={}, roles={"mon-1": "member"})
        body = UpdateChecklistItemRequest(statut="fourni", document_id="doc-libre")

        update_checklist_item("d1", "i1", body, user_id="u1", supabase=db)

        self.assertNotIn("documents", db.updates)
        ecrit = db.updates["dossiers"][0]["values"]["checklist"][0]
        self.assertEqual(ecrit["documentId"], "doc-libre")

    def test_document_non_visible_est_refuse(self) -> None:
        # Document d'un tiers, dans un projet dont l'appelant n'est pas membre :
        # sans le contrôle, il serait pourtant estampillé (stock empoisonné).
        item = {"id": "i1", "statut": "manquant", "pieceId": "rib"}
        db = _Db(
            dossier=_dossier(item),
            documents={
                "docForeign": {
                    "user_id": "u2",
                    "visibility": "custom",
                    "allowed_user_ids": [],
                    "monument_ids": ["autre-mon"],
                }
            },
            roles={"mon-1": "member"},  # rien sur "autre-mon"
        )
        body = UpdateChecklistItemRequest(statut="fourni", document_id="docForeign")

        with self.assertRaises(HTTPException) as ctx:
            update_checklist_item("d1", "i1", body, user_id="u1", supabase=db)

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertNotIn("documents", db.updates)
        self.assertNotIn("dossiers", db.updates)


if __name__ == "__main__":
    unittest.main()
