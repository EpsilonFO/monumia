"""Tests du typage automatique des conditions (scripts/veille_typage.py).

Ce qui compte ici n'est pas la qualité du typage — c'est un jugement, et le
`git diff` est sa revue — mais les invariants qui protègent les données :

  - `facts.yaml` n'est JAMAIS écrit ; un fait nouveau va dans `facts_pending`.
  - `manual_check` + `gate` est refusé, toujours.
  - un prédicat impossible pour le type du fait est refusé avant écriture.
  - `text` et `quote` ne bougent pas : le typage porte sur la forme.
  - un typage partiel est refusé : une seule `untyped` restante garde l'aide
    entière hors du moteur, donc ne sert à rien.

Le modèle est remplacé par une réponse fixée ; aucun test ne touche au réseau.

Run from backend/:  uv run pytest tests/test_veille_typage.py
"""

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import veille_typage  # noqa: E402
from veille_llm import LLMCall, ModelSpec  # noqa: E402
from veille_typage import (  # noqa: E402
    NouveauFait,
    TypageLLMOutput,
    TypageResult,
    check_nouveaux_faits,
    check_predicats,
    check_referentiel_typage,
    ecrire_faits_pending,
    index_faits,
    section_typage,
    sortie_typage,
    typer,
    valider,
)

from aides_schema import AIDES_DIR, Aide, load_aide, load_facts  # noqa: E402

AUJOURD_HUI = date(2026, 8, 24)

SPEC = ModelSpec(
    alias="faux",
    provider="openai_compat",
    model_id="faux",
    env_key="FAUX_KEY",
    prix_in=0.0,
    prix_out=0.0,
)

FICHE = """slug: aide-test
nom: Aide de test
organisme: Organisme de test
categorie: region
type: subvention
raison:
  - restauration_travaux
description: >-
  Une aide de test pour la restauration du patrimoine rural, dotée d'une
  description suffisamment longue pour occuper un block scalar replié.

source:
  url_officielle: https://ex.fr/aide
  verified_at: 2026-07-01

financement:
  taux_max: 30.0

cumul:
  cumulable: true

calendrier:
  permanent: false
  date_limite: 2026-11-30

conditions:
  - id: edifice-anterieur-1800
    text: L'édifice doit être antérieur à 1800.
    kind: user_fact
    effect: gate
    fact: annee_construction
    predicate:
      lt: 1800
    quote: Les édifices antérieurs à 1800 sont éligibles.

  - id: ouverture-public
    text: L'édifice est ouvert au public quinze jours par an.
    kind: untyped
    quote: ouvrir l'édifice au public quinze jours par an
    notes: ajoutée par audit du 2026-08-24, à typer

tags:
  - test
"""


def ecrire_fiche(contenu: str = FICHE) -> tuple[Path, Aide, tempfile.TemporaryDirectory]:
    tmp = tempfile.TemporaryDirectory()
    chemin = Path(tmp.name) / "aide-test.yaml"
    chemin.write_text(contenu, encoding="utf-8")
    return chemin, load_aide(chemin), tmp


def sortie(**kwargs) -> str:
    return json.dumps({"slug": "aide-test", "resume": "typé", **kwargs}, ensure_ascii=False)


def typage(**kwargs) -> dict:
    return {"id": "ouverture-public", "kind": "info", "effect": "info", **kwargs}


def un_fait(type_: str) -> str:
    """Clé d'un fait existant de ce type, choisie dynamiquement.

    Jamais de nom de fait en dur : l'ontologie évolue (le refactor
    `travaux_commences` → `etat_travaux` a cassé quatre tests écrits ainsi), et
    ce qu'on vérifie ici ne dépend pas de QUEL fait on prend, seulement de son
    type.
    """
    facts = load_facts()
    return next(cle for cle, f in sorted(facts.items()) if f.type == type_)


