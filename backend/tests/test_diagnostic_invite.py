"""Le diagnostic INVITÉ : ce qu'il calcule, et surtout ce qu'il ne dit pas.

La route est publique. Le gate du produit ne tient donc plus à un
`Depends(get_current_user_id)` mais à la FORME de la réponse : des questions
aux identifiants d'aides pseudonymisés, et une synthèse chiffrée. Aucun nom,
aucun slug, aucun objet aide.

`test_ne_rend_que_questions_et_synthese` est le test qui porte ce gate : il
relit tout le corpus et cherche chaque nom et chaque slug dans la réponse
sérialisée. Le reste vérifie le cadrage transmis au moteur et les bornes.
"""

import json
import re
import unittest
from unittest.mock import patch

import pydantic
from fastapi import HTTPException

from aides_schema import load_all_aides
from routers.aides import (
    DiagnosticInviteRequest,
    MonumentInvite,
    diagnostic_invite,
    pseudonymiser_aides,
)
from services.offres import GRATUIT


class _Resp:
    def __init__(self, data) -> None:
        self.data = data


class _Query:
    """Faux PostgREST : filtre `eq` pour de vrai, sur des lignes en mémoire."""

    def __init__(self, rows: list) -> None:
        self._rows = rows
        self._single = False
        self._limit: int | None = None

    def select(self, *_a, **_k) -> "_Query":
        return self

    def eq(self, column, value) -> "_Query":
        self._rows = [r for r in self._rows if r.get(column) == value]
        return self

    def limit(self, n) -> "_Query":
        self._limit = n
        return self

    def maybe_single(self) -> "_Query":
        self._single = True
        return self

    def single(self) -> "_Query":
        self._single = True
        return self

    def execute(self):
        rows = self._rows if self._limit is None else self._rows[: self._limit]
        if self._single:
            return _Resp(rows[0] if rows else None)
        return _Resp(list(rows))


class _FakeSupabase:
    def __init__(self, tables: dict) -> None:
        self._tables = tables

    def table(self, name: str) -> _Query:
        return _Query(list(self._tables.get(name, [])))


ROUEN = {
    "code_insee": "76540",
    "nom_commune": "Rouen",
    "nom_commune_matching": "rouen",
    "departement": "Seine-Maritime",
    "departement_num": "76",
    "region": "Normandie",
    "region_code": "normandie",
    "population": 110145,
    "epci_siren": "200023414",
}


def _db(**over) -> _FakeSupabase:
    tables: dict = {"communes": [ROUEN], "communes_historique": []}
    tables.update(over)
    return _FakeSupabase(tables)


MONUMENT = MonumentInvite(
    nom="Chapelle Saint-Julien",
    commune="Rouen",
    protection="classe",
    proprietaire="prive_personne_physique",
    etatConservation="peril",
    siecleConstruction="15e siècle",
)


def _requete(**over) -> DiagnosticInviteRequest:
    champs: dict = {
        "monument": MONUMENT,
        "travauxEnvisages": ["toiture"],
        "answers": {"_raisons": ["restauration_travaux"]},
    }
    champs.update(over)
    return DiagnosticInviteRequest(**champs)


class _Capture:
    """Remplace le moteur : ces tests parlent de ses ENTRÉES."""

    def __init__(self, result: dict | None = None) -> None:
        self.monument: dict | None = None
        self.population: int | None = None
        self.answers: dict | None = None
        self._result = result if result is not None else {"qcmQuestions": []}

    def __call__(self, monument, population, answers, **_kw):
        self.monument = monument
        self.population = population
        self.answers = answers
        return dict(self._result)


def _chaines(node) -> list[str]:
    """Toutes les chaînes FEUILLES du document, clés exclues.

    Un slug d'aide voyage comme une valeur entière (un `aideIds`, une entrée
    d'`eliminationsParOption`), jamais en morceaux : la comparaison est donc
    exacte. Une recherche par sous-chaîne, elle, se déclencherait sur les clés
    de faits qui NOMMENT un dispositif (`travaux_amelioration_denormandie`,
    dont l'aide `denormandie` est un fragment) — un faux positif qui n'apprend
    rien de plus que la question elle-même.
    """
    if isinstance(node, dict):
        return [c for v in node.values() for c in _chaines(v)]
    if isinstance(node, list):
        return [c for v in node for c in _chaines(v)]
    return [node] if isinstance(node, str) else []


