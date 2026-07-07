"""
Schéma Pydantic des données d'aides versionnées en YAML.

Source de vérité : backend/data/
  - facts.yaml        — ontologie des faits (questions canoniques typées)
  - aides/<slug>.yaml — une aide par fichier

Workflow :
  éditer le YAML → `uv run python scripts/lint_aides_data.py` → commit →
  `uv run python scripts/load_aides_yaml.py` (upsert Supabase par slug).

On ne modifie JAMAIS une aide directement en base : git est la source de
vérité, le loader écraserait la modification au prochain run.

Typologie des conditions (`kind`) :
  - untyped        : pas encore typée (état transitoire post-conversion ; le
                     linter compte la couverture, l'ingestion les résorbe)
  - auto           : décidable depuis les données structurées (monument,
                     commune, projet) → `field` + `predicate`
  - user_fact      : nécessite une réponse du propriétaire → `fact` (clé de
                     l'ontologie) + `predicate` évalué sur sa réponse
  - discretionary  : appréciation du financeur — jamais de question, affichée
                     comme point de vigilance pour le dossier
  - info           : modalité ou information (taux, versement…), pas une
                     condition d'éligibilité
  - manual_check   : irréductible — affichée « à vérifier auprès du
                     financeur » avec la citation source

Effet d'une condition (`effect`) :
  - gate       : dirimante — non satisfaite ⇒ aide refusée
  - modulateur : module le taux ou le montant, ne refuse jamais l'aide
  - info       : aucune incidence sur l'éligibilité

`gate` est réservé aux kinds que le moteur évalue ou que l'utilisateur peut
vérifier (auto, user_fact, manual_check, untyped). Une condition `info` est
toujours d'effect `info` ; une `discretionary` est `info` par défaut,
`modulateur` si le financeur module son taux dessus — jamais `gate`.
"""

from __future__ import annotations

from datetime import date
from functools import cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator

from labels import (
    DEPARTEMENT_LABELS,
    ETAT_LABELS,
    OWNERSHIP_LABELS,
    PROTECTION_LABELS,
    REGION_LABELS,
    TRAVAUX_LABELS,
)

DATA_DIR = Path(__file__).resolve().parent / "data"
AIDES_DIR = DATA_DIR / "aides"
FACTS_FILE = DATA_DIR / "facts.yaml"
# Faits proposés par l'agent de typage, en attente d'approbation humaine.
# L'approbation = déplacer l'entrée vers facts.yaml (cf. data/TYPING.md).
FACTS_PENDING_FILE = DATA_DIR / "facts_pending.yaml"

# Alignés sur les CHECK constraints d'aides_v3.
CATEGORIES = (
    "etat_drac",
    "departement",
    "fiscalite",
    "europe",
    "mecenat",
    "fondation",
    "region",
    "autre",
)
TYPES = (
    "label",
    "appel_a_projets",
    "exoneration",
    "mecenat",
    "souscription",
    "pret",
    "deduction_fiscale",
    "subvention",
)
# Finalités de l'aide — colonne aides_v3.raison (text[] NOT NULL + CHECK en base).
RAISONS = (
    "etude_ingenierie",
    "restauration_travaux",
    "valorisation_rayonnement",
    "fiscalite",
)

# Rôle d'une aide dans un PLAN DE FINANCEMENT — dérivé de `type` (pas de champ
# YAML : `type` suffit à le déterminer). Le plan traite chaque rôle autrement :
#   - subvention : couvre le coût (cash, soumise au plafond d'aides publiques)
#   - mecenat    : couvre le coût mais montant incertain (collecte/don)
#   - pret       : finance mais se REMBOURSE — n'allège pas le coût net
#   - fiscal     : réduit l'impôt, levier séparé (souvent étalé sur N années)
#   - label      : bénéfice indirect, pas d'apport monétaire direct
ROLE_BY_TYPE: dict[str, str] = {
    "subvention": "subvention",
    "appel_a_projets": "subvention",
    "souscription": "mecenat",
    "mecenat": "mecenat",
    "pret": "pret",
    "deduction_fiscale": "fiscal",
    "exoneration": "fiscal",
    "label": "label",
}


# ---------------------------------------------------------------------------
# Prédicats
# ---------------------------------------------------------------------------

# Un prédicat est un dict à clé unique : {"gte": 40}, {"eq": true},
# {"in": ["a", "b"]}, {"contains": "petite_cite_de_caractere"},
# {"any_of": [{...}, {...}]}. `contains` teste l'appartenance d'une valeur à
# un champ liste (labels de commune, travaux…).
COMPARISON_OPS = frozenset({"eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in", "contains"})
COMBINATOR_OPS = frozenset({"any_of", "all_of"})