class TestReferentiel(unittest.TestCase):
    def setUp(self):
        _c, self.aide, self._tmp = ecrire_fiche()
        self.addCleanup(self._tmp.cleanup)
        self.attendus = {"ouverture-public"}
        self.facts = load_facts()

    def _erreurs(self, conditions: list[dict], **kw) -> list[str]:
        out = TypageLLMOutput.model_validate({"conditions": conditions, **kw})
        return check_referentiel_typage(out, self.aide, self.attendus, self.facts)

    def test_manual_check_gate_est_interdit(self):
        erreurs = self._erreurs([typage(kind="manual_check", effect="gate", notes="parce que")])
        self.assertTrue(any("INTERDIT" in e for e in erreurs))

    def test_manual_check_info_est_accepte_avec_notes(self):
        self.assertEqual(
            self._erreurs([typage(kind="manual_check", effect="info", notes="irréductible")]), []
        )

    def test_manual_check_sans_notes_est_refuse(self):
        erreurs = self._erreurs([typage(kind="manual_check", effect="info")])
        self.assertTrue(any("exige des `notes`" in e for e in erreurs))

    def test_info_ne_peut_pas_gater(self):
        erreurs = self._erreurs([typage(kind="info", effect="gate")])
        self.assertTrue(any("`gate` interdit" in e for e in erreurs))

    def test_user_fact_sur_fait_inconnu_est_refuse(self):
        erreurs = self._erreurs(
            [
                typage(
                    kind="user_fact", effect="gate", fact="fait_imaginaire", predicate={"eq": True}
                )
            ]
        )
        self.assertTrue(any("inconnu" in e for e in erreurs))

    def test_user_fact_sur_fait_propose_est_accepte(self):
        # Un fait proposé dans la MÊME réponse est un référent valable.
        erreurs = self._erreurs(
            [
                typage(
                    kind="user_fact",
                    effect="gate",
                    fact="jours_ouverture_public_test",
                    predicate={"gte": 15},
                )
            ],
            nouveaux_faits=[
                {
                    "cle": "jours_ouverture_public_test",
                    "type": "integer",
                    "scope": "monument",
                    "question": "Combien de jours par an ?",
                }
            ],
        )
        self.assertEqual(erreurs, [])

    def test_champ_auto_hors_registre_est_refuse(self):
        erreurs = self._erreurs(
            [typage(kind="auto", effect="gate", field="monument.inexistant", predicate={"eq": "x"})]
        )
        self.assertTrue(any("absent du registre" in e for e in erreurs))

    def test_typage_partiel_est_refuse(self):
        # Une seule `untyped` restante garde l'aide ENTIÈRE hors du moteur.
        erreurs = check_referentiel_typage(
            TypageLLMOutput(), self.aide, {"ouverture-public"}, self.facts
        )
        self.assertTrue(any("non typée(s)" in e for e in erreurs))

    def test_condition_deja_typee_est_refusee(self):
        erreurs = self._erreurs([typage(id="edifice-anterieur-1800")])
        self.assertTrue(any("n'est pas une condition `untyped`" in e for e in erreurs))


class TestPredicats(unittest.TestCase):
    """Les prédicats passent par les MÊMES contrôles que le linter du dépôt."""

    def setUp(self):
        self.facts = load_facts()

    def test_operateur_impossible_pour_le_type_du_fait(self):
        # `gte` n'a aucun sens sur un fait boolean.
        out = TypageLLMOutput.model_validate(
            {
                "conditions": [
                    typage(
                        kind="user_fact",
                        effect="gate",
                        fact=un_fait("boolean"),
                        predicate={"gte": 3},
                    )
                ]
            }
        )
        erreurs = check_predicats(out, self.facts)
        self.assertTrue(any("invalide pour un fait boolean" in e for e in erreurs))

    def test_valeur_hors_options_d_un_enum(self):
        out = TypageLLMOutput.model_validate(
            {
                "conditions": [
                    typage(
                        kind="auto",
                        effect="gate",
                        field="monument.proprietaire",
                        predicate={"eq": "licorne"},
                    )
                ]
            }
        )
        erreurs = check_predicats(out, self.facts)
        self.assertTrue(any("hors référentiel" in e for e in erreurs))

    def test_predicat_valide_passe(self):
        out = TypageLLMOutput.model_validate(
            {
                "conditions": [
                    typage(
                        kind="user_fact",
                        effect="gate",
                        fact=un_fait("boolean"),
                        predicate={"eq": False},
                    )
                ]
            }
        )
        self.assertEqual(check_predicats(out, self.facts), [])