def _cles(node) -> list[str]:
    """Toutes les clés du document, à tous les niveaux."""
    if isinstance(node, dict):
        return [*node, *(c for v in node.values() for c in _cles(v))]
    if isinstance(node, list):
        return [c for v in node for c in _cles(v)]
    return []


class FormeDeLaReponseTests(unittest.TestCase):
    """Le gate du parcours découverte : rien du catalogue ne doit sortir."""

    def test_ne_rend_que_questions_et_synthese(self) -> None:
        """Moteur RÉEL, corpus réel : deux clés, et aucun slug d'aide.

        C'est ce test qui porte le gate. Toute clé ajoutée à la réponse — un
        seau d'aides « pour l'accroche », un `aidesEligibles` de débogage — le
        fait tomber, et tout slug qui échapperait à la pseudonymisation aussi.
        """
        result = diagnostic_invite(body=_requete(), supabase=_db())

        self.assertEqual(set(result), {"qcmQuestions", "synthese"})

        aides = load_all_aides()
        self.assertGreater(len(aides), 0, "corpus vide : le test ne prouverait rien")
        chaines = set(_chaines(result))
        fuites = sorted(set(aides) & chaines)
        self.assertEqual(fuites, [], f"slugs d'aides fuités : {fuites}")

    def test_aucun_nom_d_aide_hors_des_textes_de_l_ontologie(self) -> None:
        """Les noms d'aides ne sortent que par le TEXTE des questions.

        Six `help` de `facts.yaml` nomment l'aide que leur question sert (« Le
        Prix François Sommer exige qu'une maîtrise d'œuvre… ») : c'est
        l'ontologie qui explique pourquoi elle demande, et sans ça la question
        devient inintelligible. Ce n'est pas une fuite au sens du produit — un
        compte gratuit voit TOUS les noms du catalogue en clair (décision du
        2026-09-03), l'invité n'en apprend que ceux-là.

        Ce qui serait une fuite, c'est un nom ailleurs : dans un `aideIds`, une
        option, une synthèse — le signe qu'un objet aide a suivi. D'où le
        périmètre du test : tout SAUF `question` et `help`.
        """
        result = diagnostic_invite(body=_requete(), supabase=_db())
        hors_textes = json.dumps(
            {
                "qcmQuestions": [
                    {k: v for k, v in q.items() if k not in ("question", "help")}
                    for q in result["qcmQuestions"]
                ],
                "synthese": result["synthese"],
            },
            ensure_ascii=False,
            default=str,
        )
        for slug, aide in load_all_aides().items():
            self.assertNotIn(aide.nom, hors_textes, f"nom de '{slug}' hors texte de question")

    def test_aucun_objet_aide_dans_la_reponse(self) -> None:
        """Pas un seul champ d'aide, sous aucun nom.

        Le caviardage (`retirer_les_modalites`) protège un compte gratuit en
        VIDANT des champs ; ici il n'y a pas de champ du tout, et c'est plus
        fort : rien à re-remplir par erreur.
        """
        result = diagnostic_invite(body=_requete(), supabase=_db())
        interdites = {
            "aide",
            "aidesEligibles",
            "aidesPotentiellementEligibles",
            "aidesAtteignables",
            "aidesNonEligibles",
            "organisme",
            "montantMax",
            "urlOfficielle",
            "formulaireUrl",
            "documentsRequis",
            "llmEvaluation",
        }
        presentes = interdites & set(_cles(result))
        self.assertEqual(presentes, set(), f"champs d'aide dans la réponse : {presentes}")

    def test_aide_ids_pseudonymises_et_coherents(self) -> None:
        result = diagnostic_invite(body=_requete(), supabase=_db())
        questions = result["qcmQuestions"]
        self.assertGreater(len(questions), 0, "aucune question : le test ne prouverait rien")

        for q in questions:
            ids = set(q["aideIds"])
            for alias in ids:
                self.assertRegex(alias, r"^a\d+$")
            for option, elimines in (q.get("eliminationsParOption") or {}).items():
                self.assertTrue(
                    set(elimines) <= ids,
                    f"question {q['id']}, option {option} : éliminations hors aideIds",
                )

    def test_un_alias_par_slug_distinct(self) -> None:
        """La pseudonymisation est une BIJECTION à l'échelle d'une réponse.

        Sans quoi le front éliminerait la mauvaise aide (deux slugs sous le
        même alias) ou n'en éliminerait aucune (un slug sous deux alias).
        """
        brut = [
            {"id": "f1", "aideIds": ["drac-x", "region-y"], "eliminationsParOption": {}},
            {
                "id": "f2",
                "aideIds": ["region-y", "fondation-z"],
                "eliminationsParOption": {"non": ["region-y"]},
            },
        ]
        sortie = pseudonymiser_aides(brut)

        self.assertEqual(sortie[0]["aideIds"], ["a1", "a2"])
        self.assertEqual(sortie[1]["aideIds"], ["a2", "a3"])
        self.assertEqual(sortie[1]["eliminationsParOption"], {"non": ["a2"]})
        alias = {a for q in sortie for a in q["aideIds"]}
        slugs = {s for q in brut for s in q["aideIds"]}
        self.assertEqual(len(alias), len(slugs))

    def test_pseudonymisation_couvre_les_exclusions_strictes(self) -> None:
        """La seconde table d'éliminations porte aussi des slugs : sans alias,
        le visiteur y lirait les noms d'aides."""
        brut = [
            {
                "id": "usage_batiment",
                "aideIds": ["pdl-tourisme"],
                "eliminationsParOption": {"cultuel": ["pdl-tourisme"]},
                "eliminationsStrictesParOption": {"cultuel": ["pdl-tourisme"]},
            }
        ]
        sortie = pseudonymiser_aides(brut)
        self.assertEqual(sortie[0]["eliminationsStrictesParOption"], {"cultuel": ["a1"]})

    def test_pseudonymisation_ne_mute_pas_les_questions(self) -> None:
        """Les questions sortent du moteur, dont les YAML sont en cache."""
        brut = [{"id": "f1", "aideIds": ["drac-x"], "eliminationsParOption": {"non": ["drac-x"]}}]
        pseudonymiser_aides(brut)
        self.assertEqual(brut[0]["aideIds"], ["drac-x"])
        self.assertEqual(brut[0]["eliminationsParOption"], {"non": ["drac-x"]})

    def test_synthese_compte_les_seaux(self) -> None:
        capture = _Capture(
            {
                "aidesEligibles": [{"aide": {}}, {"aide": {}}],
                "aidesPotentiellementEligibles": [{"aide": {}}],
                "aidesAtteignables": [{"aide": {}}, {"aide": {}}, {"aide": {}}],
                "aidesNonEligibles": [{"aide": {}}] * 40,
                "totalAidesAnalysees": 46,
                "montantPotentielTotal": 120_000,
                "montantAtteignableTotal": 30_000,
                "tauxTravauxMaxPct": 65,
                "qcmQuestions": [],
            }
        )
        with patch("routers.aides.deterministic_diagnostic_for", capture):
            result = diagnostic_invite(body=_requete(), supabase=_db())

        self.assertEqual(
            result["synthese"],
            {
                "eligibles": 2,
                "potentielles": 1,
                "atteignables": 3,
                "totalAnalysees": 46,
                "montantPotentielTotal": 120_000,
                "montantAtteignableTotal": 30_000,
                "tauxTravauxMaxPct": 65,
            },
        )