class Predicate(RootModel[dict[str, Any]]):
    @model_validator(mode="after")
    def _check(self) -> Predicate:
        if not isinstance(self.root, dict) or len(self.root) != 1:
            raise ValueError(f"un prédicat a exactement une clé (opérateur), reçu : {self.root!r}")
        op, val = next(iter(self.root.items()))
        if op in COMBINATOR_OPS:
            if not isinstance(val, list) or not val:
                raise ValueError(f"« {op} » attend une liste non vide de prédicats")
            self.root = {op: [Predicate.model_validate(p).root for p in val]}
        elif op in COMPARISON_OPS:
            if op in ("in", "not_in") and not isinstance(val, list):
                raise ValueError(f"« {op} » attend une liste de valeurs")
        else:
            raise ValueError(f"opérateur de prédicat inconnu : « {op} »")
        return self


def evaluate_predicate(predicate: dict[str, Any], value: Any) -> bool | None:
    """Évalue un prédicat sur une valeur. Retourne None si la valeur est inconnue.

    C'est l'embryon du moteur d'évaluation déterministe : le diagnostic
    remplacera l'appel LLM par cette fonction appliquée aux faits connus.
    """
    op, ref = next(iter(predicate.items()))
    if op in COMBINATOR_OPS:
        # Logique de Kleene à trois valeurs : un seul True établit un any_of et
        # un seul False réfute un all_of, même si d'autres branches restent
        # inconnues (None). Aujourd'hui les branches partagent la même valeur
        # (donc toutes connues ou toutes None), mais cet invariant tient aussi
        # le jour où un combinateur mélangera plusieurs sources.
        results = [evaluate_predicate(p, value) for p in ref]
        if op == "any_of":
            if any(r is True for r in results):
                return True
            return False if all(r is False for r in results) else None
        if any(r is False for r in results):
            return False
        return True if all(r is True for r in results) else None
    if value is None:
        return None
    match op:
        case "eq":
            return value == ref
        case "neq":
            return value != ref
        case "gt":
            return value > ref
        case "gte":
            return value >= ref
        case "lt":
            return value < ref
        case "lte":
            return value <= ref
        case "in":
            return value in ref
        case "not_in":
            return value not in ref
        case "contains":
            return isinstance(value, (list, tuple, set)) and ref in value
    raise ValueError(f"opérateur inconnu : {op}")


# ---------------------------------------------------------------------------
# Ontologie des faits
# ---------------------------------------------------------------------------


class FactOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9_]+$")
    label: str
    # True pour les réponses du type « pas encore choisi » : le moteur traite
    # alors le fait comme inconnu (None) — la condition reste une incertitude
    # au lieu d'éliminer l'aide. Fail-closed, jamais fail-open.
    unknown: bool = False


class FactDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["boolean", "integer", "number", "enum"]
    # Où la réponse persiste : sur le monument, le projet de travaux, ou le
    # propriétaire. Détermine la réutilisation entre diagnostics.
    scope: Literal["monument", "projet", "proprietaire"]
    question: str
    options: list[FactOption] | None = None
    unit: str | None = None
    help: str | None = None
    # Champ de donnée permettant de pré-remplir la réponse sans question
    # (ex : merimee.siecle_construction pour annee_construction).
    auto_source: str | None = None

    @model_validator(mode="after")
    def _options_iff_enum(self) -> FactDef:
        if self.type == "enum" and not self.options:
            raise ValueError("un fait de type enum doit définir `options`")
        if self.type != "enum" and self.options:
            raise ValueError("`options` est réservé aux faits de type enum")
        return self


# Opérateurs autorisés par type de fait (vérifié par le linter).
OPS_BY_FACT_TYPE: dict[str, frozenset[str]] = {
    "boolean": frozenset({"eq", "neq"}),
    "integer": frozenset({"eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in"}),
    "number": frozenset({"eq", "neq", "gt", "gte", "lt", "lte"}),
    "enum": frozenset({"eq", "neq", "in", "not_in"}),
}


# ---------------------------------------------------------------------------
# Champs structurés (kind: auto, applies_if.field, auto_source)
# ---------------------------------------------------------------------------

