"""Zip des pièces d'un dossier : contenu, ordre, et respect de la visibilité.

L'endpoint agrège les documents déjà téléversés dans la checklist. Les pièces
que l'appelant n'a pas le droit de consulter sont omises du zip (cadenas
« Réservé » côté front) — c'est le point sensible couvert ici.
"""

import io
import unittest
import zipfile

from fastapi import HTTPException

from routers.dossiers import download_dossier_archive


class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, rows_by_id, table):
        self._rows = rows_by_id
        self._table = table
        self._id = None

    def select(self, *a, **k):
        return self

    def eq(self, col, value):
        if col == "id":
            self._id = value
        return self

    def single(self):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        return _Resp(self._rows.get(self._id))


class _FakeStorageFile:
    def __init__(self, blobs):
        self._blobs = blobs

    def download(self, path):
        if path not in self._blobs:
            raise RuntimeError("not found")
        return self._blobs[path]


class _FakeStorage:
    def __init__(self, blobs):
        self._blobs = blobs

    def from_(self, bucket):
        return _FakeStorageFile(self._blobs)


class _FakeSupabase:
    def __init__(self, dossiers, documents, blobs):
        self._tables = {"dossiers": dossiers, "documents": documents}
        self.storage = _FakeStorage(blobs)

    def table(self, name):
        return _Query(self._tables.get(name, {}), name)


DOSSIER = {
    "id": "d1",
    "monument_id": "m1",
    "titre": "DRAC — Église Saint-Pierre",
    "checklist": [
        {"id": "c2", "ordre": 2, "label": "Devis détaillé", "documentId": "doc2"},
        {"id": "c1", "ordre": 1, "label": "Plan de financement", "documentId": "doc1"},
        {"id": "c3", "ordre": 3, "label": "Pièce non fournie"},
    ],
}

DOCUMENTS = {
    "doc1": {
        "id": "doc1",
        "nom": "Plan",
        "nom_fichier": "plan.pdf",
        "url": "u1/plan.pdf",
        "user_id": "u1",
        "monument_ids": ["m1"],
        "visibility": "team",
        "allowed_user_ids": [],
    },
    "doc2": {
        "id": "doc2",
        "nom": "Devis",
        "nom_fichier": "devis.xlsx",
        "url": "u1/devis.xlsx",
        "user_id": "u1",
        "monument_ids": ["m1"],
        "visibility": "responsables",
        "allowed_user_ids": [],
    },
}

BLOBS = {"u1/plan.pdf": b"%PDF-1.4 plan", "u1/devis.xlsx": b"PK devis"}


def _patch_access(testcase, role):
    """Neutralise les appels base de require_project_access / get_project_role."""
    import routers.dossiers as mod

    testcase.addCleanup(setattr, mod, "require_project_access", mod.require_project_access)
    testcase.addCleanup(setattr, mod, "get_project_role", mod.get_project_role)
    mod.require_project_access = lambda *a, **k: None
    mod.get_project_role = lambda *a, **k: role


class TestDossierArchive(unittest.TestCase):
    def _run(self, user_id, role):
        _patch_access(self, role)
        supabase = _FakeSupabase({"d1": DOSSIER}, DOCUMENTS, BLOBS)
        return download_dossier_archive("d1", user_id=user_id, supabase=supabase)

    def test_zip_contient_les_pieces_dans_l_ordre(self):
        res = self._run("u1", "owner")
        self.assertEqual(res.media_type, "application/zip")
        self.assertIn("attachment", res.headers["content-disposition"])
        with zipfile.ZipFile(io.BytesIO(res.body)) as zf:
            names = zf.namelist()
            self.assertEqual(names, ["01 - Plan de financement.pdf", "02 - Devis detaille.xlsx"])
            self.assertEqual(zf.read(names[0]), b"%PDF-1.4 plan")

    def test_piece_non_consultable_omise(self):
        # Membre simple : 'responsables' lui est masqué, 'team' reste visible.
        res = self._run("u9", "member")
        with zipfile.ZipFile(io.BytesIO(res.body)) as zf:
            self.assertEqual(zf.namelist(), ["01 - Plan de financement.pdf"])

    def test_404_si_aucune_piece_lisible(self):
        _patch_access(self, "member")
        dossier = {**DOSSIER, "checklist": [{"id": "c1", "ordre": 1, "label": "X"}]}
        supabase = _FakeSupabase({"d1": dossier}, DOCUMENTS, BLOBS)
        with self.assertRaises(HTTPException) as ctx:
            download_dossier_archive("d1", user_id="u9", supabase=supabase)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_fichier_manquant_en_storage_ignore(self):
        _patch_access(self, "owner")
        supabase = _FakeSupabase({"d1": DOSSIER}, DOCUMENTS, {"u1/plan.pdf": b"pdf"})
        res = download_dossier_archive("d1", user_id="u1", supabase=supabase)
        with zipfile.ZipFile(io.BytesIO(res.body)) as zf:
            self.assertEqual(zf.namelist(), ["01 - Plan de financement.pdf"])


if __name__ == "__main__":
    unittest.main()
