"""Tests de la proposition de faits (scripts/ingestion/faits.py).

Le fichier `facts_pending.yaml` a déjà été détruit une fois par deux ingestions
parallèles (2026-09-04, quatre faits perdus). Les tests ci-dessous fixent les
trois propriétés qui l'empêchent de se reproduire : une collision est refusée,
une écriture refusée laisse le fichier strictement intact, et le fait ajouté
est immédiatement visible du lint lancé dans le même processus.

Run from backend/:  uv run pytest tests/test_ingestion_faits.py
"""

import dataclasses
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from ingestion import faits  # noqa: E402
from ingestion.atelier import atelier_redirige, restaurer_sources  # noqa: E402

from aides_schema import FactDef, charger_yaml, load_pending_facts  # noqa: E402

JOUR = date(2026, 9, 6)

FACTS = {
    "monument_ouvert_au_public": FactDef(
        type="boolean", scope="monument", question="Le monument est-il ouvert au public ?"
    ),
    "accord_abf": FactDef(
        type="enum",
        scope="projet",
        question="Avez-vous l'accord de l'Architecte des Bâtiments de France (ABF) ?",
        options=[
            {"id": "obtenu", "label": "Obtenu"},  # type: ignore[list-item]
            {"id": "en_cours", "label": "En cours"},  # type: ignore[list-item]
        ],
    ),
}

DEFINITION = """\
type: boolean
scope: monument
question: Le jardin est-il labellisé « Jardin remarquable » ?
help: Label délivré par le ministère de la Culture pour cinq ans.
"""

JUSTIFICATION = (
    "Aucun fait existant ne porte le label « Jardin remarquable » : "
    "`monument_ouvert_au_public` ne dit rien du label, et `accord_abf` relève de "
    "l'autorisation de travaux, pas d'une distinction. Le règlement en fait un "
    "critère de bonification explicite."
)