class TestNouveauxFaits(unittest.TestCase):
    def setUp(self):
        self.facts = load_facts()

    def _erreurs(self, faits: list[dict], conditions: list[dict] | None = None) -> list[str]:
        out = TypageLLMOutput.model_validate(
            {"nouveaux_faits": faits, "conditions": conditions or []}
        )
        return check_nouveaux_faits(out, self.facts, {})

    def test_fait_deja_dans_l_ontologie_est_refuse(self):
        # La valeur de l'ontologie est la déduplication : recréer un fait
        # existant la détruit.
        existant = next(iter(self.facts))
        erreurs = self._erreurs(
            [{"cle": existant, "type": "boolean", "scope": "projet", "question": "?"}],
            [typage(kind="user_fact", effect="gate", fact=existant, predicate={"eq": True})],
        )
        self.assertTrue(any("existe DÉJÀ" in e for e in erreurs))

    def test_enum_sans_options_est_refuse(self):
        erreurs = self._erreurs(
            [{"cle": "un_enum_test", "type": "enum", "scope": "projet", "question": "?"}],
            [typage(kind="user_fact", effect="gate", fact="un_enum_test", predicate={"eq": "a"})],
        )
        self.assertTrue(any("options" in e for e in erreurs))

    def test_fait_orphelin_est_refuse(self):
        # Un fait que personne ne référence est du bruit dans facts_pending.
        erreurs = self._erreurs(
            [{"cle": "fait_orphelin", "type": "boolean", "scope": "projet", "question": "?"}]
        )
        self.assertTrue(any("référencé(s) par aucune condition" in e for e in erreurs))


