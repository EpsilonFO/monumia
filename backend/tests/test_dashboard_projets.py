"""Payload du dashboard après l'inversion de hiérarchie.

Un digest par PROJET (plus par monument), les suivis indexés par projet, et un
monument sans projet qui n'apparaît dans aucun digest — le front y affiche le
CTA « Lancer un projet de travaux » plutôt qu'un diagnostic vide.
"""

import unittest
from unittest.mock import patch

from routers.dashboard import build_digest, get_dashboard


class _Resp:
    def __init__(self, data) -> None:
        self.data = data


class _FakeQuery:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def select(self, *_a, **_k) -> "_FakeQuery":
        return self

    def eq(self, *_a, **_k) -> "_FakeQuery":
        return self

    def in_(self, *_a, **_k) -> "_FakeQuery":
        return self

    def order(self, *_a, **_k) -> "_FakeQuery":
        return self

    def execute(self) -> _Resp:
        return _Resp(list(self._rows))


class _FakeSupabase:
    def __init__(self, tables: dict) -> None:
        self._tables = tables

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(self._tables.get(name, []))


# `fetch_user_monuments` pose toujours `my_role` : renseigné pour l'équipe du
# monument, None pour un accès obtenu via un seul de ses projets.
M_AVEC = {"id": "m1", "code_insee": "75056", "nom": "Avec projets", "my_role": "owner"}
M_SANS = {"id": "m2", "code_insee": "75056", "nom": "Sans projet", "my_role": "owner"}
P1 = {"id": "p1", "monument_id": "m1", "travaux_envisages": ["toiture"], "questionnaire": {}}
P2 = {"id": "p2", "monument_id": "m1", "travaux_envisages": [], "questionnaire": {"f": "oui"}}


def _dashboard(
    tables: dict,
    *,
    unlocked: list[str] | None = None,
    monuments: list[dict] | None = None,
    mes_projets: list[str] | None = None,
):
    supabase = _FakeSupabase(tables)
    with (
        patch(
            "routers.dashboard.fetch_user_monuments",
            return_value=(
                monuments if monuments is not None else [M_AVEC, M_SANS],
                {"75056": 2_100_000},
            ),
        ),
        patch("routers.dashboard.projet_ids_membre", return_value=mes_projets or []),
        patch("routers.dashboard.deterministic_diagnostic_for", return_value={}),
        patch(
            "routers.dashboard.billing.access_snapshot",
            return_value={"unlockedMonumentIds": unlocked or [], "allAccess": False},
        ),
    ):
        return get_dashboard(user_id="u1", supabase=supabase)


class DashboardPayloadTests(unittest.TestCase):
    def test_un_digest_par_projet(self) -> None:
        payload = _dashboard({"projets": [P1, P2]})
        self.assertEqual(sorted(payload["digests"]), ["p1", "p2"])

    def test_monument_sans_projet_n_a_pas_de_digest(self) -> None:
        payload = _dashboard({"projets": [P1]})
        self.assertNotIn("m2", payload["digests"])
        # Le monument reste servi : c'est lui qui porte le CTA de création.
        self.assertIn("m2", [m["id"] for m in payload["monuments"]])

    def test_les_projets_sont_dans_le_payload(self) -> None:
        payload = _dashboard({"projets": [P1, P2]})
        self.assertEqual([p["id"] for p in payload["projets"]], ["p1", "p2"])

    def test_suivis_indexes_par_projet(self) -> None:
        suivi = {"id": "s1", "projet_id": "p2", "monument_id": "m1", "aide_id": "a1"}
        payload = _dashboard({"projets": [P1, P2], "aide_suivis": [suivi]})
        self.assertEqual(payload["suivis"]["p1"], [])
        self.assertEqual(payload["suivis"]["p2"], [suivi])

    def test_le_verrou_reste_calcule_par_monument(self) -> None:
        """Débloquer m1 ouvre TOUS ses projets — le paywall est clé monument."""
        with patch("routers.dashboard.build_digest", side_effect=build_digest) as spy:
            _dashboard({"projets": [P1, P2]}, unlocked=["m1"])
        self.assertTrue(all(call.kwargs["locked"] is False for call in spy.call_args_list))

        with patch("routers.dashboard.build_digest", side_effect=build_digest) as spy:
            _dashboard({"projets": [P1, P2]}, unlocked=[])
        self.assertTrue(all(call.kwargs["locked"] is True for call in spy.call_args_list))

    def test_acces_par_projet_ne_montre_que_ce_projet(self) -> None:
        """Le cœur du cloisonnement : invité sur p2, on ne voit pas p1."""
        restreint = {**M_AVEC, "my_role": None}
        payload = _dashboard(
            {
                "projets": [P1, P2],
                "dossiers": [
                    {"id": "d1", "projet_id": "p1", "monument_id": "m1"},
                    {"id": "d2", "projet_id": "p2", "monument_id": "m1"},
                ],
                "aide_suivis": [
                    {"id": "s1", "projet_id": "p1", "monument_id": "m1", "aide_id": "a"},
                    {"id": "s2", "projet_id": "p2", "monument_id": "m1", "aide_id": "a"},
                ],
            },
            monuments=[restreint],
            mes_projets=["p2"],
        )
        self.assertEqual([p["id"] for p in payload["projets"]], ["p2"])
        self.assertEqual(list(payload["digests"]), ["p2"])
        self.assertEqual([d["id"] for d in payload["dossiers"]], ["d2"])
        self.assertEqual(list(payload["suivis"]), ["p2"])
        # Le monument reste servi : c'est la porte d'entrée vers le chantier.
        self.assertEqual([m["id"] for m in payload["monuments"]], ["m1"])

    def test_sans_monument_le_payload_reste_complet(self) -> None:
        supabase = _FakeSupabase({})
        with (
            patch("routers.dashboard.fetch_user_monuments", return_value=([], {})),
            patch("routers.dashboard.projet_ids_membre", return_value=[]),
        ):
            payload = get_dashboard(user_id="u1", supabase=supabase)
        self.assertEqual(payload["projets"], [])
        self.assertEqual(payload["digests"], {})


class BuildDigestTests(unittest.TestCase):
    def test_porte_les_deux_identifiants(self) -> None:
        digest = build_digest({}, "m1", "p1")
        self.assertEqual(digest["projetId"], "p1")
        self.assertEqual(digest["monumentId"], "m1")

    def test_masque_le_nom_des_aides_quand_verrouille(self) -> None:
        result = {
            "aidesEligibles": [{"aide": {"id": "a1", "nom": "DRAC MH", "categorie": "etat_drac"}}]
        }
        digest = build_digest(result, "m1", "p1", locked=True)
        self.assertEqual(digest["aidesEligibles"][0]["aide"]["nom"], "Aide masquée")


if __name__ == "__main__":
    unittest.main()