# Registre des chemins évaluables sans question. C'est le CONTRAT du futur
# moteur d'évaluation : tout chemin listé ici devra être fourni dans son
# contexte (monument, commune enrichie). Un chemin hors registre est une
# erreur de lint — un typo (`monument.protecion`) rendrait sinon None pour
# toujours, c.-à-d. une incertitude silencieuse jamais résolue.
#
# `commune.programmes` et `commune.eligible_detr` n'ont pas encore de colonne
# dans `communes` : ce sont des données d'enrichissement à câbler avant
# d'activer le moteur sur les aides qui les référencent (Denormandie, DETR).
FIELD_REGISTRY: dict[str, dict] = {
    "monument.protection": {"type": "enum", "values": frozenset(PROTECTION_LABELS)},
    "monument.proprietaire": {"type": "enum", "values": frozenset(OWNERSHIP_LABELS)},
    "monument.etat_conservation": {"type": "enum", "values": frozenset(ETAT_LABELS)},
    "monument.region": {"type": "enum", "values": frozenset(REGION_LABELS)},
    "monument.departement_num": {"type": "enum", "values": frozenset(DEPARTEMENT_LABELS)},
    "monument.travaux_envisages": {"type": "list", "values": frozenset(TRAVAUX_LABELS)},
    # Texte brut Mérimée (ex. « 15e siècle ») — sert d'auto_source, la
    # conversion vers un entier reste à écrire côté moteur.
    "monument.siecle_construction": {"type": "string"},
    "commune.population": {"type": "integer"},
    "commune.programmes": {"type": "list"},
    "commune.eligible_detr": {"type": "boolean"},
    # SIREN de l'EPCI d'appartenance de la commune (référentiel BANATIC) —
    # enrichissement à câbler : pas encore de colonne dans `communes`. Permet
    # les aides intercommunales (ex. CC Moret Seine et Loing = 247700032).
    "commune.epci": {"type": "string"},
}

OPS_BY_FIELD_TYPE: dict[str, frozenset[str]] = {
    **OPS_BY_FACT_TYPE,
    "string": frozenset({"eq", "neq", "in", "not_in"}),
    "list": frozenset({"contains"}),
}


# ---------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------

ConditionKind = Literal["untyped", "auto", "user_fact", "discretionary", "info", "manual_check"]
ConditionEffect = Literal["gate", "modulateur", "info"]


class AppliesIf(BaseModel):
    """Clause d'applicabilité : la condition ne concerne qu'un sous-ensemble
    de profils. Cible soit un champ structuré (`field` — ex. « autofinancement
    20 % » seulement pour les collectivités), soit un fait utilisateur (`fact`
    — ex. « engagement de location 9 ans » seulement si l'usage prévu est la
    location) : exactement l'un des deux. Prédicat faux ⇒ condition ignorée ;
    prédicat inconnu ⇒ la condition reste potentiellement applicable
    (fail-closed)."""

    model_config = ConfigDict(extra="forbid")

    field: str | None = None
    fact: str | None = None
    predicate: Predicate

    @model_validator(mode="after")
    def _exactly_one_target(self) -> AppliesIf:
        if bool(self.field) == bool(self.fact):
            raise ValueError("applies_if cible exactement un de `field` ou `fact`")
        return self


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9-]+$")
    # Texte de la condition, contenu inchangé par rapport à la source.
    text: str
    kind: ConditionKind = "untyped"
    effect: ConditionEffect = "gate"
    # kind=user_fact : clé dans facts.yaml.
    fact: str | None = None
    # kind=auto : chemin du champ structuré (monument.*, commune.*, projet.*).
    field: str | None = None
    predicate: Predicate | None = None
    # La condition ne s'applique qu'aux profils satisfaisant cette clause.
    applies_if: AppliesIf | None = None
    # Gate « souple » : si le prédicat est FAUX, l'échec n'est PAS dirimant — il
    # dégrade en incertitude (« à vérifier auprès du financeur ») au lieu de
    # refuser l'aide. Pour les conditions à échappatoire (« sauf dérogation »,
    # « sauf demande motivée »…). Ex. non-commencement des travaux : « non
    # commencés » valide, « commencés » n'élimine pas (un démarrage anticipé
    # motivé reste possible). N'a de sens que sur un gate auto/user_fact.
    derogation_possible: bool = False
    # Citation verbatim du règlement source (remplie à l'ingestion, étape 2).
    quote: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _coherence(self) -> Condition:
        if self.kind == "user_fact":
            if not self.fact or self.predicate is None:
                raise ValueError(f"[{self.id}] user_fact exige `fact` et `predicate`")
            if self.field:
                raise ValueError(f"[{self.id}] `field` est réservé à kind=auto")
        elif self.kind == "auto":
            if not self.field or self.predicate is None:
                raise ValueError(f"[{self.id}] auto exige `field` et `predicate`")
            if self.fact:
                raise ValueError(f"[{self.id}] `fact` est réservé à kind=user_fact")
        else:
            if self.fact or self.field or self.predicate is not None:
                raise ValueError(
                    f"[{self.id}] kind={self.kind} n'admet ni fact, ni field, ni predicate"
                )
        # `effect` n'a de sens que pour les conditions évaluables/vérifiables.
        # info et discretionary ne sont jamais évaluées par le moteur : `gate`
        # y est interdit, et l'effect par défaut (gate) est coercé en info au
        # lieu de laisser un défaut silencieusement faux dans les stats.
        if self.kind == "info":
            if "effect" not in self.model_fields_set:
                self.effect = "info"
            elif self.effect != "info":
                raise ValueError(
                    f"[{self.id}] une condition info n'a aucune incidence — effect doit être info"
                )
        elif self.kind == "discretionary":
            if "effect" not in self.model_fields_set:
                self.effect = "info"
            elif self.effect == "gate":
                raise ValueError(
                    f"[{self.id}] une condition discretionary n'est jamais évaluée par le "
                    "moteur — effect gate interdit (info ou modulateur)"
                )
        if self.derogation_possible and not (
            self.kind in ("auto", "user_fact") and self.effect == "gate"
        ):
            raise ValueError(
                f"[{self.id}] derogation_possible n'a de sens que sur un gate auto/user_fact"
            )
        return self