class TestEcritureFaitsPending(unittest.TestCase):
    """`facts.yaml` ne doit JAMAIS être touché — règle du dépôt."""

    def test_ecrit_dans_pending_et_jamais_dans_facts(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        pending = Path(tmp.name) / "facts_pending.yaml"
        reel = Path("data/facts.yaml").resolve()
        avant = reel.read_bytes()

        with mock.patch.object(veille_typage, "FACTS_PENDING_FILE", pending):
            ecrits = ecrire_faits_pending(
                [
                    NouveauFait(
                        cle="s_engage_ouverture_test",
                        type="boolean",
                        scope="projet",
                        question="Vous engagez-vous à ouvrir au public ?",
                    )
                ]
            )
        self.assertEqual(ecrits, ["s_engage_ouverture_test"])
        contenu = pending.read_text(encoding="utf-8")
        self.assertIn("s_engage_ouverture_test:", contenu)
        self.assertIn("scope: projet", contenu)
        self.assertEqual(reel.read_bytes(), avant, "facts.yaml doit rester intact")

    def test_ajoute_sans_reecrire_l_existant(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        pending = Path(tmp.name) / "facts_pending.yaml"
        pending.write_text("fait_anterieur:\n  type: boolean\n  scope: projet\n  question: 'x'\n")
        with mock.patch.object(veille_typage, "FACTS_PENDING_FILE", pending):
            ecrire_faits_pending(
                [NouveauFait(cle="fait_neuf", type="boolean", scope="projet", question="?")]
            )
        contenu = pending.read_text(encoding="utf-8")
        self.assertIn("fait_anterieur:", contenu)
        self.assertIn("fait_neuf:", contenu)


class TestApplication(unittest.TestCase):
    def _typer(self, reponse: str, *, dry_run: bool = False, fiche: str = FICHE):
        chemin, aide, tmp = ecrire_fiche(fiche)
        appels: list[str] = []

        def faux_call(spec, system, user, **kwargs):
            appels.append(user)
            return LLMCall(text=reponse, model="faux", cost_usd=0.0)

        pending = Path(tmp.name) / "facts_pending.yaml"
        with (
            mock.patch.object(veille_typage, "call", faux_call),
            mock.patch.object(veille_typage, "FACTS_PENDING_FILE", pending),
        ):
            res = typer(aide, SPEC, aujourd_hui=AUJOURD_HUI, dry_run=dry_run, chemin=chemin)
        return res, chemin, tmp, appels

    def test_typage_en_info_reecrit_kind_et_effect(self):
        res, chemin, tmp, _ = self._typer(sortie(conditions=[typage(notes="simple modalité")]))
        with tmp:
            self.assertEqual(res.etat, "type", res.erreurs)
            texte = chemin.read_text(encoding="utf-8")
            self.assertIn("kind: info", texte)
            self.assertNotIn("kind: untyped", texte)
            # Le fond ne bouge pas : text et quote sont hors de CHAMPS_TYPAGE.
            self.assertIn("text: L'édifice est ouvert au public quinze jours par an.", texte)
            self.assertIn("quote: ouvrir l'édifice au public quinze jours par an", texte)
            # La note « à typer » de l'audit est remplacée, pas empilée.
            self.assertNotIn("à typer", texte)
            self.assertIn(f"typée par audit du {AUJOURD_HUI.isoformat()}", texte)
            # Le fichier reste une fiche valide et devient engine-ready.
            relu = load_aide(chemin)
            self.assertTrue(all(c.kind != "untyped" for c in relu.conditions))

    def test_gate_sur_fait_existant_est_ecrit(self):
        # Décision explicite du dépôt : le typage a le droit de poser un gate.
        fait = un_fait("boolean")
        res, chemin, tmp, _ = self._typer(
            sortie(
                conditions=[
                    typage(kind="user_fact", effect="gate", fact=fait, predicate={"eq": False})
                ]
            )
        )
        with tmp:
            self.assertEqual(res.etat, "type", res.erreurs)
            self.assertEqual(res.gates_poses, 1)
            relu = load_aide(chemin)
            cond = next(c for c in relu.conditions if c.id == "ouverture-public")
            self.assertEqual((cond.kind, cond.effect, cond.fact), ("user_fact", "gate", fait))
            # `effect` s'insère à sa place canonique, juste après `kind`, et non
            # en fin d'item : le `git diff` est la revue.
            texte = chemin.read_text(encoding="utf-8")
            self.assertLess(texte.index("kind: user_fact"), texte.index("effect: gate"))
            self.assertLess(texte.index("effect: gate"), texte.index("quote: ouvrir"))

    def test_dry_run_n_ecrit_ni_fiche_ni_faits(self):
        res, chemin, tmp, _ = self._typer(
            sortie(
                conditions=[
                    typage(
                        kind="user_fact", effect="gate", fact="fait_neuf", predicate={"eq": True}
                    )
                ],
                nouveaux_faits=[
                    {"cle": "fait_neuf", "type": "boolean", "scope": "projet", "question": "?"}
                ],
            ),
            dry_run=True,
        )
        with tmp:
            self.assertEqual(res.etat, "type", res.erreurs)
            self.assertEqual(chemin.read_text(encoding="utf-8"), FICHE)
            self.assertFalse((Path(tmp.name) / "facts_pending.yaml").exists())

    def test_manual_check_gate_ne_s_ecrit_jamais(self):
        res, chemin, tmp, appels = self._typer(
            sortie(conditions=[typage(kind="manual_check", effect="gate", notes="x")])
        )
        with tmp:
            self.assertEqual(res.etat, "echec")
            self.assertEqual(res.etape_echec, "referentiel")
            self.assertEqual(len(appels), 2, "une seule nouvelle tentative")
            self.assertEqual(chemin.read_text(encoding="utf-8"), FICHE)

    def test_aide_sans_untyped_ne_consomme_aucun_appel(self):
        propre = FICHE.replace("    kind: untyped\n", "    kind: info\n    effect: info\n")
        chemin, aide, tmp = ecrire_fiche(propre)
        appels: list[str] = []

        def faux_call(*a, **k):
            appels.append("appel")
            return LLMCall(text="{}", model="faux")

        with tmp, mock.patch.object(veille_typage, "call", faux_call):
            res = typer(aide, SPEC, aujourd_hui=AUJOURD_HUI, chemin=chemin)
            self.assertEqual(res.etat, "rien_a_faire")
            self.assertEqual(appels, [])


class TestSortieTypage(unittest.TestCase):
    def test_ni_text_ni_quote_ne_sont_transmis(self):
        _c, aide, tmp = ecrire_fiche()
        with tmp:
            out = TypageLLMOutput.model_validate({"conditions": [typage()]})
            sortie_veille = sortie_typage(out, aide, AUJOURD_HUI)
            champs = sortie_veille.conditions[0].champs or {}
            self.assertNotIn("text", champs)
            self.assertNotIn("quote", champs)
            self.assertEqual(champs["kind"], "info")


class TestIndexFaits(unittest.TestCase):
    def test_l_index_est_bien_plus_compact_que_le_fichier(self):
        # 92 Ko de facts.yaml envoyés à chaque appel seraient du gaspillage.
        facts = load_facts()
        index = index_faits(facts)
        self.assertLess(len(index), len(Path("data/facts.yaml").read_text(encoding="utf-8")) // 2)
        # Chaque fait y figure avec son type, son scope et sa question.
        self.assertEqual(len(index.splitlines()), len(facts))
        cle = un_fait("boolean")
        self.assertIn(f"{cle} (boolean, {facts[cle].scope})", index)


class TestSectionRapport(unittest.TestCase):
    def test_les_gates_sont_signales_dans_le_rapport(self):
        res = TypageResult(
            slug="a",
            etat="type",
            typees=[("c1", "user_fact", "gate"), ("c2", "info", "info")],
            faits_proposes=["un_fait"],
            gates_poses=1,
        )
        rapport = "\n".join(section_typage({"a": res}, "complet"))
        self.assertIn("| a | `c1` | `user_fact` | `gate` ⚠ |", rapport)
        self.assertIn("| a | `c2` | `info` | `info` |", rapport)
        self.assertIn("facts_pending.yaml", rapport)
        self.assertIn("`un_fait`", rapport)

    def test_section_vide_quand_rien_a_typer(self):
        self.assertEqual(section_typage({}, "complet"), [])


class TestValidationComplete(unittest.TestCase):
    def test_la_chaine_s_arrete_a_la_premiere_etape_fautive(self):
        _c, aide, tmp = ecrire_fiche()
        with tmp:
            facts = load_facts()
            out, erreurs, etape = valider(
                sortie(conditions=[typage(kind="manual_check", effect="gate", notes="x")]),
                aide,
                {"ouverture-public"},
                facts,
                {},
            )
            self.assertIsNotNone(out)
            self.assertEqual(etape, "referentiel")
            self.assertTrue(erreurs)

    def test_json_sale_est_tolere(self):
        _c, aide, tmp = ecrire_fiche()
        with tmp:
            brut = "```json\n" + sortie(conditions=[typage()]) + "\n```"
            out, erreurs, etape = valider(brut, aide, {"ouverture-public"}, load_facts(), {})
            self.assertIsNotNone(out)
            self.assertEqual((erreurs, etape), ([], None))


class TestParcReel(unittest.TestCase):
    def test_toutes_les_fiches_du_depot_restent_chargeables(self):
        # Garde-fou : le module ne doit rien casser à l'import ni au chargement.
        chemins = sorted(AIDES_DIR.glob("*.yaml"))
        self.assertGreater(len(chemins), 100)
        for chemin in chemins:
            load_aide(chemin)


if __name__ == "__main__":
    unittest.main()
