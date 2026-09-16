"""Une date de protection vide n'est pas une date : elle doit valoir NULL.

Le formulaire envoie `""` pour « pas de date ». C'est ce qu'il fait dès qu'on
choisit « non protégé », qui vide date et détail de protection — donc le cas
courant d'un monument ABSENT de Mérimée, saisi à la main. PostgreSQL refuse la
chaîne vide sur une colonne `date` et l'erreur PostgREST remontait en 500 à la
dernière étape du wizard (« Terminer »), et de nouveau au rejeu du brouillon
après l'inscription d'un visiteur.

Ce qui est figé ici :

  * la création insère `date_protection: None`, jamais `""` ;
  * le PATCH qui efface une date écrit bien NULL — la clé reste dans l'update,
    sinon l'ancienne valeur survivrait et la date serait ineffaçable ;
  * une date mal formée est un 400 (faute du client), pas un 500.
"""

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from routers.monuments import (
    CreateMonumentRequest,
    UpdateMonumentRequest,
    create_monument,
    update_monument,
)


class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    """Chaînage fluent minimal : lectures sur des lignes fixes, écritures
    journalisées dans `writes`."""

    def __init__(self, table, rows, writes):
        self._table = table
        self._rows = rows
        self._writes = writes
        self._op = "select"
        self._payload = None
        self._single = False

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def single(self):
        self._single = True
        return self

    def maybe_single(self):
        self._single = True
        return self

    def insert(self, payload, *a, **k):
        self._op, self._payload = "insert", payload
        return self

    def update(self, payload, *a, **k):
        self._op, self._payload = "update", payload
        return self

    def execute(self):
        if self._op == "select":
            if self._single:
                return _Resp(self._rows[0] if self._rows else None)
            return _Resp(list(self._rows))
        self._writes.append((self._table, self._op, self._payload))
        ligne = {"id": "monument-1", **self._payload}
        return _Resp([ligne])


class _FakeSupabase:
    def __init__(self, tables=None):
        self.tables = tables or {}
        self.writes: list = []

    def table(self, name):
        rows = self.tables.setdefault(name, [])
        return _Query(name, rows, self.writes)

    def ecritures(self, table: str, op: str) -> list[dict]:
        return [p for t, o, p in self.writes if t == table and o == op]


def _base() -> _FakeSupabase:
    return _FakeSupabase({"communes": [{"code_insee": "35238", "nom_commune": "Rennes"}]})


def _corps_create(**extra) -> CreateMonumentRequest:
    champs = {
        "nom": "Manoir sans notice",
        "commune": "Rennes",
        "codeInsee": "35238",
        "protection": "non_protege",
        "proprietaire": "prive_personne_physique",
        "etatConservation": "moyen",
        **extra,
    }
    return CreateMonumentRequest(**champs)


class DateProtectionVideTests(unittest.TestCase):
    def test_creation_insere_null_et_non_chaine_vide(self):
        supabase = _base()
        with (
            patch("routers.monuments.quotas.verifier_creation_monument"),
            patch("routers.monuments._enrich_monument", side_effect=lambda _s, m, _u: m),
        ):
            create_monument(
                body=_corps_create(dateProtection="", typeProtection=""),
                user_id="user-1",
                supabase=supabase,
            )
        (insert,) = supabase.ecritures("monuments", "insert")
        self.assertIn("date_protection", insert)
        self.assertIsNone(insert["date_protection"])

    def test_creation_garde_une_date_valide(self):
        supabase = _base()
        with (
            patch("routers.monuments.quotas.verifier_creation_monument"),
            patch("routers.monuments._enrich_monument", side_effect=lambda _s, m, _u: m),
        ):
            create_monument(
                body=_corps_create(protection="classe", dateProtection="1928-06-16"),
                user_id="user-1",
                supabase=supabase,
            )
        (insert,) = supabase.ecritures("monuments", "insert")
        self.assertEqual(insert["date_protection"], "1928-06-16")

    def test_creation_refuse_une_date_mal_formee_en_400(self):
        supabase = _base()
        with (
            patch("routers.monuments.quotas.verifier_creation_monument"),
            patch("routers.monuments._enrich_monument", side_effect=lambda _s, m, _u: m),
            self.assertRaises(HTTPException) as ctx,
        ):
            create_monument(
                body=_corps_create(dateProtection="16/06/1928"),
                user_id="user-1",
                supabase=supabase,
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_patch_efface_vraiment_la_date(self):
        """La clé reste dans l'update : la retirer garderait l'ancienne date."""
        supabase = _base()
        with (
            patch("routers.monuments.require_project_access"),
            patch("routers.monuments._enrich_monument", side_effect=lambda _s, m, _u: m),
        ):
            update_monument(
                monument_id="monument-1",
                body=UpdateMonumentRequest(protection="non_protege", dateProtection=""),
                user_id="user-1",
                supabase=supabase,
            )
        update = supabase.ecritures("monuments", "update")[0]
        self.assertIn("date_protection", update)
        self.assertIsNone(update["date_protection"])


if __name__ == "__main__":
    unittest.main()