# ---------------------------------------------------------------------------
# Aide
# ---------------------------------------------------------------------------


def _codes_validator(allowed, dimension: str):
    """`allowed` : tout conteneur supportant `in` (dict de labels, tuple…)."""

    def _check(values: list[str]) -> list[str]:
        unknown = [v for v in values if v not in allowed]
        if unknown:
            raise ValueError(f"codes {dimension} inconnus : {unknown}")
        return values

    return _check


class HardFilters(BaseModel):
    """Restrictions structurées. Liste vide = pas de restriction (sémantique DB)."""

    model_config = ConfigDict(extra="forbid")

    protections: list[str] = []
    proprietaires: list[str] = []
    travaux: list[str] = []
    regions: list[str] = []
    departements: list[str] = []
    etats_conservation: list[str] = []
    commune_max_population: int | None = None

    _v_prot = field_validator("protections")(_codes_validator(PROTECTION_LABELS, "protection"))
    _v_prop = field_validator("proprietaires")(_codes_validator(OWNERSHIP_LABELS, "propriétaire"))
    _v_trav = field_validator("travaux")(_codes_validator(TRAVAUX_LABELS, "travaux"))
    _v_reg = field_validator("regions")(_codes_validator(REGION_LABELS, "région"))
    _v_dep = field_validator("departements")(_codes_validator(DEPARTEMENT_LABELS, "département"))
    _v_etat = field_validator("etats_conservation")(_codes_validator(ETAT_LABELS, "état"))


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url_officielle: str | None = None
    formulaire_url: str | None = None
    # Date de dernière vérification humaine contre la source officielle.
    verified_at: date | None = None
    # Chemin du snapshot archivé de la source (sources/<slug>/<date>.md).
    snapshot: str | None = None


class Financement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    montant_min: float | None = None
    montant_max: float | None = None
    taux_min: float | None = None
    taux_max: float | None = None
    plancher: float | None = None
    base_ttc: bool = False
    # PLAN DE FINANCEMENT (MVP) : assiette des dépenses éligibles — le taux ne
    # s'applique presque jamais à la totalité du coût (ex. « parties protégées
    # uniquement », « travaux énergétiques »). Texte fidèle à la source, cité
    # dans une condition ; le plan s'en sert pour ne pas surestimer l'apport.
    assiette: str | None = None


class Cumul(BaseModel):
    """Règles de cumul pour le plan de financement (MVP).

    Le cumul se modélise par RÈGLE, pas par paires d'aides : les sources
    énoncent « cumulable avec les aides publiques dans la limite de X % »
    plutôt que des couples. Les exclusions nommées (rares) sont listées en clair.
    """

    model_config = ConfigDict(extra="forbid")

    # Plafond d'aides publiques cumulées, en % du coût (souvent 80, parfois 100).
    plafond_public_pct: float | None = None
    # Dispositif exclusif si False (ne se cumule avec rien).
    cumulable: bool = True
    # Dispositifs explicitement non cumulables : slug si connu, sinon nom/
    # catégorie tels que cités par la source (ex. "maprimerenov", "DETR").
    exclusions: list[str] = []


