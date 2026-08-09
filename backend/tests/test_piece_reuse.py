"""Reprise des pièces déjà déposées dans un nouveau dossier.

Le faux client Supabase renvoie une liste de documents fixe : ces tests portent
sur la SÉLECTION et le MARQUAGE, pas sur le SQL.
"""

import unittest
from datetime import UTC, datetime

from services.piece_reuse import age_mois, apply_reuse, choisir_document

_NOW = datetime(2026, 8, 9, tzinfo=UTC)


class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, data):
        self._data = data

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def or_(self, *a, **k):
        return self

    def is_(self, *a, **k):
        return self

    def execute(self):
        return _Resp(self._data)


class _FakeSupabase:
    """documents → le stock ; project_members / monuments → les rôles."""

    def __init__(self, documents, members=(), owned=()):
        self._tables = {
            "documents": list(documents),
            "project_members": list(members),
            "monuments": list(owned),
        }

    def table(self, name):
        return _Query(self._tables.get(name, []))


def _doc(doc_id, piece_id, **kw):
    base = {
        "id": doc_id,
        "piece_id": piece_id,
        "user_id": "u1",
        "monument_ids": ["p1"],
        "visibility": "team",
        "allowed_user_ids": [],
        "date_upload": "2026-08-01T00:00:00+00:00",
        "date_document": None,
        "trashed_at": None,
    }
    return {**base, **kw}


def _item(item_id, piece_id, statut="manquant"):
    return {
        "id": item_id,
        "label": "Pièce",
        "description": "",
        "obligatoire": True,
        "categorie": "document",
        "ordre": 1,
        "statut": statut,
        "pieceId": piece_id,
    }


def _reprendre(checklist, documents, *, user_id="u1", members=(), owned=("p1",)):
    supabase = _FakeSupabase(
        documents,
        members=members,
        owned=[{"id": m} for m in owned],
    )
    return apply_reuse(supabase, checklist, "p1", user_id, now=_NOW)


class PorteeTests(unittest.TestCase):
    def test_piece_porteur_reprise(self) -> None:
        items, n = _reprendre([_item("i1", "rib")], [_doc("d1", "rib")])
        self.assertEqual(n, 1)
        self.assertEqual(items[0]["statut"], "repris")
        self.assertEqual(items[0]["documentId"], "d1")
        self.assertEqual(items[0]["origine"], "repris")

    def test_piece_monument_reprise_dans_le_projet(self) -> None:
        items, n = _reprendre([_item("i1", "titre_propriete")], [_doc("d1", "titre_propriete")])
        self.assertEqual(n, 1)
        self.assertEqual(items[0]["documentId"], "d1")

    def test_piece_monument_hors_projet_non_reprise(self) -> None:
        """Une pièce `monument` rattachée à un AUTRE projet ne doit pas être reprise."""
        doc = _doc("d1", "titre_propriete", monument_ids=["p2"])
        items, n = _reprendre([_item("i1", "titre_propriete")], [doc])
        self.assertEqual(n, 0)
        self.assertEqual(items[0]["statut"], "manquant")

    def test_piece_porteur_dun_autre_non_reprise(self) -> None:
        """Une pièce `porteur` visible (équipe) mais déposée par un tiers ne doit
        jamais être rattachée à ma place : `porteur` est propre au demandeur."""
        doc = _doc("d1", "rib", user_id="u2", monument_ids=["p1"], visibility="team")
        items, n = _reprendre(
            [_item("i1", "rib")],
            [doc],
            user_id="u1",
            members=[{"monument_id": "p1", "role": "member"}],
            owned=(),
        )
        self.assertEqual(n, 0)
        self.assertEqual(items[0]["statut"], "manquant")

    def test_piece_porteur_reprise_hors_projet(self) -> None:
        """C'est tout l'intérêt de `porteur` : mon propre RIB compte même s'il
        n'est rattaché à aucun projet."""
        doc = _doc("d1", "rib", monument_ids=[])
        items, n = _reprendre([_item("i1", "rib")], [doc])
        self.assertEqual(n, 1)
        self.assertEqual(items[0]["documentId"], "d1")

    def test_piece_operation_jamais_reprise(self) -> None:
        items, n = _reprendre([_item("i1", "devis_travaux")], [_doc("d1", "devis_travaux")])
        self.assertEqual(n, 0)
        self.assertEqual(items[0]["statut"], "manquant")
        self.assertNotIn("documentId", items[0])

    def test_item_sans_piece_id_inchange(self) -> None:
        items, n = _reprendre([_item("i1", None)], [_doc("d1", "rib")])
        self.assertEqual(n, 0)
        self.assertEqual(items[0]["statut"], "manquant")

    def test_piece_id_hors_referentiel_ignore(self) -> None:
        items, n = _reprendre([_item("i1", "piece_fantome")], [_doc("d1", "piece_fantome")])
        self.assertEqual(n, 0)


