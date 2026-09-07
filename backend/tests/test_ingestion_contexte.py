"""Tests du prompt système de l'agent d'ingestion (scripts/ingestion/contexte.py).

Deux dérives sont possibles et invisibles à l'œil nu, parce qu'elles ne cassent
rien : un champ ajouté au schéma que le prompt ne mentionne pas (le modèle
n'écrira jamais ce champ), et une étape du skill qui n'a plus d'outil
correspondant dans le harnais (le modèle essaiera de la faire avec un outil
qu'il n'a pas). Les tests ci-dessous surveillent exactement ces deux choses.

Run from backend/:  uv run pytest tests/test_ingestion_contexte.py
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import yaml  # noqa: E402
from ingestion.contexte import (  # noqa: E402
    ADAPTATIONS,
    MODELES,
    SKILL_PATH,
    condense_schema,
    index_faits,
    prompt_systeme,
    sans_front_matter,
    section,
    titres,
)

from aides_schema import (  # noqa: E402
    CATEGORIES,
    FIELD_REGISTRY,
    RAISONS,
    TYPES,
    Aide,
    Condition,
    load_facts,
    load_pending_facts,
)

MD = """\
# Titre

Introduction.

## Alpha

Contenu alpha.

### Alpha-1

Détail.

## Bêta

Contenu bêta.
"""


class TestDecoupe(unittest.TestCase):
    def test_section_va_jusquau_titre_de_meme_niveau(self):
        alpha = section(MD, "Alpha")
        self.assertIn("Contenu alpha", alpha)
        self.assertIn("Alpha-1", alpha)
        self.assertNotIn("Contenu bêta", alpha)

    def test_titre_donne_en_prefixe(self):
        self.assertIn("Détail", section(MD, "Alpha-"))

    def test_backticks_ignores_dans_la_comparaison(self):
        self.assertIn("Contenu bêta", section(MD, "`Bêta`"))

    def test_section_absente_leve(self):
        with self.assertRaises(KeyError):
            section(MD, "Gamma")

    def test_front_matter_retire(self):
        self.assertEqual(sans_front_matter("---\nname: x\n---\n\n# Titre\n"), "# Titre\n")
        self.assertEqual(sans_front_matter("# Titre\n"), "# Titre\n")


class TestCondenseSchema(unittest.TestCase):
    """Le condensé est généré : ce test le compare au SCHÉMA, pas à lui-même."""

    def setUp(self):
        self.texte = condense_schema()

    def test_tous_les_champs_daide_et_de_condition_sont_decrits(self):
        for modele in (Aide, Condition):
            for champ in modele.model_fields:
                self.assertIn(f"{champ}:", self.texte, f"{modele.__name__}.{champ} absent")

    def test_tous_les_modeles_listes(self):
        for modele in MODELES:
            self.assertIn(f"{modele.__name__} :", self.texte)

    def test_vocabulaires_fermes_au_complet(self):
        for valeur in (*CATEGORIES, *TYPES, *RAISONS):
            self.assertIn(valeur, self.texte)
        for kind in ("untyped", "auto", "user_fact", "discretionary", "info", "manual_check"):
            self.assertIn(kind, self.texte)
        for effect in ("gate", "modulateur", "info"):
            self.assertIn(effect, self.texte)

    def test_chemins_du_field_registry_au_complet(self):
        for chemin in FIELD_REGISTRY:
            self.assertIn(chemin, self.texte)

    def test_annonce_que_les_champs_inconnus_sont_refuses(self):
        self.assertIn("N'EXISTE PAS", self.texte)

    def test_referentiel_des_pieces_au_complet(self):
        """Sans lui, le modèle invente des `piece_id` et le schéma refuse tout.

        Mesuré sur un run réel (or-glm, 2026-09-06) : quatre `piece_id`
        fabriqués — `note_intention`, `vademecum`, `guide_saisie`,
        `carte_territoires_enjeux` — ont fait échouer l'écriture d'une
        extraction par ailleurs correcte. Le champ n'est pas devinable : il
        vient d'un référentiel fermé que le prompt doit porter.
        """
        from pieces_schema import load_pieces

        for piece in load_pieces():
            self.assertIn(piece, self.texte, f"pièce {piece} absente du condensé")
        self.assertIn("TOUTE AUTRE VALEUR EST REFUSÉE", self.texte)
        self.assertIn("FACULTATIF", self.texte)


class TestIndexFaits(unittest.TestCase):
    def setUp(self):
        load_facts.cache_clear()
        load_pending_facts.cache_clear()
        self.facts = load_facts()
        self.pending = load_pending_facts()
        self.texte = index_faits(self.facts, self.pending)

    def test_une_ligne_par_fait(self):
        for cle in {**self.facts, **self.pending}:
            self.assertIn(cle, self.texte)

    def test_les_faits_en_attente_sont_marques(self):
        for cle in self.pending:
            ligne = self._ligne(cle)
            self.assertTrue(ligne.startswith("⏳"), ligne)

    def test_les_faits_approuves_ne_sont_pas_marques(self):
        cle = next(iter(sorted(set(self.facts) - set(self.pending))))
        self.assertFalse(self._ligne(cle).startswith("⏳"))

    def _ligne(self, cle: str) -> str:
        """La ligne de l'index qui décrit ce fait, marqueur ⏳ compris."""
        return next(li for li in self.texte.splitlines() if li.lstrip("⏳ ").split()[:1] == [cle])

    def test_options_listees_pour_les_enums(self):
        enums = [(c, f) for c, f in self.facts.items() if f.options]
        self.assertTrue(enums)
        cle, fait = enums[0]
        ligne = self._ligne(cle)
        for option in fait.options or []:
            self.assertIn(option.id, ligne)

    def test_beaucoup_plus_court_que_facts_yaml(self):
        from aides_schema import FACTS_FILE

        self.assertLess(len(self.texte), len(FACTS_FILE.read_text(encoding="utf-8")) / 2)