class CadrageTransmisTests(unittest.TestCase):
    def test_resout_la_commune_et_transmet_le_cadrage(self) -> None:
        capture = _Capture()
        with patch("routers.aides.deterministic_diagnostic_for", capture):
            diagnostic_invite(body=_requete(), supabase=_db())

        assert capture.monument is not None
        self.assertEqual(capture.monument["code_insee"], "76540")
        self.assertEqual(capture.monument["commune"], "Rouen")
        self.assertEqual(capture.monument["region"], "normandie")
        self.assertEqual(capture.monument["departement_num"], "76")
        self.assertEqual(capture.monument["travaux_envisages"], ["toiture"])
        self.assertEqual(capture.monument["protection"], "classe")
        self.assertEqual(capture.monument["etat_conservation"], "peril")
        self.assertEqual(capture.monument["siecle_construction"], "15e siècle")
        self.assertEqual(capture.population, 110145)
        self.assertEqual(capture.answers, {"_raisons": ["restauration_travaux"]})

    def test_code_insee_historique_resolu(self) -> None:
        """Une notice Mérimée porte le code INSEE d'AVANT la fusion.

        `enrich_monument_with_population` ferait un `eq` direct et ne
        trouverait rien : c'est `resolve_code_insee` qui traverse
        `communes_historique`, d'où sa réutilisation ici.
        """
        capture = _Capture()
        monument = MonumentInvite(
            nom="Église",
            commune="Ancienne-Commune",
            codeInsee="76999",
            protection="inscrit",
            proprietaire="public_commune",
        )
        db = _db(
            communes_historique=[{"ancien_code_insee": "76999", "nouveau_code_insee": "76540"}],
        )
        with patch("routers.aides.deterministic_diagnostic_for", capture):
            diagnostic_invite(body=_requete(monument=monument), supabase=db)

        assert capture.monument is not None
        self.assertEqual(capture.monument["code_insee"], "76540")
        self.assertEqual(capture.population, 110145)

    def test_commune_introuvable_400(self) -> None:
        """Refus IMMÉDIAT, pour que le front puisse corriger avant l'inscription."""
        monument = MonumentInvite(
            nom="Manoir",
            commune="Nulle-Part",
            protection="non_protege",
            proprietaire="prive_personne_physique",
        )
        with self.assertRaises(HTTPException) as ctx:
            diagnostic_invite(body=_requete(monument=monument), supabase=_db())
        self.assertEqual(ctx.exception.status_code, 400)

    def test_redaction_gratuit_appliquee(self) -> None:
        """Un visiteur est au gratuit : même caviardage qu'un compte gratuit."""
        capture = _Capture()
        with (
            patch("routers.aides.deterministic_diagnostic_for", capture),
            patch("routers.aides.redact_bientot_hors_offre", side_effect=lambda r, _o: r) as red,
        ):
            diagnostic_invite(body=_requete(), supabase=_db())
        self.assertIs(red.call_args.args[1], GRATUIT)

    def test_travaux_absents_valent_liste_vide(self) -> None:
        """Le dry-run de l'étape monument n'a pas encore de cadrage."""
        capture = _Capture()
        with patch("routers.aides.deterministic_diagnostic_for", capture):
            diagnostic_invite(body=DiagnosticInviteRequest(monument=MONUMENT), supabase=_db())
        assert capture.monument is not None
        self.assertEqual(capture.monument["travaux_envisages"], [])
        self.assertEqual(capture.answers, {})


