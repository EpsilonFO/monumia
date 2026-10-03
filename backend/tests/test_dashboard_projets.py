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


# `fetch_user_monuments` pose toujours `my_role` et `offre` : le rôle renseigné
# pour l'équipe du monument (None pour un accès obtenu via un seul de ses
# projets), et l'offre qui gouverne le bien — c'est elle qui décide si les aides
# encore à venir sortent nommées du digest.
OFFRE_GRATUITE = {"aidesBientot": False}
OFFRE_VEILLE = {"aidesBientot": True}
M_AVEC = {
    "id": "m1",
    "code_insee": "75056",
    "nom": "Avec projets",
    "my_role": "owner",
    "offre": OFFRE_GRATUITE,
}
M_SANS = {
    "id": "m2",
    "code_insee": "75056",
    "nom": "Sans projet",
    "my_role": "owner",
    "offre": OFFRE_GRATUITE,
}
P1 = {"id": "p1", "monument_id": "m1", "travaux_envisages": ["toiture"], "questionnaire": {}}
P2 = {"id": "p2", "monument_id": "m1", "travaux_envisages": [], "questionnaire": {"f": "oui"}}


def _dashboard(
    tables: dict,
    *,
    monuments: list[dict] | None = None,
    mes_projets: dict[str, str] | None = None,
):
    supabase = _FakeSupabase(tables)
    with (
        patch(
            "routers.dashboard.fetch_user_monuments",
            # Les appartenances propres aux projets (et leur rôle) sortent de
            # `fetch_user_monuments`, qui les lit de toute façon.
            return_value=(
                monuments if monuments is not None else [M_AVEC, M_SANS],
                {"75056": 2_100_000},
                mes_projets or {},
            ),
        ),
        patch("routers.dashboard.deterministic_diagnostic_for", return_value={}),
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

    def test_le_masquage_reste_calcule_par_monument(self) -> None:
        """L'offre du bien vaut pour TOUS ses projets : aucune requête de droits
        n'est refaite ici, l'offre posée par `fetch_user_monuments` suffit."""
        veille = [{**M_AVEC, "offre": OFFRE_VEILLE}, M_SANS]
        with patch("routers.dashboard.build_digest", side_effect=build_digest) as spy:
            _dashboard({"projets": [P1, P2]}, monuments=veille)
        self.assertTrue(all(call.kwargs["masquer_bientot"] is False for call in spy.call_args_list))

        with patch("routers.dashboard.build_digest", side_effect=build_digest) as spy:
            _dashboard({"projets": [P1, P2]})
        self.assertTrue(all(call.kwargs["masquer_bientot"] is True for call in spy.call_args_list))

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
            mes_projets={"p2": "member"},
        )
        self.assertEqual([p["id"] for p in payload["projets"]], ["p2"])
        self.assertEqual(list(payload["digests"]), ["p2"])
        self.assertEqual([d["id"] for d in payload["dossiers"]], ["d2"])
        self.assertEqual(list(payload["suivis"]), ["p2"])
        # Le monument reste servi : c'est la porte d'entrée vers le chantier.
        self.assertEqual([m["id"] for m in payload["monuments"]], ["m1"])

    def test_chaque_projet_porte_son_role_effectif(self) -> None:
        """Le payload remplace les projets du store : sans `my_role`, il
        effacerait le rôle posé par `GET /projets/{id}`."""
        restreint = {**M_AVEC, "my_role": None}
        payload = _dashboard({"projets": [P2]}, monuments=[restreint], mes_projets={"p2": "member"})
        self.assertEqual(payload["projets"][0]["my_role"], "member")

        # Équipe du monument : le rôle se transmet à tous ses chantiers.
        payload = _dashboard({"projets": [P1, P2]})
        self.assertEqual([p["my_role"] for p in payload["projets"]], ["owner", "owner"])

    def test_sans_monument_le_payload_reste_complet(self) -> None:
        supabase = _FakeSupabase({})
        with patch("routers.dashboard.fetch_user_monuments", return_value=([], {}, {})):
            payload = get_dashboard(user_id="u1", supabase=supabase)
        self.assertEqual(payload["projets"], [])
        self.assertEqual(payload["digests"], {})