class TestGabarit(unittest.TestCase):
    """Le gabarit n'enseigne que ce qu'il contient.

    Mesuré sur un run réel (or-glm, 2026-09-06) : le gabarit servi était une
    aide sans `applies_if` et sans un seul `modulateur`. Le modèle n'a produit
    ni l'un ni l'autre — il a reproduit fidèlement son exemple, et on a
    d'abord conclu à une insuffisance du MODÈLE. C'était une insuffisance du
    harnais, choisissant alors son exemple par date de modification.
    """

    def test_le_gabarit_montre_toujours_un_applies_if(self):
        from ingestion.contexte import choisir_aide_reference

        from aides_schema import AIDES_DIR, load_all_aides

        sans: list[str] = []
        for slug in load_all_aides():
            choix = choisir_aide_reference(slug, AIDES_DIR)
            if choix is None or not yaml.safe_load(choix[1]).get("applies_if"):
                sans.append(slug)
        self.assertEqual(sans, [], "slugs dont le gabarit ne montre pas le périmètre")

    def test_le_gabarit_montre_toujours_un_modulateur(self):
        """L'autre mécanisme que les runs réels ratent systématiquement.

        Mesuré deux fois sur hdf-jardins-en-scene : les 11 critères de
        sélection de la source repliés en 2 conditions composites typées
        `info`, donc sans effet sur le diagnostic. Un gabarit sans un seul
        `modulateur` n'enseigne pas la scission.
        """
        from ingestion.contexte import choisir_aide_reference

        from aides_schema import AIDES_DIR, load_all_aides

        sans: list[str] = []
        for slug in load_all_aides():
            choix = choisir_aide_reference(slug, AIDES_DIR)
            conditions = (yaml.safe_load(choix[1]) or {}).get("conditions") or []
            if not any(c.get("effect") == "modulateur" for c in conditions):
                sans.append(slug)
        self.assertEqual(sans, [], "slugs dont le gabarit ne montre aucun modulateur")

    def test_le_gabarit_nest_jamais_laide_en_cours(self):
        from ingestion.contexte import choisir_aide_reference

        from aides_schema import AIDES_DIR

        for slug in ("hdf-jardins-en-scene", "cvl-tourisme-hebergements"):
            choix = choisir_aide_reference(slug, AIDES_DIR)
            assert choix is not None
            self.assertNotEqual(choix[0], slug)

    def test_la_richesse_recompense_les_mecanismes_rares(self):
        from ingestion.contexte import richesse_doctrinale

        from aides_schema import Aide

        base = {
            "slug": "ex",
            "nom": "x",
            "organisme": "y",
            "categorie": "region",
            "type": "subvention",
            "description": "z",
        }
        pauvre = Aide.model_validate(
            {**base, "conditions": [{"id": "a", "text": "t", "kind": "info"}]}
        )
        riche = Aide.model_validate(
            {
                **base,
                "applies_if": {"fact": "monument_ouvert_au_public", "predicate": {"eq": True}},
                "financement": {"assiette": "les parties classées"},
                "conditions": [
                    {"id": "a", "text": "t", "kind": "info"},
                    {
                        "id": "b",
                        "text": "t",
                        "kind": "user_fact",
                        "effect": "modulateur",
                        "fact": "monument_ouvert_au_public",
                        "predicate": {"eq": True},
                    },
                ],
            }
        )
        self.assertGreater(richesse_doctrinale(riche), richesse_doctrinale(pauvre))

    def test_le_manual_check_coute_des_points(self):
        """Un gabarit qui en porte treize enseigne ce que la doctrine résorbe.

        Le score récompensait la diversité des `kind`, donc récompensait le
        `manual_check` : il servait `hdf-prac-projets-rayonnement-culturel`
        (13 manual_check, 39 `info`, 1 seul modulateur), et la sortie du modèle
        a suivi.
        """
        from ingestion.contexte import richesse_doctrinale

        sobre = self._aide([{"id": "a", "text": "t", "kind": "info"}])
        charge = self._aide(
            [{"id": "a", "text": "t", "kind": "info"}]
            + [{"id": f"m{i}", "text": "t", "kind": "manual_check", "notes": "x"} for i in range(4)]
        )
        self.assertLess(richesse_doctrinale(charge), richesse_doctrinale(sobre))

    def test_les_modulateurs_rapportent(self):
        from ingestion.contexte import richesse_doctrinale

        un = self._aide([self._modulateur(0)])
        quatre = self._aide([self._modulateur(i) for i in range(4)])
        self.assertGreater(richesse_doctrinale(quatre), richesse_doctrinale(un))

    def test_applies_if_domine_toute_richesse(self):
        """Le classement est lexicographique, `applies_if` d'abord.

        En simple bonus pondéré (+4), il se faisait dépasser par le bonus des
        modulateurs (+5) : 19 slugs sur 215 retombaient sur un gabarit sans
        périmètre — le mécanisme le plus coûteux à rater et le seul que le
        modèle ne peut pas deviner.

        Le catalogue réel ne l'exerce pas aujourd'hui (le plus riche sans
        périmètre y reste sous le gabarit servi), d'où un catalogue jetable :
        c'est le MÉCANISME qui est testé, pas la donnée du jour.
        """
        import tempfile

        from ingestion.contexte import choisir_aide_reference, richesse_doctrinale

        with tempfile.TemporaryDirectory() as tmp:
            dossier = Path(tmp)
            riche = self._aide([self._modulateur(i) for i in range(5)])
            maigre = self._aide(
                [{"id": "a", "text": "t", "kind": "info"}],
                applies_if={"fact": "monument_ouvert_au_public", "predicate": {"eq": True}},
            )
            self.assertGreater(richesse_doctrinale(riche), richesse_doctrinale(maigre))
            for slug, aide in (("zz-riche-sans-perimetre", riche), ("zz-maigre", maigre)):
                (dossier / f"{slug}.yaml").write_text(
                    yaml.safe_dump(
                        {**aide.model_dump(mode="json", exclude_none=True), "slug": slug},
                        allow_unicode=True,
                    ),
                    encoding="utf-8",
                )
            choix = choisir_aide_reference("zz-cible", dossier)
            assert choix is not None
            self.assertEqual(choix[0], "zz-maigre")

    def _modulateur(self, index: int) -> dict:
        return {
            "id": f"modulateur-{index}",
            "text": "t",
            "kind": "user_fact",
            "effect": "modulateur",
            "fact": "monument_ouvert_au_public",
            "predicate": {"eq": True},
        }

    def _aide(self, conditions: list[dict], **kw):
        from aides_schema import Aide

        return Aide.model_validate(
            {
                "slug": "ex",
                "nom": "x",
                "organisme": "y",
                "categorie": "region",
                "type": "subvention",
                "description": "z",
                "conditions": conditions,
                **kw,
            }
        )


