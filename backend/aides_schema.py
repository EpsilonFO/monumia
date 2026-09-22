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
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    ValidationError,
    field_validator,
    model_validator,
)

from labels import (
    DEPARTEMENT_LABELS,
    ETAT_LABELS,
    FAMILLES_LABELS,
    OWNERSHIP_LABELS,
    PROTECTION_LABELS,
    REGION_LABELS,
    TRAVAUX_LABELS,
)
from pieces_schema import load_pieces

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

# Familles thématiques — colonne aides_v3.familles (text[] NOT NULL + CHECK).
# Liste fermée dérivée du référentiel de libellés : une seule définition des
# codes, trois lieux où elle doit rester d'accord (ici, le CHECK SQL de la
# migration, et `FAMILLE_OPTIONS` côté front), ce que des tests vérifient.
FAMILLES = tuple(FAMILLES_LABELS)

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


class MultiValue(tuple):
    """Valeur d'un fait à choix MULTIPLE (`multi_enum`) : les options cochées.

    Un prédicat est satisfait dès qu'UNE des valeurs cochées le satisfait, et
    réfuté seulement si TOUTES le réfutent (sémantique existentielle). C'est ce
    que veut dire cocher plusieurs cases : « l'une de ces entités déposera la
    demande », « le bâtiment a ces usages ». Un règlement réservé aux
    associations reste donc ouvert à qui a coché « association » + « personne
    physique » — le dossier passera par l'association.

    Le tri de la sélection ne change rien au résultat (any/all), et une
    sélection vide vaut fait inconnu (None), jamais faux.
    """

    __slots__ = ()


class RangeValue(tuple):
    """Valeur numérique connue à un INTERVALLE près : (borne basse, borne haute).

    Sert aux faits déduits de la fiche plutôt que demandés : « 15e siècle » ne
    donne pas une année mais l'intervalle 1401-1500. Un prédicat n'est tranché
    que si les DEUX bornes s'accordent (`lt: 1800` est vrai sur tout le 15e
    siècle) ; sinon la valeur reste indéterminée et la question est posée.
    Sémantique universelle, à l'inverse du MultiValue existentiel.

    Seuls les opérateurs de seuil (gt/gte/lt/lte) sont conclus aux bornes : ils
    sont monotones, donc l'accord des bornes vaut pour tout l'intervalle. Un
    `eq` dont les deux bornes sont fausses pourrait, lui, être vrai au milieu —
    il rend None plutôt qu'un faux « non » qui éliminerait l'aide à tort.
    """

    __slots__ = ()


# Opérateurs monotones : leur valeur de vérité ne change au plus qu'une fois sur
# un intervalle croissant, d'où la conclusion aux bornes (cf. RangeValue).
MONOTONE_OPS = frozenset({"gt", "gte", "lt", "lte"})


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


def _evaluate_over_range(op: str, ref: Any, value: RangeValue) -> bool | None:
    """Évalue un opérateur de comparaison sur un intervalle (cf. RangeValue)."""
    if not value:
        return None
    basse, haute = value[0], value[-1]
    if basse == haute:
        return evaluate_predicate({op: ref}, basse)
    if op not in MONOTONE_OPS:
        return None
    bas = evaluate_predicate({op: ref}, basse)
    haut = evaluate_predicate({op: ref}, haute)
    return bas if bas is haut else None


def evaluate_predicate(predicate: dict[str, Any], value: Any) -> bool | None:
    """Évalue un prédicat sur une valeur. Retourne None si la valeur est inconnue.

    C'est l'embryon du moteur d'évaluation déterministe : le diagnostic
    remplacera l'appel LLM par cette fonction appliquée aux faits connus.
    """
    # Fait à choix multiple : on distribue le prédicat ENTIER sur chaque valeur
    # cochée (cf. MultiValue). Distribuer avant les combinateurs est équivalent
    # à le faire après — toutes les branches lisent la même valeur — et évite de
    # dupliquer la logique de Kleene.
    if isinstance(value, MultiValue):
        if not value:
            return None
        results = [evaluate_predicate(predicate, v) for v in value]
        if any(r is True for r in results):
            return True
        return False if all(r is False for r in results) else None
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
    if isinstance(value, RangeValue):
        return _evaluate_over_range(op, ref, value)
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


