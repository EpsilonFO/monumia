"""Supprimer ou jeter un document détache ses références dans les checklists.

Sans ce détachement, la pièce reste « fournie » avec un fichier fantôme : le
front ne peut plus l'afficher (le document n'existe plus) et la rend
verrouillée — « Réservé » — sans plus aucune action possible.
"""

import unittest

from routers.documents import delete_document, trash_document


class _Resp:
    def __init__(self, data):
        self.data = data


class _Table:
    def __init__(self, db, name):
        self._db = db
        self._name = name
        self._filters: dict = {}
        self._contains = None
        self._update = None
        self._delete = False

    def select(self, *a, **k):
        return self

    def update(self, values, *a, **k):
        self._update = values
        return self

    def delete(self, *a, **k):
        self._delete = True
        return self

    def eq(self, field, value, *a, **k):
        self._filters[field] = value
        return self

    def contains(self, field, value, *a, **k):
        self._contains = (field, value)
        self._db.contains_values.append(value)
        return self

    def single(self):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        if self._delete:
            self._db.deletes.append((self._name, self._filters.get("id")))
            self._db.operations.append(f"delete:{self._name}")
            return _Resp(None)
        if self._update is not None:
            self._db.updates.setdefault(self._name, []).append(
                {"id": self._filters.get("id"), "values": self._update}
            )
            return _Resp([self._update])
        if self._name == "dossiers" and self._contains is not None:
            # La fidélité du filtre `checklist @> [{documentId: …}]` relève de
            # PostgREST ; le faux client renvoie la liste préparée par le test.
            return _Resp(self._db.dossiers_referencants)
        if self._name == "documents":
            return _Resp(self._db.doc)
        if self._name == "project_members":
            return _Resp({"role": self._db.role} if self._db.role else None)
        return _Resp(None)


class _StorageFile:
    def __init__(self, db):
        self._db = db

    def remove(self, paths):
        self._db.operations.append("storage.remove")


class _Storage:
    def __init__(self, db):
        self._db = db

    def from_(self, bucket):
        return _StorageFile(self._db)


class _Db:
    def __init__(self, *, doc, role="owner", dossiers_referencants=None):
        self.doc = doc
        self.role = role
        self.dossiers_referencants = dossiers_referencants or []
        self.updates: dict[str, list] = {}
        self.deletes: list = []
        # Journal ordonné des opérations sensibles : l'ordre stockage/ligne est
        # un invariant (cf. test_le_stockage_est_efface_en_dernier).
        self.operations: list[str] = []
        self.contains_values: list = []
        self.storage = _Storage(self)

    def table(self, name):
        return _Table(self, name)


def _doc(**over):
    base = {
        "id": "docA",
        "user_id": "u1",
        "url": "u1/f.pdf",
        "monument_ids": ["m1"],
        "dossiers_utilises": [],
    }
    base.update(over)
    return base


def _dossier_referencant():
    return {
        "id": "dz",
        "checklist": [
            {
                "id": "i1",
                "label": "RIB",
                "obligatoire": True,
                "statut": "fourni",
                "documentId": "docA",
                "pieceId": "rib",
            },
            {
                "id": "i2",
                "label": "Autre pièce",
                "obligatoire": True,
                "statut": "fourni",
                "documentId": "autre-doc",
            },
        ],
    }


class TrashDetacheChecklistsTests(unittest.TestCase):
    def test_jeter_detache_les_references(self) -> None:
        db = _Db(doc=_doc(), dossiers_referencants=[_dossier_referencant()])

        trash_document("docA", user_id="u1", supabase=db)

        maj = next(u for u in db.updates["dossiers"] if u["id"] == "dz")
        items = maj["values"]["checklist"]
        self.assertIsNone(items[0]["documentId"])
        self.assertEqual(items[0]["statut"], "manquant")
        # L'autre pièce, rattachée à un autre fichier, n'est pas touchée.
        self.assertEqual(items[1]["documentId"], "autre-doc")
        self.assertEqual(items[1]["statut"], "fourni")
        # La progression est recalculée : plus qu'une pièce fournie sur deux.
        self.assertEqual(maj["values"]["progression_pourcentage"], 50)

    def test_jeter_detache_aussi_une_piece_reprise(self) -> None:
        dossier = _dossier_referencant()
        dossier["checklist"][0].update({"statut": "repris", "origine": "repris", "perime": True})
        db = _Db(doc=_doc(), dossiers_referencants=[dossier])

        trash_document("docA", user_id="u1", supabase=db)

        item = db.updates["dossiers"][0]["values"]["checklist"][0]
        self.assertIsNone(item["documentId"])
        self.assertEqual(item["statut"], "manquant")
        self.assertNotIn("origine", item)
        self.assertNotIn("perime", item)

    def test_jeter_sans_reference_ne_touche_aucun_dossier(self) -> None:
        db = _Db(doc=_doc())

        trash_document("docA", user_id="u1", supabase=db)

        self.assertNotIn("dossiers", db.updates)


class DeleteDetacheChecklistsTests(unittest.TestCase):
    def test_supprimer_detache_les_references(self) -> None:
        db = _Db(doc=_doc(), dossiers_referencants=[_dossier_referencant()])

        delete_document("docA", user_id="u1", supabase=db)

        item = db.updates["dossiers"][0]["values"]["checklist"][0]
        self.assertIsNone(item["documentId"])
        self.assertEqual(item["statut"], "manquant")
        self.assertIn(("documents", "docA"), db.deletes)

    def test_le_filtre_contains_est_une_chaine_json(self) -> None:
        """postgrest-py sérialise une LISTE avec ','.join(...) — passer une liste
        de dicts lève TypeError et l'endpoint répond 500 (« failed to fetch »
        côté client). Le filtre jsonb doit partir en chaîne JSON. Les fakes ne
        peuvent pas attraper la sérialisation : ce test fige au moins la forme."""
        import json

        db = _Db(doc=_doc())

        trash_document("docA", user_id="u1", supabase=db)

        self.assertEqual(len(db.contains_values), 1)
        valeur = db.contains_values[0]
        self.assertIsInstance(valeur, str)
        self.assertEqual(json.loads(valeur), [{"documentId": "docA"}])

    def test_le_stockage_est_efface_en_dernier(self) -> None:
        """Le fichier de stockage ne doit disparaître qu'une fois la ligne
        supprimée : dans l'autre ordre, un échec à mi-chemin laisse une ligne
        vivante dont le fichier n'existe plus — aperçu mort, suppression qui
        re-échoue à chaque essai."""
        db = _Db(doc=_doc(), dossiers_referencants=[_dossier_referencant()])

        delete_document("docA", user_id="u1", supabase=db)

        self.assertIn("delete:documents", db.operations)
        self.assertIn("storage.remove", db.operations)
        self.assertLess(
            db.operations.index("delete:documents"),
            db.operations.index("storage.remove"),
        )


if __name__ == "__main__":
    unittest.main()