class TestAdaptations(unittest.TestCase):
    """Chaque étape du skill doit avoir sa traduction dans le harnais.

    C'est le test de non-dérive : si quelqu'un ajoute une « Étape 6 » au skill
    sans dire par quel outil elle passe, l'agent la tentera à mains nues.
    """

    def setUp(self):
        self.skill = SKILL_PATH.read_text(encoding="utf-8")

    def test_chaque_etape_du_skill_a_une_ligne_dans_les_adaptations(self):
        etapes = [t for t in titres(self.skill) if t.startswith("Étape ")]
        self.assertTrue(etapes)
        for etape in etapes:
            numero = etape.split()[1]
            self.assertIn(f"| {numero} ", ADAPTATIONS, f"{etape} sans correspondance")

    def test_les_interdits_du_harnais_sont_ecrits(self):
        for regle in ("NON CITABLE", "proposer_fait", "BUDGET ÉPUISÉ", "Un seul slug"):
            self.assertIn(regle, ADAPTATIONS)


class TestPromptSysteme(unittest.TestCase):
    def setUp(self):
        load_facts.cache_clear()
        load_pending_facts.cache_clear()
        self.texte = prompt_systeme(load_facts(), load_pending_facts())

    def test_le_skill_est_repris_tel_quel(self):
        corps = sans_front_matter(SKILL_PATH.read_text(encoding="utf-8")).rstrip()
        self.assertTrue(self.texte.startswith(corps))

    def test_ni_front_matter_ni_nom_de_skill(self):
        self.assertNotIn("name: ingest-aide", self.texte)

    def test_sections_de_typing_presentes(self):
        for attendu in (
            "L'arbre de décision",
            "Jurisprudence des retypages",
            "Puces composites",
            "Proposer un nouveau fait",
            "Format de la fiche de review",
        ):
            self.assertIn(attendu, self.texte)

    def test_sections_de_readme_presentes(self):
        self.assertIn("## Workflow", self.texte)
        self.assertIn("## Typologie des conditions", self.texte)

    def test_stable_dun_appel_a_lautre(self):
        """Le préfixe doit être identique pour que le cache du fournisseur morde."""
        self.assertEqual(self.texte, prompt_systeme(load_facts(), load_pending_facts()))


if __name__ == "__main__":
    unittest.main()