def predicate_leaves(predicate: dict) -> list[tuple[str, object]]:
    """Comparaisons FEUILLES d'un prédicat, combinateurs aplatis.

    `{"any_of": [{"eq": "a"}, {"in": ["b"]}]}` → `[("eq", "a"), ("in", ["b"])]`.
    Deux usages, et c'est pourquoi la fonction vit ici plutôt que dans l'un des
    deux : le linter vérifie que chaque valeur citée existe dans les options du
    fait, et l'administration du catalogue cherche l'inverse — quelles aides
    citent une option qu'on s'apprête à supprimer.
    """
    op, val = next(iter(predicate.items()))
    if op in COMBINATOR_OPS:
        return [leaf for p in val for leaf in predicate_leaves(p)]
    return [(op, val)]


# ---------------------------------------------------------------------------
# Ontologie des faits
# ---------------------------------------------------------------------------

# Faits à options : même déclaration, une seule réponse (`enum`) ou plusieurs
# (`multi_enum`).
ENUM_FACT_TYPES = frozenset({"enum", "multi_enum"})

# Le fait qui dit QUI dépose la demande. Nommé une seule fois : le lint, le
# script de proposition de gates et le worker d'ingestion le citent tous —
# `porteurs_concernes` n'a de sens que par rapport à ses options.
FAIT_PORTEUR = "statut_juridique_porteur"


class FactOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9_]+$")
    label: str
    # True pour les réponses du type « pas encore choisi » : le moteur traite
    # alors le fait comme inconnu (None) — la condition reste une incertitude
    # au lieu d'éliminer l'aide. Fail-closed, jamais fail-open.
    unknown: bool = False
    # Réservé aux faits `boolean` qui déclarent leurs options : valeur de vérité
    # que cette réponse envoie aux prédicats des aides. Permet d'offrir plus de
    # deux réponses à une question binaire (« oui », « non », « les deux ») sans
    # retyper un seul prédicat — ils restent `eq: true` / `eq: false`.
    #
    # `None` veut dire « ne tranche pas » : le fait reste inconnu, la condition
    # reste une incertitude, l'aide n'est JAMAIS écartée. C'est la convention
    # `None` déjà en vigueur dans `evaluate_predicate`, et elle rend la réponse
    # inoffensive par construction.
    #
    # Sur un `enum` / `multi_enum`, l'identifiant EST la valeur : le champ y est
    # interdit (cf. `_options_coherentes`).
    valeur: bool | None = None


# Le couple Oui/Non d'un fait `boolean` qui ne déclare RIEN. Défini une seule
# fois : le moteur (options du QCM, normalisation des réponses) et
# l'administration du catalogue (panneau d'édition des réponses) le lisent tous
# les deux — deux définitions dériveraient, et un « oui » qui ne vaut plus True
# est une élimination silencieuse.
OPTIONS_BOOLEEN_IMPLICITES: tuple[FactOption, ...] = (
    FactOption(id="oui", label="Oui", valeur=True),
    FactOption(id="non", label="Non", valeur=False),
)

# Types dont les réponses viennent de la DÉCLARATION du fait, donc éditables.
# Les tranches d'un `integer` / `number` sont fabriquées par le moteur depuis
# les seuils des prédicats : elles n'ont rien à faire dans le YAML.
TYPES_A_OPTIONS = ENUM_FACT_TYPES | {"boolean"}


