"""Test du contrôle d'accès de la suppression de document (projets partagés).

La suppression doit suivre la même règle que `can_delete_document` :
- l'auteur peut toujours supprimer SON document ;
- un owner / co_owner peut supprimer N'IMPORTE quel document du projet ;
- un simple membre ne peut PAS supprimer le document d'un autre.

(La consultation reste ouverte à tout membre — couverte ailleurs.)
"""

import unittest

from fastapi import HTTPException

from routers.documents import delete_document


class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    """Mime le chaînage fluent supabase-py ; renvoie une réponse fixe."""

    def __init__(self, response, deleted):
        self._response = response
        self._deleted = deleted

    def select(self, *a, **k):
        return self

    def delete(self, *a, **k):
        self._deleted.append(True)
        return self

    def eq(self, *a, **k):
        return self

    def contains(self, *a, **k):
        # Le balayage des checklists (détachement à la suppression) interroge les
        # dossiers par `contains` ; ces fakes n'en fournissent aucun → no-op.
        return self

    def single(self):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        return self._response


class _StorageFile:
    def __init__(self):
        self.removed = []

    def remove(self, paths):
        self.removed.append(paths)


class _Storage:
    def __init__(self, file):
        self._file = file

    def from_(self, bucket):
        return self._file


class _FakeSupabase:
    def __init__(self, responses_by_table):
        self._responses = responses_by_table
        self.deleted = []
        self.storage_file = _StorageFile()
        self.storage = _Storage(self.storage_file)

    def table(self, name):
        return _Query(self._responses.get(name, _Resp(None)), self.deleted)


def _supabase(doc, *, caller_role):
    return _FakeSupabase(
        {
            "documents": _Resp(doc),
            "project_members": _Resp({"role": caller_role} if caller_role else None),
            "monuments": _Resp(None),
        }
    )


DOC_BY_OTHER = {
    "id": "d1",
    "user_id": "u2",  # déposé par quelqu'un d'autre
    "url": "u2/file.pdf",
    "monument_ids": ["m1"],
}


class DeleteDocumentAccessTests(unittest.TestCase):
    def test_co_owner_can_delete_others_document(self):
        fake = _supabase(DOC_BY_OTHER, caller_role="co_owner")
        delete_document("d1", user_id="u1", supabase=fake)
        self.assertTrue(fake.deleted, "le document aurait dû être supprimé")
        # Le fichier de stockage est rangé sous l'auteur (u2), pas l'appelant.
        self.assertIn(["u2/file.pdf"], fake.storage_file.removed)

    def test_owner_can_delete_others_document(self):
        fake = _supabase(DOC_BY_OTHER, caller_role="owner")
        delete_document("d1", user_id="u1", supabase=fake)
        self.assertTrue(fake.deleted)

    def test_member_cannot_delete_others_document(self):
        fake = _supabase(DOC_BY_OTHER, caller_role="member")
        with self.assertRaises(HTTPException) as ctx:
            delete_document("d1", user_id="u1", supabase=fake)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertFalse(fake.deleted)

    def test_uploader_member_can_delete_own_document(self):
        own = {**DOC_BY_OTHER, "user_id": "u1", "url": "u1/file.pdf"}
        fake = _supabase(own, caller_role="member")
        delete_document("d1", user_id="u1", supabase=fake)
        self.assertTrue(fake.deleted)


if __name__ == "__main__":
    unittest.main()