class Calendrier(BaseModel):
    model_config = ConfigDict(extra="forbid")

    permanent: bool = True
    date_ouverture: date | None = None
    date_limite: date | None = None
    delai_instruction: str | None = None


class Flags(BaseModel):
    """Booléens dénormalisés hérités des seeds — redondants avec les
    conditions typées, conservés le temps de la transition puis à supprimer."""

    model_config = ConfigDict(extra="forbid")

    architecte_requis: bool = False
    cofinancement_requis: bool = False


class Document(BaseModel):
    """Pièce du dossier à constituer pour l'aide.

    `url` : lien de téléchargement / remplissage trouvé sur la page de l'aide
    (formulaire Cerfa, modèle de plan de financement, notice…) — évite à
    l'utilisateur de chercher la pièce. `obligatoire=False` + `note` servent à
    distinguer les pièces conditionnelles (« si propriétaire public ») pour ne
    pas remplir des documents inutiles.

    Rétrocompat : une simple chaîne en YAML est coercée en `{nom: <chaîne>}`.
    """

    model_config = ConfigDict(extra="forbid")

    nom: str
    url: str | None = None
    obligatoire: bool = True
    note: str | None = None


class Aide(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    nom: str
    nom_court: str | None = None
    organisme: str
    categorie: Literal[CATEGORIES]  # type: ignore[valid-type]
    type: Literal[TYPES]  # type: ignore[valid-type]
    # Finalité(s) de l'aide (colonne aides_v3.raison, NOT NULL en base).
    # Optionnel en YAML pendant la transition : liste vide ⇒ le loader
    # préserve la valeur déjà en base (voir load_aides_yaml.aide_to_row).
    raison: list[str] = []
    description: str
    description_longue: str | None = None
    source: Source = Source()
    financement: Financement = Financement()
    cumul: Cumul = Cumul()
    calendrier: Calendrier = Calendrier()
    hard_filters: HardFilters = HardFilters()
    conditions: list[Condition] = []
    flags: Flags = Flags()
    # Étapes de constitution du dossier (prose numérotée, fidèle à la source).
    demarche: str | None = None
    # Pièces du dossier — chaque pièce porte idéalement son lien (cf. Document).
    documents_requis: list[Document] = []
    tags: list[str] = []

    _v_raison = field_validator("raison")(_codes_validator(RAISONS, "raison"))

    @field_validator("documents_requis", mode="before")
    @classmethod
    def _coerce_documents(cls, v):
        """Rétrocompat : `documents_requis: [str, ...]` → `[{nom: str}, ...]`."""
        if not isinstance(v, list):
            return v
        return [{"nom": d} if isinstance(d, str) else d for d in v]

    @model_validator(mode="after")
    def _unique_condition_ids(self) -> Aide:
        seen: set[str] = set()
        for c in self.conditions:
            if c.id in seen:
                raise ValueError(f"id de condition en doublon : {c.id}")
            seen.add(c.id)
        return self


# ---------------------------------------------------------------------------
# Chargement
# ---------------------------------------------------------------------------


# Les trois loaders sont mis en cache : les YAML ne changent qu'au déploiement
# (git est la source de vérité, cf. docstring du module) et chaque appel non
# caché reparse ~130 fichiers (~0,7 s de CPU pur — sérialisé par le GIL quand
# le dashboard lance un diagnostic par monument). Corollaire : les structures
# retournées sont PARTAGÉES entre requêtes — ne jamais les modifier en place.


@cache
def load_facts(path: Path = FACTS_FILE) -> dict[str, FactDef]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {key: FactDef.model_validate(val) for key, val in raw.items()}


@cache
def load_pending_facts(path: Path = FACTS_PENDING_FILE) -> dict[str, FactDef]:
    """Faits en attente d'approbation. Fichier absent ou vide ⇒ {}."""
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {key: FactDef.model_validate(val) for key, val in raw.items()}


def load_aide(path: Path) -> Aide:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    aide = Aide.model_validate(raw)
    if aide.slug != path.stem:
        raise ValueError(f"slug « {aide.slug} » ≠ nom de fichier « {path.stem} »")
    return aide


@cache
def load_all_aides(directory: Path = AIDES_DIR) -> dict[str, Aide]:
    return {p.stem: load_aide(p) for p in sorted(directory.glob("*.yaml"))}