class Levier(BaseModel):
    """Démarche accessible qui transforme un fait défavorable en fait favorable.

    Un gate en échec sur un fait porteur d'un levier ne refuse pas l'aide : il la
    rend « atteignable ». Répondre « non » à « avez-vous le label ? » ne doit pas
    faire disparaître silencieusement 500 k€ d'aides — le propriétaire doit voir
    la démarche, son organisme, son coût et son délai, puis décider.

    `resume` est la seule information obligatoire : une phrase qui dit ce qu'il y
    a à faire. Les autres champs enrichissent le plan d'action quand la source
    les donne ; on ne les invente pas.
    """

    model_config = ConfigDict(extra="forbid")

    resume: str
    # Comment s'y prendre concrètement (étapes, formulaire, interlocuteur).
    demarche: str | None = None
    # Qui délivre / instruit (Fondation du patrimoine, Région, DRAC…).
    organisme: str | None = None
    # Coût pour le propriétaire, texte fidèle à la source (« gratuit », « 2 % du
    # montant des travaux »…) — jamais un montant inventé.
    cout: str | None = None
    delai: str | None = None
    url: str | None = None


class AppliesIf(BaseModel):
    """Clause d'applicabilité : la condition ne concerne qu'un sous-ensemble
    de profils. Cible soit un champ structuré (`field` — ex. « autofinancement
    20 % » seulement pour les collectivités), soit un fait utilisateur (`fact`
    — ex. « engagement de location 9 ans » seulement si l'usage prévu est la
    location) : exactement l'un des deux. Prédicat faux ⇒ condition ignorée ;
    prédicat inconnu ⇒ la condition reste potentiellement applicable
    (fail-closed).

    Le même modèle porte la clause de PÉRIMÈTRE d'une aide entière
    (`Aide.applies_if`) et la DÉPENDANCE INTRINSÈQUE d'un fait
    (`FactDef.pertinent_si`), qui n'acceptent toutes deux qu'un `fact`.

    Déclarée avant `FactDef`, qui la référence : pydantic résout les
    annotations à la création de la classe."""

    model_config = ConfigDict(extra="forbid")

    field: str | None = None
    fact: str | None = None
    predicate: Predicate

    @model_validator(mode="after")
    def _exactly_one_target(self) -> AppliesIf:
        if bool(self.field) == bool(self.fact):
            raise ValueError("applies_if cible exactement un de `field` ou `fact`")
        return self


class FactDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # `multi_enum` = mêmes options qu'un enum, mais plusieurs cochables. À
    # réserver aux faits où le cumul est la réalité (usages d'un bâtiment,
    # entités susceptibles de déposer) : cf. MultiValue pour la sémantique.
    type: Literal["boolean", "integer", "number", "enum", "multi_enum"]
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
    # Fait ACTIONNABLE : une démarche permet de le rendre favorable. Les aides
    # bloquées uniquement là-dessus passent en statut « atteignable » au lieu
    # d'être refusées (cf. Levier).
    levier: Levier | None = None
    # Fait qu'AUCUNE condition ne doit gater : sa réponse ne trie rien (seuil
    # quasi universel) ou n'a pas de sens avant le montage du dossier. Le lint
    # refuse un gate dessus et `detail_fait` le dit à l'agent. Archétype :
    # autofinancement_pct — cf. TYPING « manual_check + effect: info ». Le
    # 2026-09-09, cinq aides d'un même lot ont regaté dessus : la règle ne
    # vivait que dans un commentaire YAML, que personne ne lit à la machine.
    hors_gate: bool = False
    # DÉPENDANCE INTRINSÈQUE du fait : la question n'a de sens que si cette
    # clause est vraie. « Depuis combien d'années les travaux sont-ils
    # achevés ? » ne veut rien dire tant que `etat_travaux` ne vaut pas
    # `acheves` — c'est une propriété du FAIT, pas de telle aide, et elle était
    # jusqu'ici recopiée en `applies_if` sur chaque condition qui le cite
    # (quatre fois pour ce fait, huit pour la location, sept pour le jardin,
    # neuf pour l'activité de restauration).
    #
    # Le moteur la reporte sur les conditions exactement comme il reporte le
    # périmètre d'une aide (cf. `_scoped_conditions`) : la clause PROPRE d'une
    # condition reste prioritaire, et le périmètre de l'aide passe avant celle
    # du fait — une condition ne porte qu'une clause, et le périmètre décide
    # d'abord si l'aide concerne l'utilisateur.
    #
    # Frontière : une clause qui ne vaut que pour UNE aide reste un `applies_if`
    # de condition. `pertinent_si` ne dit que ce qui est vrai du fait partout.
    pertinent_si: AppliesIf | None = None
    # Les seules catégories de porteur pour qui ce fait a un sens (ids d'options
    # de `statut_juridique_porteur`). Une aide qui gate un fait marqué n'est
    # ouverte qu'à ces porteurs-là : le MOTEUR l'applique désormais, elle n'a
    # plus à le redire (`conditions_porteur_derivees`).
    #
    # Le marqueur a été un garde-fou de LINT jusqu'au 2026-09-21 : l'aide devait
    # traduire sa puce « Bénéficiaires » en gate `in`, et le lint refusait
    # sinon. Ça a produit l'inverse de son but — quand la source ne nomme pas
    # ses bénéficiaires, le modèle INVENTAIT le gate pour satisfaire le lint,
    # le vérificateur le contestait à chaque passage, et le modèle le maintenait
    # « parce que le lint l'exige ». 580 aides sur 643 gatent le porteur, 60
    # conditions le disent dans leurs `notes`, 13 sont étiquetées « NON SOURCÉ ».
    #
    # Le marqueur est donc devenu EXÉCUTABLE, et la règle de lint un simple
    # relevé. Un gate porteur explicite garde la PRÉCÉDENCE : 138 aides du
    # corpus ont un gate plus large que le marqueur d'un fait qu'elles gatent
    # (31 admettent `public_commune`), et un cumul strict refuserait une commune
    # que la source admet.
    #
    # Ce n'est toujours PAS un `pertinent_si` : `_evaluate_aide` ignore une
    # condition dont la clause vaut False, si bien qu'un `pertinent_si`
    # désarmerait le gate PME au lieu de le faire échouer — un prêt PME
    # s'ouvrirait à une commune.
    #
    # L'existence des options est vérifiée par le LINT (`check_facts`), qui seul
    # dispose de l'ontologie entière — comme `pertinent_si` délègue l'existence
    # de sa cible. C'est une ERREUR CRITIQUE : une option inconnue dans le
    # marqueur refuserait désormais l'aide à tout le monde.
    porteurs_concernes: list[str] | None = None

    @model_validator(mode="after")
    def _porteurs_concernes_non_vide(self) -> FactDef:
        """Une liste vide dirait « aucun porteur », donc « question jamais posée ».

        C'est une faute de frappe, pas une intention : le marqueur s'omet quand
        le fait concerne tout le monde.
        """
        if self.porteurs_concernes is not None and not self.porteurs_concernes:
            raise ValueError("`porteurs_concernes` vide : omettre le champ plutôt que le vider")
        return self

    @model_validator(mode="after")
    def _pertinent_si_cible_un_fait(self) -> FactDef:
        """Trois restrictions, pour que la clause reste rendable et sûre.

        Un `field` n'a rien à faire ici : la dépendance d'une question porte sur
        une autre RÉPONSE, jamais sur une donnée de la fiche (qui relève de
        `hard_filters` ou d'un `applies_if` de condition). Un combinateur ne se
        rendrait pas à l'écran (`_depends_on` projette un `showForOptionIds`).
        Et un fait ne peut pas dépendre de lui-même.

        L'existence de la cible et la compatibilité du prédicat avec son type
        sont vérifiées par le LINT (`check_fact_predicate`), qui seul dispose de
        l'ontologie entière — mot pour mot la validation de l'administration.
        """
        clause = self.pertinent_si
        if clause is None:
            return self
        if clause.field:
            raise ValueError("`pertinent_si` cible un `fact`, jamais un `field`")
        if set(clause.predicate.root) & COMBINATOR_OPS:
            raise ValueError("`pertinent_si` attend un prédicat simple, sans combinateur")
        return self

    @model_validator(mode="after")
    def _options_coherentes(self) -> FactDef:
        """Cinq règles, dont la première porte toute la compatibilité ascendante.

        Un `boolean` PEUT déclarer ses options (pour offrir plus de deux
        réponses), mais il doit alors garder `oui`/`non` avec leurs valeurs
        d'origine : c'est ce qui rend l'ajout INERTE pour les réponses déjà
        persistées dans `projets.questionnaire`, et ce qui garantit que les deux
        valeurs de vérité restent atteignables — un booléen dont plus aucune
        réponse ne vaut `false` rendrait ses gates impossibles à échouer.
        """
        if self.type in ENUM_FACT_TYPES and not self.options:
            raise ValueError(f"un fait de type {self.type} doit définir `options`")
        # R5 — les tranches d'un fait numérique viennent des seuils des aides.
        if self.type not in TYPES_A_OPTIONS and self.options:
            raise ValueError("`options` est réservé aux faits enum / multi_enum / boolean")
        if not self.options:
            return self

        # R3 — identifiants uniques.
        ids = [o.id for o in self.options]
        doublons = sorted({i for i in ids if ids.count(i) > 1})
        if doublons:
            raise ValueError(f"identifiants d'options en double : {', '.join(doublons)}")

        for o in self.options:
            # R2 — sur un fait à choix, l'identifiant EST la valeur.
            if self.type in ENUM_FACT_TYPES and o.valeur is not None:
                raise ValueError(
                    f"`valeur` est réservé aux faits boolean ; option « {o.id} » "
                    f"d'un fait {self.type}"
                )
            # R4 — une réponse « je ne sais pas » ne tranche rien, par définition.
            if o.unknown and o.valeur is not None:
                raise ValueError(f"option « {o.id} » : `unknown: true` exclut `valeur`")

        if self.type == "boolean":
            # R1 — le couple implicite doit survivre à la déclaration.
            par_id = {o.id: o for o in self.options}
            for attendu in OPTIONS_BOOLEEN_IMPLICITES:
                presente = par_id.get(attendu.id)
                if presente is None:
                    raise ValueError(
                        f"un fait boolean qui déclare ses options doit garder "
                        f"« {attendu.id} » (les réponses déjà enregistrées en dépendent)"
                    )
                if presente.valeur is not attendu.valeur:
                    raise ValueError(
                        f"option « {attendu.id} » : valeur attendue {attendu.valeur}, "
                        f"reçu {presente.valeur}"
                    )
        return self