class BornesTests(unittest.TestCase):
    """La route est publique et pyright n'analyse pas `routers/`."""

    def test_nom_trop_long_refuse(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            MonumentInvite(
                nom="x" * 201,
                commune="Rouen",
                protection="classe",
                proprietaire="prive_personne_physique",
            )

    def test_trop_de_reponses_refuse(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            DiagnosticInviteRequest(
                monument=MONUMENT,
                answers={f"fait_{i}": "oui" for i in range(101)},
            )

    def test_trop_de_travaux_refuse(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            DiagnosticInviteRequest(
                monument=MONUMENT,
                travauxEnvisages=[f"t{i}" for i in range(31)],
            )

    def test_champs_inconnus_ignores(self) -> None:
        """Le brouillon du front porte plus que ce que le moteur lit."""
        monument = MonumentInvite.model_validate(
            {
                "nom": "Chapelle",
                "commune": "Rouen",
                "protection": "classe",
                "proprietaire": "prive_personne_physique",
                "referenceMerimee": "PA00100000",
                "dateProtection": "1930-01-01",
                "descriptionGenerale": "Un texte libre",
            }
        )
        self.assertFalse(hasattr(monument, "referenceMerimee"))

    def test_alias_camel_et_snake_acceptes(self) -> None:
        """Le front envoie `travauxEnvisages` ; les tests écrivent l'un ou l'autre."""
        self.assertEqual(
            DiagnosticInviteRequest(
                monument=MONUMENT, travaux_envisages=["toiture"]
            ).travaux_envisages,
            ["toiture"],
        )
        self.assertEqual(
            DiagnosticInviteRequest(
                monument=MONUMENT, travauxEnvisages=["toiture"]
            ).travaux_envisages,
            ["toiture"],
        )


class AliasFormatTests(unittest.TestCase):
    def test_alias_numerotes_dans_l_ordre_d_apparition(self) -> None:
        sortie = pseudonymiser_aides([{"id": "f1", "aideIds": ["z-aide", "a-aide", "m-aide"]}])
        self.assertEqual(sortie[0]["aideIds"], ["a1", "a2", "a3"])
        self.assertTrue(all(re.fullmatch(r"a\d+", a) for a in sortie[0]["aideIds"]))


if __name__ == "__main__":
    unittest.main()