class VisibiliteTests(unittest.TestCase):
    def test_document_responsables_non_repris_pour_un_membre(self) -> None:
        """Le test qui compte : la reprise ne contourne pas la visibilité."""
        doc = _doc("d1", "titre_propriete", user_id="u2", visibility="responsables")
        items, n = _reprendre(
            [_item("i1", "titre_propriete")],
            [doc],
            user_id="u1",
            members=[{"monument_id": "p1", "role": "member"}],
            owned=(),
        )
        self.assertEqual(n, 0)
        self.assertEqual(items[0]["statut"], "manquant")

    def test_document_responsables_repris_pour_un_co_owner(self) -> None:
        doc = _doc("d1", "titre_propriete", user_id="u2", visibility="responsables")
        items, n = _reprendre(
            [_item("i1", "titre_propriete")],
            [doc],
            user_id="u1",
            members=[{"monument_id": "p1", "role": "co_owner"}],
            owned=(),
        )
        self.assertEqual(n, 1)


class PeremptionTests(unittest.TestCase):
    def test_piece_perissable_recente_non_marquee(self) -> None:
        doc = _doc("d1", "bilan_dernier_exercice", date_document="2026-03-01T00:00:00+00:00")
        items, _ = _reprendre([_item("i1", "bilan_dernier_exercice")], [doc])
        self.assertFalse(items[0]["perime"])

    def test_piece_perissable_ancienne_marquee(self) -> None:
        doc = _doc("d1", "bilan_dernier_exercice", date_document="2024-01-01T00:00:00+00:00")
        items, n = _reprendre([_item("i1", "bilan_dernier_exercice")], [doc])
        self.assertEqual(n, 1)
        self.assertTrue(items[0]["perime"])

    def test_piece_non_perissable_jamais_marquee(self) -> None:
        doc = _doc("d1", "rib", date_document="2019-01-01T00:00:00+00:00")
        items, _ = _reprendre([_item("i1", "rib")], [doc])
        self.assertFalse(items[0]["perime"])

    def test_date_document_prime_sur_date_upload(self) -> None:
        doc = _doc(
            "d1",
            "bilan_dernier_exercice",
            date_document="2024-01-01T00:00:00+00:00",
            date_upload="2026-08-01T00:00:00+00:00",
        )
        items, _ = _reprendre([_item("i1", "bilan_dernier_exercice")], [doc])
        self.assertTrue(items[0]["perime"])


class SelectionTests(unittest.TestCase):
    def test_le_plus_recent_gagne(self) -> None:
        vieux = _doc("d1", "rib", date_upload="2025-01-01T00:00:00+00:00")
        recent = _doc("d2", "rib", date_upload="2026-07-01T00:00:00+00:00")
        items, _ = _reprendre([_item("i1", "rib")], [vieux, recent])
        self.assertEqual(items[0]["documentId"], "d2")

    def test_document_en_corbeille_exclu(self) -> None:
        corbeille = _doc("d1", "rib", trashed_at="2026-07-01T00:00:00+00:00")
        items, n = _reprendre([_item("i1", "rib")], [corbeille])
        self.assertEqual(n, 0)

    def test_choisir_document_sur_liste_vide(self) -> None:
        self.assertIsNone(choisir_document([]))


class NonEcrasementTests(unittest.TestCase):
    def test_item_deja_fourni_non_ecrase(self) -> None:
        item = _item("i1", "rib", statut="fourni")
        item["documentId"] = "deja"
        items, n = _reprendre([item], [_doc("d1", "rib")])
        self.assertEqual(n, 0)
        self.assertEqual(items[0]["documentId"], "deja")

    def test_item_en_attente_non_ecrase(self) -> None:
        items, n = _reprendre([_item("i1", "rib", statut="en_attente")], [_doc("d1", "rib")])
        self.assertEqual(n, 0)

    def test_idempotence(self) -> None:
        premier, n1 = _reprendre([_item("i1", "rib")], [_doc("d1", "rib")])
        second, n2 = _reprendre(premier, [_doc("d1", "rib")])
        self.assertEqual((n1, n2), (1, 0))
        self.assertEqual(premier, second)

    def test_checklist_source_non_mutee(self) -> None:
        source = [_item("i1", "rib")]
        _reprendre(source, [_doc("d1", "rib")])
        self.assertEqual(source[0]["statut"], "manquant")


class AgeMoisTests(unittest.TestCase):
    def test_age_en_mois(self) -> None:
        self.assertEqual(age_mois("2025-08-09T00:00:00+00:00", _NOW), 12)

    def test_date_absente(self) -> None:
        self.assertIsNone(age_mois(None, _NOW))

    def test_date_illisible(self) -> None:
        self.assertIsNone(age_mois("pas une date", _NOW))


if __name__ == "__main__":
    unittest.main()