# Opérateurs autorisés par type de fait (vérifié par le linter).
OPS_BY_FACT_TYPE: dict[str, frozenset[str]] = {
    "boolean": frozenset({"eq", "neq"}),
    "integer": frozenset({"eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in"}),
    "number": frozenset({"eq", "neq", "gt", "gte", "lt", "lte"}),
    "enum": frozenset({"eq", "neq", "in", "not_in"}),
    # Un multi_enum se compare option par option (cf. MultiValue) : mêmes
    # opérateurs qu'un enum, `contains` n'a rien à y faire.
    "multi_enum": frozenset({"eq", "neq", "in", "not_in"}),
}


def check_fact_predicate(
    where: str,
    fact_key: str | None,
    predicate: Predicate,
    facts: dict[str, FactDef],
) -> list[str]:
    """Le prédicat est-il posable sur ce fait ? Liste d'erreurs, vide si tout va.

    Remontée du linter le 2026-09-13, pour la même raison que `predicate_leaves`
    avant elle : un SECOND usager au runtime. L'administration du catalogue
    laisse modifier le prédicat d'une condition depuis `/admin`, et la validation
    doit y être MOT POUR MOT celle du lint — deux validations qui divergent, et
    la surcouche accepterait ce que le YAML refuse.

    Le lint réimporte le nom, donc `veille_apply` et `veille_typage` continuent
    de faire `from lint_aides_data import check_fact_predicate` sans changement.
    Bénéfice de bord : la fonction gagne le type-check de pyright, qui n'analyse
    pas `scripts/`.
    """
    errors: list[str] = []
    fact = facts.get(fact_key or "")
    if fact is None:
        errors.append(f"{where}: fait inconnu « {fact_key} » (absent de facts.yaml)")
        return errors
    allowed_ops = OPS_BY_FACT_TYPE[fact.type]
    for op, val in predicate_leaves(predicate.root):
        if op not in allowed_ops:
            errors.append(f"{where}: opérateur « {op} » invalide pour un fait {fact.type}")
        if fact.type in ENUM_FACT_TYPES:
            option_ids = {o.id for o in fact.options or []}
            vals = val if isinstance(val, list) else [val]
            bad = [v for v in vals if v not in option_ids]
            if bad:
                errors.append(f"{where}: valeur(s) hors options du fait : {bad}")
        if fact.type == "boolean" and not isinstance(val, bool):
            errors.append(f"{where}: un fait boolean se compare à true/false, reçu {val!r}")
    return errors


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
    # Le nom du bien ne sert QU'À déduire des faits (auto_source) : « Église
    # Saint-Martin » répond d'avance à « est-ce une église ? ». Ne jamais typer
    # une condition d'aide dessus — un nom est saisi à la main, il ne prouve
    # rien à lui seul.
    "monument.nom": {"type": "string"},
    "monument.protection": {"type": "enum", "values": frozenset(PROTECTION_LABELS)},
    "monument.proprietaire": {"type": "enum", "values": frozenset(OWNERSHIP_LABELS)},
    "monument.etat_conservation": {"type": "enum", "values": frozenset(ETAT_LABELS)},
    "monument.region": {"type": "enum", "values": frozenset(REGION_LABELS)},
    "monument.departement_num": {"type": "enum", "values": frozenset(DEPARTEMENT_LABELS)},
    "monument.travaux_envisages": {"type": "list", "values": frozenset(TRAVAUX_LABELS)},
    # Texte brut Mérimée (ex. « 15e siècle ») — sert d'auto_source à
    # `annee_construction`, converti en intervalle d'années par le moteur
    # (cf. eligibility_engine._annee_depuis_siecle).
    "monument.siecle_construction": {"type": "string"},
    "commune.population": {"type": "integer"},
    "commune.programmes": {"type": "list"},
    "commune.eligible_detr": {"type": "boolean"},
    # Commune éligible au dispositif Denormandie (ACV / ORT / besoin de
    # réhabilitation de l'habitat — arrêté du 26 mars 2019, simulateur
    # service-public). Enrichissement à câbler : colonne booléenne à ajouter
    # dans `communes`.
    "commune.eligible_denormandie": {"type": "boolean"},
    # SIREN de l'EPCI d'appartenance de la commune (référentiel BANATIC), pour
    # les aides intercommunales (ex. CC Moret Seine et Loing = 247700032).
    # Colonne `communes.epci_siren`, alimentée par
    # scripts/seeds/seed_communes_epci.py.
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

    `piece_id` : rattachement au référentiel des pièces canoniques
    (data/pieces.yaml). C'est lui qui permet de reconnaître qu'un document déjà
    déposé pour une autre aide répond à cette demande. `None` est un état
    valide et fréquent : beaucoup de pièces sont propres à une seule aide et
    n'ont rien à réutiliser.

    Rétrocompat : une simple chaîne en YAML est coercée en `{nom: <chaîne>}`.
    """

    model_config = ConfigDict(extra="forbid")

    nom: str
    url: str | None = None
    obligatoire: bool = True
    note: str | None = None
    piece_id: str | None = None

    @field_validator("piece_id")
    @classmethod
    def _piece_connue(cls, v: str | None) -> str | None:
        if v is not None and v not in load_pieces():
            raise ValueError(f"pièce inconnue « {v} » (absente de data/pieces.yaml)")
        return v


class Aide(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    nom: str
    # Absent du YAML = `null` en base, or `aides_v3.nom_court` est NOT NULL :
    # c'est le LINT qui l'exige (cf. lint_aides_data), pas le schéma. Le garder
    # optionnel ici laisse les fixtures de test à ce qu'elles testent, et met le
    # refus là où le workflow l'attend — avant le commit, pas au chargement.
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
    # PÉRIMÈTRE de l'aide : elle ne concerne qu'un type de projet ou de porteur,
    # que seul l'utilisateur peut déclarer. À réserver aux aides d'un autre
    # métier que celui du demandeur type (festivals, compagnies, écoles d'art) :
    # sans elle, leurs conditions polluent le questionnaire de tout le monde
    # (« détenez-vous une licence d'entrepreneur de spectacles ? » pour un
    # ravalement de façade). La finalité `raison` ne suffit pas : elle n'a que
    # quatre valeurs et « valorisation_rayonnement » couvre 89 aides.
    #
    # Le fait est posé EN PREMIER dans le questionnaire (il débloque le plus
    # d'aides), et toutes les questions de l'aide s'y branchent. Réponse
    # négative ⇒ l'aide est écartée du résultat ; réponse inconnue ⇒ l'aide
    # reste candidate mais incertaine (fail-closed).
    #
    # Seul un `fact` est admis : un champ structuré relève de `hard_filters`.
    applies_if: AppliesIf | None = None
    # FAMILLES thématiques de l'aide (liste fermée, cf. labels.FAMILLES_LABELS).
    # L'axe de cadrage d'un projet « faire vivre le lieu », là où `raison` met
    # dans le même sac un festival, un gîte et un outil de médiation.
    #
    # Vide = l'aide concerne tout projet (fail-open), exactement comme une
    # `raison` absente : `hors_famille` ne l'écarte jamais. Ne poser une famille
    # que si la source RESTREINT le thème — un tag posé « au cas où » est un
    # faux négatif silencieux.
    #
    # Pluriel assumé : une aide « restauration et valorisation d'un site ouvert
    # au public » relève de deux familles, et la réduire à une seule l'écarterait
    # de l'autre.
    familles: list[str] = []
    conditions: list[Condition] = []
    flags: Flags = Flags()
    # Étapes de constitution du dossier (prose numérotée, fidèle à la source).
    demarche: str | None = None
    # Pièces du dossier — chaque pièce porte idéalement son lien (cf. Document).
    documents_requis: list[Document] = []
    tags: list[str] = []

    _v_raison = field_validator("raison")(_codes_validator(RAISONS, "raison"))
    _v_familles = field_validator("familles")(_codes_validator(FAMILLES, "famille"))

    @field_validator("documents_requis", mode="before")
    @classmethod
    def _coerce_documents(cls, v):
        """Rétrocompat : `documents_requis: [str, ...]` → `[{nom: str}, ...]`."""
        if not isinstance(v, list):
            return v
        return [{"nom": d} if isinstance(d, str) else d for d in v]

    @model_validator(mode="after")
    def _perimetre_cible_un_fait(self) -> Aide:
        if self.applies_if and not self.applies_if.fact:
            raise ValueError(
                "applies_if d'une aide cible un `fact` — un champ structuré relève de hard_filters"
            )
        return self

    @model_validator(mode="after")
    def _unique_condition_ids(self) -> Aide:
        seen: set[str] = set()
        for c in self.conditions:
            if c.id in seen:
                raise ValueError(f"id de condition en doublon : {c.id}")
            seen.add(c.id)
        return self


#: Une aide de ces catégories est instruite par un financeur dont le ressort EST
#: son territoire. Sans filtre géographique, elle se propose partout.
CATEGORIES_TERRITORIALES = {"departement": "departements", "region": "regions"}


def hard_filters_poses(aide: Aide) -> int:
    """Combien de restrictions structurées l'aide déclare."""
    hf = aide.hard_filters
    champs = (
        "protections",
        "proprietaires",
        "travaux",
        "regions",
        "departements",
        "etats_conservation",
    )
    return sum(1 for c in champs if getattr(hf, c, None)) + (1 if hf.commune_max_population else 0)