class BuildDigestTests(unittest.TestCase):
    def test_porte_les_deux_identifiants(self) -> None:
        digest = build_digest({}, "m1", "p1")
        self.assertEqual(digest["projetId"], "p1")
        self.assertEqual(digest["monumentId"], "m1")

    def test_masque_le_nom_des_aides_encore_a_venir(self) -> None:
        """Le digest alimente l'échéancier : une aide dont le guichet n'est pas
        ouvert ne doit pas plus en sortir nommée que du diagnostic complet."""
        aide = {"id": "a1", "nom": "DRAC MH", "categorie": "etat_drac"}
        result = {
            "aidesEligibles": [
                {"aide": dict(aide), "disponibilite": "bientot"},
                {"aide": dict(aide), "disponibilite": "maintenant"},
            ]
        }
        digest = build_digest(result, "m1", "p1", masquer_bientot=True)
        self.assertEqual(digest["aidesEligibles"][0]["aide"]["nom"], "Aide masquée")
        # L'aide déjà ouverte reste nommée : son détail est gratuit.
        self.assertEqual(digest["aidesEligibles"][1]["aide"]["nom"], "DRAC MH")

    def test_ne_masque_rien_avec_l_offre_veille(self) -> None:
        aide = {"id": "a1", "nom": "DRAC MH", "categorie": "etat_drac"}
        result = {"aidesEligibles": [{"aide": aide, "disponibilite": "bientot"}]}
        digest = build_digest(result, "m1", "p1", masquer_bientot=False)
        self.assertEqual(digest["aidesEligibles"][0]["aide"]["nom"], "DRAC MH")

    def test_porte_la_carte_redigee(self) -> None:
        """« À faire maintenant » rédige l'aide comme sa carte : titre, chapeau, montant."""
        carte = {
            "titre": "Subvention DRAC",
            "chapeau": "Pour les travaux.",
            "montant": {"valeur": "40 %"},
        }
        aide = {
            "id": "a1",
            "nom": "DRAC MH",
            "categorie": "etat_drac",
            "carte": carte,
            "tauxMax": 40,
        }
        result = {"aidesEligibles": [{"aide": aide, "disponibilite": "maintenant"}]}
        entree = build_digest(result, "m1", "p1")["aidesEligibles"][0]["aide"]
        self.assertEqual(entree["carte"], carte)
        self.assertEqual(entree["tauxMax"], 40)

    def test_retient_la_carte_des_aides_encore_a_venir(self) -> None:
        """La carte redirait ce que le nom masqué tait."""
        aide = {
            "id": "a1",
            "nom": "DRAC MH",
            "categorie": "etat_drac",
            "carte": {"titre": "Subvention DRAC"},
        }
        result = {"aidesEligibles": [{"aide": aide, "disponibilite": "bientot"}]}
        entree = build_digest(result, "m1", "p1", masquer_bientot=True)["aidesEligibles"][0]["aide"]
        self.assertNotIn("carte", entree)
        self.assertNotIn("nomCourt", entree)

    def test_compte_les_questions_restantes(self) -> None:
        """Une question tranchée ne compte plus ; « passer » ou une réponse
        inconnue du moteur ne tranchent pas."""
        options = [{"id": "oui"}, {"id": "nsp", "unknown": True}]
        result = {
            "aidesPotentiellementEligibles": [
                {
                    "aide": {"id": "a1", "nom": "A", "categorie": "region"},
                    "disponibilite": "maintenant",
                },
                {
                    "aide": {"id": "a2", "nom": "B", "categorie": "region"},
                    "disponibilite": "maintenant",
                },
            ],
            "qcmQuestions": [
                {"id": "q1", "aideIds": ["a1", "a2"], "options": options},
                {"id": "q2", "aideIds": ["a1"], "options": options},
                {"id": "q3", "aideIds": ["a1"], "options": options},
                {"id": "q4", "aideIds": ["a2"], "options": options},
            ],
            "qcmAnswers": {"q2": "skip", "q3": "nsp", "q4": "oui"},
        }
        digest = build_digest(result, "m1", "p1")
        restantes = [m["questionsRestantes"] for m in digest["aidesPotentiellementEligibles"]]
        self.assertEqual(restantes, [3, 1])


if __name__ == "__main__":
    unittest.main()
