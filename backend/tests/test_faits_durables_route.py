"""La route `GET /monuments/{id}/faits-durables` : son droit et sa forme.

Le droit exigé est `co_owner` sur le MONUMENT — exactement celui de créer un
projet, et cette route ne sert qu'à ça. Le point sensible : les réponses
viennent des AUTRES projets du monument, qu'un collaborateur invité sur un seul
chantier n'a pas le droit de voir (cf. « les deux niveaux de partage »). Un
`member`, ou un membre projet-seulement, doit donc être refusé.
"""

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from routers.projets import get_faits_durables


class _Resp:
    def __init__(self, data) -> None:
        self.data = data


class _FakeQuery:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def select(self, *_a, **_k) -> "_FakeQuery":
        return self

    def eq(self, colonne, valeur) -> "_FakeQuery":
        self._rows = [r for r in self._rows if r.get(colonne) == valeur]
        return self

    def execute(self):
        return _Resp(self._rows)


class _FakeSupabase:
    def __init__(self, projets: list[dict]) -> None:
        self._projets = projets

    def table(self, nom: str) -> _FakeQuery:
        return _FakeQuery(list(self._projets) if nom == "projets" else [])


PROJETS = [
    {
        "id": "p-ancien",
        "titre": "Toiture 2024",
        "monument_id": "m1",
        "updated_at": "2026-01-01",
        # `edifice_cultuel` est de scope `monument`, `etat_travaux` de scope
        # `projet` : seul le premier se reprend.
        "questionnaire": {"edifice_cultuel": "oui", "etat_travaux": "acheves"},
    },
    {
        "id": "p-autre-monument",
        "titre": "Ailleurs",
        "monument_id": "m2",
        "updated_at": "2026-02-01",
        "questionnaire": {"edifice_cultuel": "non"},
    },
]


class FaitsDurablesRouteTest(unittest.TestCase):
    def _appeler(self, user_id: str = "u1"):
        return get_faits_durables("m1", user_id=user_id, supabase=_FakeSupabase(PROJETS))  # type: ignore[arg-type]

    def test_rend_les_reponses_leur_provenance_et_les_titres(self) -> None:
        with patch("routers.projets.require_project_access", return_value="co_owner"):
            corps = self._appeler()
        self.assertEqual(corps["reponses"], {"edifice_cultuel": "oui"})
        self.assertEqual(corps["source"], {"edifice_cultuel": "p-ancien"})
        self.assertEqual(corps["titres"], {"p-ancien": "Toiture 2024"})

    def test_ne_lit_que_les_projets_de_CE_monument(self) -> None:
        """Le filtre est posé côté serveur : la réponse de l'autre monument ne
        doit pas fuiter, et surtout pas écraser celle du bon."""
        with patch("routers.projets.require_project_access", return_value="co_owner"):
            corps = self._appeler()
        self.assertNotIn("p-autre-monument", corps["titres"])
        self.assertEqual(corps["reponses"]["edifice_cultuel"], "oui")

    def test_nomme_les_reponses_reprises_et_leur_provenance(self) -> None:
        """Le bandeau du questionnaire doit pouvoir DIRE lesquelles : une
        réponse reprise n'est plus une incertitude, donc aucune fiche d'aide ne
        l'offre à la correction, donc rien d'autre ne la rend vérifiable."""
        with patch("routers.projets.require_project_access", return_value="co_owner"):
            details = self._appeler()["details"]
        self.assertEqual(len(details), 1)
        (reprise,) = details
        self.assertEqual(reprise["fact"], "edifice_cultuel")
        # La question en clair, pas la clé technique.
        self.assertIn("cultuel", reprise["question"].lower())
        # Et la réponse en clair, pas l'identifiant d'option.
        self.assertEqual(reprise["reponse"], "Oui")
        self.assertEqual(reprise["projetTitre"], "Toiture 2024")

    def test_le_droit_exige_est_co_owner_sur_le_monument(self) -> None:
        """Miroir de `create_projet` : la route ne sert qu'à préparer sa
        création, et elle expose les réponses des autres chantiers."""
        with patch("routers.projets.require_project_access", return_value="co_owner") as garde:
            self._appeler()
        garde.assert_called_once()
        self.assertEqual(garde.call_args.args[1:], ("m1", "u1", "co_owner"))

    def test_un_role_insuffisant_est_refuse(self) -> None:
        refus = HTTPException(status_code=403, detail="Action non autorisée pour votre rôle")
        with (
            patch("routers.projets.require_project_access", side_effect=refus),
            self.assertRaises(HTTPException) as ctx,
        ):
            self._appeler("u-member")
        self.assertEqual(ctx.exception.status_code, 403)

    def test_un_monument_sans_projet_rend_un_corps_vide(self) -> None:
        with patch("routers.projets.require_project_access", return_value="co_owner"):
            corps = get_faits_durables("m1", user_id="u1", supabase=_FakeSupabase([]))  # type: ignore[arg-type]
        self.assertEqual(corps, {"reponses": {}, "source": {}, "titres": {}, "details": []})


if __name__ == "__main__":
    unittest.main()