def sans_rien_a_verifier(aide: Aide) -> bool:
    """L'aide n'oppose RIEN : ni gate vérifiable, ni hard_filter.

    Le moteur n'a alors rien à évaluer et la rend « potentiellement éligible »
    à tout le monde, partout. Vu en production le 2026-09-22 sur un monument
    des Vosges à qui `92-innovation-ess-financements` s'affichait « vous semblez
    éligible » — une fiche dont la page source répondait 503 à l'ingestion et
    qui se déclarait elle-même non actionnable.

    `mesure_questionnaire.audit_fail_open` portait déjà ce diagnostic, mot pour
    mot, depuis un script de mesure dont la sortie n'arrête rien. Le contrôle
    appartient au lint.

    `applies_if` COMPTE : c'est le périmètre de l'aide, et le moteur s'en sert
    pour la déclarer hors sujet (`hors_perimetre`). Une aide qui ne porte que
    lui — `programme-patrimoine-emploi-fondation-patrimoine` et son
    `projet_support_insertion_ou_formation` — n'est pas fail-open, et l'oublier
    faisait de ce contrôle un faux positif sur du cœur de métier.
    """
    if aide.applies_if is not None:
        return False
    verifiables = any(
        c.kind in ("auto", "user_fact", "manual_check") and c.effect == "gate"
        for c in aide.conditions
    )
    return not verifiables and hard_filters_poses(aide) == 0


