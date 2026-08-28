"""Test de l'endpoint d'URL signée serveur (consultation partagée des documents).

La signature passe par le service role pour contourner la RLS storage : tout
membre peut consulter, pas seulement l'auteur. Ici on couvre le câblage de
l'endpoint (auteur → URL renvoyée) ; le contrôle d'accès lui-même est couvert
par les tests de _require_document_read / get_project_role.
"""

import unittest

from fastapi import HTTPException

from routers.documents import get_document_signed_url


class _Resp:
    def __init__(self, data):
        self.data = data


class _Table:
    """Le vrai client rend un dict après single(), une liste sinon."""

    def __init__(self, row):
        self._row = row
        self._single = False

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
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
        if self._single:
            return _Resp(self._row)
        return _Resp([] if self._row is None else [self._row])


class _SignedFile:
    def __init__(self, raises=False):
        self._raises = raises

    def create_signed_url(self, path, expires_in):
        if self._raises:
            raise RuntimeError("storage down")
        return {"signedURL": f"https://x/storage/v1/object/sign/{path}?token=abc"}


class _Storage:
    def __init__(self, raises=False):
        self._raises = raises

    def from_(self, bucket):
        return _SignedFile(self._raises)


class _FakeSupabase:
    def __init__(self, row, raises=False):
        self._row = row
        self.storage = _Storage(raises)

    def table(self, name):
        # Seule la table `documents` est modélisée : les tables d'appartenance
        # répondent « rien », l'auteur du document suffisant à ces tests.
        return _Table(self._row if name == "documents" else None)


class GetDocumentSignedUrlTests(unittest.TestCase):
    def test_author_gets_signed_url(self):
        fake = _FakeSupabase(
            {"id": "d1", "user_id": "u1", "url": "u1/file.pdf", "monument_ids": []}
        )
        out = get_document_signed_url("d1", user_id="u1", supabase=fake)
        self.assertIn("signed_url", out)
        self.assertIn("u1/file.pdf", out["signed_url"])

    def test_rejects_full_url_path(self):
        fake = _FakeSupabase(
            {"id": "d1", "user_id": "u1", "url": "https://evil/x.pdf", "monument_ids": []}
        )
        with self.assertRaises(HTTPException) as ctx:
            get_document_signed_url("d1", user_id="u1", supabase=fake)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_storage_failure_returns_502(self):
        fake = _FakeSupabase(
            {"id": "d1", "user_id": "u1", "url": "u1/file.pdf", "monument_ids": []}, raises=True
        )
        with self.assertRaises(HTTPException) as ctx:
            get_document_signed_url("d1", user_id="u1", supabase=fake)
        self.assertEqual(ctx.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()