class BaseFaits(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        # `atelier_redirige` détourne une globale de PROCESSUS : sans ce
        # nettoyage, les tests suivants liraient un tmpdir effacé.
        self.addCleanup(restaurer_sources)
        self.racine = Path(self._tmp.name)
        self.pending_path = self.racine / "facts_pending.yaml"
        self.pending_path.write_text("", encoding="utf-8")
        self.atelier = dataclasses.replace(
            atelier_redirige("ex-aide", self.racine, jour=JOUR),
            pending_path=self.pending_path,
        )
        load_pending_facts.cache_clear()

    def proposer(
        self,
        fact_id="jardin_remarquable",
        definition=DEFINITION,
        justif=JUSTIFICATION,
        *,
        deja_proposes=(),
        detailles=(),
    ):
        return faits.proposer(
            self.atelier,
            FACTS,
            fact_id,
            definition,
            justif,
            deja_proposes=deja_proposes,
            detailles=detailles,
        )


class TestPlafondEtForme(BaseFaits):
    """D1-D4 — ce qu'une aide n'a PAS le droit de faire naître.

    563 faits proposés pour 643 aides, dont 431 cités par une seule : l'ontologie
    a doublé en une nuit. Chacun de ces quatre refus ORIENTE — il nomme ce qu'il
    faut écrire à la place, sinon il pousse à contourner.
    """

    def test_le_quatrieme_fait_est_refuse_et_oriente(self):
        sortie = self.proposer(deja_proposes=("a", "b", "c"))
        self.assertIn("ERREUR", sortie)
        self.assertIn("plafond", sortie)
        # Les trois issues de la doctrine, nommées.
        self.assertIn("manual_check", sortie)
        self.assertIn("effect: info", sortie)
        self.assertIn("retirer_fait", sortie)
        self.assertEqual(self.pending_path.read_text(encoding="utf-8"), "")

    def test_le_troisieme_passe(self):
        self.assertNotIn("ERREUR", self.proposer(deja_proposes=("a", "b")))

    def test_booleen_a_seuil_dans_la_cle_refuse(self):
        """Le seuil appartient au prédicat : 37 booléens du lot l'enfermaient."""
        sortie = self.proposer(
            fact_id="logement_plus_15_ans",
            definition=(
                "type: boolean\nscope: monument\nquestion: Le logement a-t-il plus de 15 ans ?\n"
            ),
        )
        self.assertIn("ERREUR", sortie)
        self.assertIn("integer", sortie)
        self.assertIn("gte", sortie)

    def test_integer_a_seuil_accepte(self):
        """La clé peut nommer l'unité ; c'est le COMPARATEUR qui est interdit."""
        sortie = self.proposer(
            fact_id="age_batiment_ans",
            definition=(
                "type: integer\nscope: monument\nunit: ans\n"
                "question: Quel âge a le bâtiment, en années ?\n"
            ),
        )
        self.assertNotIn("ERREUR", sortie)

    def test_un_millesime_dans_la_cle_passe(self):
        """« avant 1948 » n'est pas un seuil comparatif."""
        sortie = self.proposer(
            fact_id="batiment_construit_avant_1948",
            definition=(
                "type: boolean\nscope: monument\n"
                "question: Le bâtiment a-t-il été construit avant 1948 ?\n"
            ),
        )
        self.assertNotIn("ERREUR", sortie)

    def test_question_trop_longue_refusee(self):
        """36 listes d'exclusions du lot faisaient de 500 à 656 caractères."""
        liste = "intermédiation financière, promotion immobilière, " * 12
        sortie = self.proposer(
            fact_id="activite_hors_exclusions",
            definition=(
                "type: boolean\nscope: proprietaire\n"
                f"question: >-\n  L'activité est-elle hors des catégories exclues : {liste} ?\n"
            ),
        )
        self.assertIn("ERREUR", sortie)
        self.assertIn("help", sortie)
        self.assertIn("manual_check", sortie)

    def test_polarite_cle_question_opposee_refusee(self):
        """Le pire des défauts : chaque prédicat dirait l'inverse de la source."""
        sortie = self.proposer(
            fact_id="demande_eligible_france_agrimer",
            definition=(
                "type: boolean\nscope: projet\n"
                "question: La demande est-elle non éligible aux aides France AgriMer ?\n"
            ),
        )
        self.assertIn("ERREUR", sortie)
        self.assertIn("polarité", sortie.lower())

    def test_promesse_refusee(self):
        """43 faits `s_engage_*` retypés à la main le 2026-09-22 : ils ne renaissent plus."""
        for fact_id, question in (
            ("s_engage_ouverture_journees_patrimoine", "Ouvrirez-vous le lieu ?"),
            ("ouverture_journees_patrimoine", "Vous engagez-vous à ouvrir le lieu aux JEP ?"),
            ("mention_financeur", "Acceptez-vous de mentionner le soutien du Département ?"),
        ):
            with self.subTest(fact_id=fact_id):
                sortie = self.proposer(
                    fact_id=fact_id,
                    definition=f"type: boolean\nscope: projet\nquestion: {question}\n",
                )
                self.assertIn("ERREUR", sortie)
                self.assertIn("PROMESSE", sortie)
                self.assertIn("effect: info", sortie)

    def test_un_critere_nest_pas_une_promesse(self):
        sortie = self.proposer(
            fact_id="monument_accueille_visiteurs",
            definition="type: boolean\nscope: monument\nquestion: Le lieu est-il ouvert au public ?\n",
        )
        self.assertNotIn("PROMESSE", sortie)

    def test_aucun_refus_de_forme_nest_muet(self):
        """Un refus qui ne dit pas quoi écrire pousse à contourner le libellé."""
        for fact_id, definition in (
            (
                "logement_plus_15_ans",
                "type: boolean\nscope: monument\nquestion: Le logement a-t-il plus de 15 ans ?\n",
            ),
            (
                "demande_eligible_france_agrimer",
                "type: boolean\nscope: projet\n"
                "question: La demande est-elle non éligible aux aides France AgriMer ?\n",
            ),
        ):
            with self.subTest(fact_id=fact_id):
                sortie = self.proposer(fact_id=fact_id, definition=definition)
                self.assertIn("ERREUR", sortie)
                self.assertGreater(len(sortie), 300, "un refus doit orienter, pas buter")


class TestRecherche(unittest.TestCase):
    def test_mord_sur_lid_la_question_et_les_options(self):
        self.assertIn("accord_abf", faits.rechercher(FACTS, {}, "architecte bâtiments"))
        self.assertIn("accord_abf", faits.rechercher(FACTS, {}, "en_cours"))
        self.assertIn("monument_ouvert_au_public", faits.rechercher(FACTS, {}, "ouvert public"))

    def test_classe_par_nombre_de_mots_retrouves(self):
        sortie = faits.rechercher(FACTS, {}, "public monument ouvert")
        self.assertLess(
            sortie.index("monument_ouvert_au_public"),
            sortie.index("accord_abf") if "accord_abf" in sortie else len(sortie),
        )

    def test_scope_filtre(self):
        self.assertIn("Aucun fait", faits.rechercher(FACTS, {}, "architecte", scope="monument"))

    def test_faits_en_attente_marques(self):
        pending = {
            "jardin_remarquable": FactDef(
                type="boolean", scope="monument", question="Jardin remarquable ?"
            )
        }
        self.assertIn("⏳", faits.rechercher(FACTS, pending, "jardin remarquable"))

    def test_sans_resultat_oriente_vers_la_proposition(self):
        self.assertIn("proposer_fait", faits.rechercher(FACTS, {}, "zorglub"))


class TestDetail(unittest.TestCase):
    def test_rend_le_yaml_du_fait(self):
        sortie = faits.detail(FACTS, {}, "accord_abf")
        self.assertIn("enum", sortie)
        self.assertIn("obtenu", sortie)

    def test_fait_inconnu(self):
        self.assertIn("Fait inconnu", faits.detail(FACTS, {}, "zorglub"))


class TestProposition(BaseFaits):
    def test_ajout_nominal(self):
        sortie = self.proposer()
        self.assertNotIn("ERREUR", sortie)
        contenu = self.pending_path.read_text(encoding="utf-8")
        self.assertIn("# --- ex-aide ---", contenu)
        self.assertIn("Proposé par ingerer.py ex-aide (2026-09-06)", contenu)
        self.assertIn("Jardin remarquable", contenu)
        brut = charger_yaml(contenu)
        self.assertEqual(set(brut), {"jardin_remarquable"})

    def test_le_fait_est_visible_immediatement(self):
        """Le lint tourne dans le MÊME processus : le cache doit avoir été purgé."""
        self.proposer()
        self.assertIn("jardin_remarquable", load_pending_facts(self.pending_path))

    def test_collision_avec_facts_yaml_refusee(self):
        sortie = self.proposer(fact_id="monument_ouvert_au_public")
        self.assertIn("ERREUR", sortie)
        self.assertIn("existe déjà", sortie)
        self.assertEqual(self.pending_path.read_text(encoding="utf-8"), "")

    def test_collision_avec_un_fait_deja_propose_refusee(self):
        self.proposer()
        avant = self.pending_path.read_text(encoding="utf-8")
        sortie = self.proposer()
        self.assertIn("ERREUR", sortie)
        self.assertIn("déjà proposé", sortie)
        self.assertEqual(self.pending_path.read_text(encoding="utf-8"), avant)

    def test_identifiant_invalide_refuse(self):
        for mauvais in ("JardinRemarquable", "jardin-remarquable", "jardin remarquable", ""):
            self.assertIn("ERREUR", self.proposer(fact_id=mauvais), mauvais)
        self.assertEqual(self.pending_path.read_text(encoding="utf-8"), "")

    def test_justification_trop_courte_refusee(self):
        sortie = self.proposer(justif="parce que")
        self.assertIn("ERREUR", sortie)
        self.assertEqual(self.pending_path.read_text(encoding="utf-8"), "")

    def test_definition_invalide_refusee(self):
        sortie = self.proposer(definition="type: couleur\nscope: monument\nquestion: x ?\n")
        self.assertIn("ERREUR", sortie)
        self.assertEqual(self.pending_path.read_text(encoding="utf-8"), "")

    def test_enum_sans_options_refuse(self):
        sortie = self.proposer(definition="type: enum\nscope: monument\nquestion: Laquelle ?\n")
        self.assertIn("ERREUR", sortie)

    def test_definition_enveloppee_dans_son_id_acceptee(self):
        """Les modèles envoient tantôt la définition nue, tantôt `{id: …}`."""
        enveloppee = "jardin_remarquable:\n" + "\n".join(
            f"  {li}" for li in DEFINITION.strip().splitlines()
        )
        self.assertNotIn("ERREUR", self.proposer(definition=enveloppee))
        self.assertIn("jardin_remarquable", load_pending_facts(self.pending_path))

    def test_deux_faits_saccumulent(self):
        self.proposer()
        self.proposer(
            fact_id="jardin_labellise_ens",
            definition="type: boolean\nscope: monument\nquestion: Espace naturel sensible ?\n",
        )
        self.assertEqual(
            set(load_pending_facts(self.pending_path)),
            {"jardin_remarquable", "jardin_labellise_ens"},
        )


class TestProximite(BaseFaits):
    """L'avertissement de proximité : il oriente, il ne refuse jamais.

    Les deux populations mesurées sur le corpus réel se chevauchent de bout en
    bout (vrais doublons de 0,09 à 1,00, voisins légitimes de 0,27 à 0,89) : un
    seuil ne peut donc pas trancher. Ce que ces tests fixent, c'est qu'un fait
    proche FORCE la LECTURE — et qu'une proposition qui l'a lu passe.

    La citation ne suffit plus, depuis le 2026-09-21 : le garde cherchait la clé
    du voisin comme sous-chaîne de la justification, donc la recopier levait
    l'alerte sans avoir jamais ouvert sa définition. 27 paires de quasi-doublons
    sont entrées comme ça.
    """

    PROCHE = "type: boolean\nscope: monument\nquestion: Le monument est-il ouvert au public ?\n"
    # Une justification longue et sérieuse, qui ne NOMME simplement aucun des
    # faits proches : c'est exactement le geste qui a produit le passif.
    SANS_CITATION = (
        "Le règlement conditionne l'aide à l'ouverture du bien au public, et rien dans "
        "l'ontologie ne semble porter ce critère. Le fait est déclaratif, vérifié au "
        "dossier par la production du calendrier d'ouverture de l'année écoulée."
    )

    def proposer_proche(self, justif=SANS_CITATION, *, detailles=()):
        return self.proposer(
            fact_id="monument_ouvert_public",
            definition=self.PROCHE,
            justif=justif,
            detailles=detailles,
        )

    def test_fait_proche_non_lu_refuse(self):
        sortie = self.proposer_proche()
        self.assertIn("ERREUR", sortie)
        self.assertIn("monument_ouvert_au_public", sortie)
        self.assertEqual(self.pending_path.read_text(encoding="utf-8"), "")

    def test_lerreur_montre_la_question_du_fait_proche(self):
        """Le message doit permettre de trancher sans rappeler `detail_fait`."""
        sortie = self.proposer_proche()
        self.assertIn("Le monument est-il ouvert au public ?", sortie)
        self.assertIn("detail_fait", sortie)
        self.assertIn("pas encore lu", sortie)

    def test_fait_proche_lu_accepte(self):
        justif = (
            "Le fait proche `monument_ouvert_au_public` porte l'ouverture PERMANENTE du "
            "monument, alors que le règlement ne demande ici qu'une ouverture le jour de "
            "la manifestation : les deux se répondent « oui » et « non » indépendamment, "
            "et les fusionner rendrait le gate faux pour les monuments fermés à l'année."
        )
        sortie = self.proposer_proche(justif, detailles=("monument_ouvert_au_public",))
        self.assertNotIn("ERREUR", sortie)
        self.assertIn("monument_ouvert_public", load_pending_facts(self.pending_path))

    def test_citer_sans_avoir_lu_ne_suffit_plus(self):
        """Recopier une clé dans une phrase n'est pas l'avoir ouverte."""
        justif = (
            "Le fait proche `monument_ouvert_au_public` ne convient pas ici, car le "
            "règlement vise l'ouverture ponctuelle d'un jour de manifestation et non "
            "l'ouverture permanente qu'il mesure, ce qui rendrait le gate faux."
        )
        self.assertIn("ERREUR", self.proposer_proche(justif))

    def test_fait_lointain_inchange(self):
        """Un fait sans voisin passe sans avoir rien à citer."""
        self.assertNotIn("ERREUR", self.proposer())

    def test_la_proximite_voit_aussi_les_faits_deja_proposes(self):
        """Le passif vient surtout de là : un worker repropose ce qu'un autre a écrit."""
        self.proposer()
        sortie = self.proposer(
            fact_id="jardin_remarquable_v2",
            definition=DEFINITION,
            justif=JUSTIFICATION,
        )
        self.assertIn("ERREUR", sortie)
        self.assertIn("jardin_remarquable", sortie)


class TestRetrait(BaseFaits):
    """`retirer_fait` : le droit à l'erreur de l'agent, et ses deux gardes."""

    AUTRE = "type: boolean\nscope: monument\nquestion: Espace naturel sensible ?\n"
    JUSTIF_AUTRE = (
        "Le classement en Espace naturel sensible relève du département et ouvre des "
        "financements propres ; aucun fait de l'ontologie ne porte ce classement, qui ne "
        "se déduit ni de la protection au titre des monuments historiques ni d'un label."
    )

    def proposer_voisin(self):
        return self.proposer(
            fact_id="jardin_labellise_ens", definition=self.AUTRE, justif=self.JUSTIF_AUTRE
        )

    def retirer(self, fact_id="jardin_remarquable", proposes=("jardin_remarquable",)):
        return faits.retirer(self.atelier, fact_id, proposes=proposes)

    def test_retrait_preserve_le_voisin_et_sa_justification(self):
        """Le pendant de `test_deux_faits_saccumulent` : on retire l'un, l'autre reste ENTIER."""
        self.proposer()
        self.proposer_voisin()
        sortie = self.retirer()
        self.assertNotIn("ERREUR", sortie)
        contenu = self.pending_path.read_text(encoding="utf-8")
        self.assertEqual(set(charger_yaml(contenu)), {"jardin_labellise_ens"})
        # La justification commentée du voisin est ce que la relecture humaine
        # arbitre : un `safe_dump` l'aurait effacée sans bruit.
        self.assertIn("# --- ex-aide ---", contenu)
        self.assertIn("Espace naturel sensible", contenu)
        self.assertIn("Espace naturel sensible relève du département", contenu)
        self.assertNotIn("Jardin remarquable", contenu)

    def test_retrait_du_dernier_fait_vide_le_fichier(self):
        self.proposer()
        self.assertNotIn("ERREUR", self.retirer())
        self.assertEqual(self.pending_path.read_text(encoding="utf-8"), "")
        self.assertEqual(load_pending_facts(self.pending_path), {})

    def test_retrait_du_premier_preserve_le_second(self):
        self.proposer()
        self.proposer_voisin()
        self.assertNotIn(
            "ERREUR", self.retirer("jardin_labellise_ens", proposes=("jardin_labellise_ens",))
        )
        self.assertEqual(set(load_pending_facts(self.pending_path)), {"jardin_remarquable"})

    def test_fait_dun_autre_run_refuse(self):
        """Sans cette garde, un worker parallèle effacerait le fait d'un autre."""
        self.proposer()
        avant = self.pending_path.read_text(encoding="utf-8")
        sortie = self.retirer(proposes=())
        self.assertIn("ERREUR", sortie)
        self.assertIn("pas été proposé par cette ingestion", sortie)
        self.assertEqual(self.pending_path.read_text(encoding="utf-8"), avant)

    def test_fait_encore_reference_refuse(self):
        self.proposer()
        avant = self.pending_path.read_text(encoding="utf-8")
        self.atelier.aides_dir.mkdir(parents=True, exist_ok=True)
        (self.atelier.aides_dir / "ex-aide.yaml").write_text(
            "conditions:\n  - id: c1\n    fact: jardin_remarquable\n", encoding="utf-8"
        )
        sortie = self.retirer()
        self.assertIn("ERREUR", sortie)
        self.assertIn("ex-aide", sortie)
        self.assertEqual(self.pending_path.read_text(encoding="utf-8"), avant)

    def test_fait_absent_du_fichier_refuse(self):
        sortie = self.retirer("zorglub", proposes=("zorglub",))
        self.assertIn("ERREUR", sortie)
        self.assertIn("rien à retirer", sortie)

    def test_un_fait_approuve_ne_se_retire_pas(self):
        """`facts.yaml` n'est pas de ce ressort : l'approbation est humaine."""
        sortie = self.retirer("monument_ouvert_au_public", proposes=("monument_ouvert_au_public",))
        self.assertIn("ERREUR", sortie)

    def test_le_retrait_est_visible_immediatement(self):
        """Le lint tourne dans le MÊME processus : le cache doit avoir été purgé."""
        self.proposer()
        self.retirer()
        self.assertNotIn("jardin_remarquable", load_pending_facts(self.pending_path))

    def test_retrait_puis_reproposition(self):
        """Le geste que l'outil existe pour permettre : corriger, plutôt qu'empiler."""
        self.proposer()
        self.retirer()
        self.assertNotIn(
            "ERREUR",
            self.proposer(
                fact_id="jardin_remarquable",
                definition=DEFINITION.replace("boolean", "boolean"),
            ),
        )


if __name__ == "__main__":
    unittest.main()