def gate_porteur(aide: Aide) -> bool:
    """L'aide dit-elle EXPLICITEMENT qui peut déposer ?

    Un `applies_if` d'aide sur le même fait compte : quatre aides du catalogue
    cadrent ainsi leur périmètre entier plutôt que condition par condition, et
    le moteur les traite pareil (`_scoped_conditions`).

    Vit ici et non dans `scripts/lint_aides_data.py` parce que le MOTEUR en a
    besoin : un gate explicite a précédence sur le marqueur `porteurs_concernes`
    (cf. `FactDef.porteurs_concernes`), et le moteur ne peut pas importer
    `scripts/`.
    """
    if aide.applies_if and aide.applies_if.fact == FAIT_PORTEUR:
        return True
    return any(c.effect == "gate" and c.fact == FAIT_PORTEUR for c in aide.conditions)


# ---------------------------------------------------------------------------
# Chargement
# ---------------------------------------------------------------------------


# Les trois loaders sont mis en cache : les YAML ne changent qu'au déploiement
# (git est la source de vérité, cf. docstring du module) et chaque appel non
# caché reparse ~130 fichiers (~0,7 s de CPU pur — sérialisé par le GIL quand
# le dashboard lance un diagnostic par monument). Corollaire : les structures
# retournées sont PARTAGÉES entre requêtes — ne jamais les modifier en place.


def _valider_faits(raw: dict, origine: Path) -> dict[str, FactDef]:
    """Valide une ontologie en NOMMANT la clé fautive.

    Sans ça, l'erreur pydantic d'une option mal déclarée arrive sans son fait :
    illisible dans la sortie du lint, qui charge les 900 faits d'un coup.
    """
    faits: dict[str, FactDef] = {}
    for key, val in raw.items():
        try:
            faits[key] = FactDef.model_validate(val)
        except ValidationError as exc:
            raise ValueError(f"{origine.name} — fait « {key} » : {exc}") from exc
    return faits


@cache
def load_facts(path: Path = FACTS_FILE) -> dict[str, FactDef]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _valider_faits(raw, path)


@cache
def load_pending_facts(path: Path = FACTS_PENDING_FILE) -> dict[str, FactDef]:
    """Faits en attente d'approbation. Fichier absent ou vide ⇒ {}."""
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _valider_faits(raw, path)


def load_aide(path: Path) -> Aide:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    aide = Aide.model_validate(raw)
    if aide.slug != path.stem:
        raise ValueError(f"slug « {aide.slug} » ≠ nom de fichier « {path.stem} »")
    return aide


@cache
def load_all_aides(directory: Path = AIDES_DIR) -> dict[str, Aide]:
    return {p.stem: load_aide(p) for p in sorted(directory.glob("*.yaml"))}
