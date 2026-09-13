"""Surcouche d'EXPLOITATION du catalogue : aides retirées, questions reformulées,
prédicats de conditions remplacés.

`backend/data/` reste la source de vérité éditoriale. Ce module lit trois tables
que le loader YAML ne touche jamais (`aides_retirees`, `faits_surcharges`,
`conditions_predicats`) et les applique PAR-DESSUS le cache YAML, au moment de
servir. Le besoin est
d'exploitation, pas d'édition : retirer en quelques secondes une aide qui
s'avère fausse, corriger la formulation d'une question du QCM, sans attendre un
commit et un déploiement. Un retrait ou une reformulation DURABLE se reporte
ensuite dans les YAML, puis se rétablit ici.

Trois invariants tiennent tout le module :

  * Les structures YAML sont PARTAGÉES entre requêtes (loaders `@cache`) : on
    n'en modifie jamais une en place, on rend toujours de nouveaux dicts.
  * Une ligne malformée (slug absent du corpus, JSON inattendu) est ignorée
    avec un avertissement. Une erreur d'administration ne doit pas casser le
    diagnostic de tout le monde.
  * Les ids des réponses (`options[].id`) sont FIGÉS : les prédicats des aides
    les citent. On peut renommer un libellé sans rien casser ; supprimer une
    réponse citée, en revanche, est une décision — d'où `impact_options`, qui
    la met sous les yeux de l'administrateur avant qu'il enregistre.
  * Une surcharge de prédicat MÉMORISE ce qui a motivé la décision humaine
    (texte de la condition, fait, prédicat d'origine) et le recompare à chaque
    passage : quand le YAML bouge sous elle, l'alerte revient d'elle-même.

Le cache est module-level, avec un TTL court et une invalidation après chaque
écriture. Un seul process uvicorn par environnement (cf. backend/Dockerfile,
sans `--workers`) : l'invalidation vaut donc pour tous les utilisateurs de
l'environnement, et le TTL n'est qu'un filet pour une ligne modifiée
directement dans Supabase Studio.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import cached_property

from pydantic import BaseModel, ConfigDict, Field
from supabase import Client

from aides_schema import (
    COMBINATOR_OPS,
    ENUM_FACT_TYPES,
    OPTIONS_BOOLEEN_IMPLICITES,
    TYPES_A_OPTIONS,
    Aide,
    Condition,
    FactDef,
    Predicate,
    check_fact_predicate,
    evaluate_predicate,
    load_all_aides,
    load_facts,
    load_pending_facts,
    predicate_leaves,
)
from eligibility_engine import disponibilite as aide_disponibilite
from eligibility_engine import engine_ready_aides

logger = logging.getLogger(__name__)

TABLE_RETIREES = "aides_retirees"
TABLE_SURCHARGES = "faits_surcharges"
TABLE_PREDICATS = "conditions_predicats"

#: Durée de validité du cache. Court : c'est le délai maximal entre une
#: modification faite hors de l'application (Supabase Studio) et sa prise
#: d'effet. Les écritures passées par `/admin`, elles, invalident tout de suite.
TTL_SECONDES = 60


# ---------------------------------------------------------------------------
# Formes validées des deux tables
# ---------------------------------------------------------------------------


#: Bornes des textes administrables. Elles doivent couvrir CE QUI EXISTE DÉJÀ
#: dans l'ontologie — le front renvoie les libellés d'origine quand l'admin n'y
#: touche pas, et une borne trop courte ferait échouer l'enregistrement d'une
#: modification qui ne les concerne même pas. Au 2026-09-11 le corpus culmine à
#: 234 caractères pour un libellé, 744 pour une question, 697 pour une aide
#: contextuelle : chaque borne garde de la marge sur ces maximums.
LABEL_MAX = 400
QUESTION_MAX = 1000
HELP_MAX = 4000
#: Une question du QCM au-delà n'est plus une question, c'est un formulaire.
OPTIONS_MAX = 50


class OptionSurchargee(BaseModel):
    """Une réponse possible, telle que l'administration la décrit.

    Même forme que `FactOption` — c'est elle qui la remplacera — mais bornée :
    ces valeurs viennent d'un formulaire, pas d'un YAML relu en revue de code.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9_]+$", max_length=80)
    label: str = Field(min_length=1, max_length=LABEL_MAX)
    #: Réponse NEUTRE (« je ne sais pas ») : le moteur traite alors le fait
    #: comme inconnu, et la réponse n'écarte aucune aide.
    unknown: bool = False
    #: Faits `boolean` seulement : la valeur de vérité envoyée aux prédicats
    #: (cf. `FactOption.valeur`). `None` = « ne tranche pas », la réponse
    #: n'écarte alors rien. Sur un fait à choix, l'identifiant EST la valeur et
    #: le champ est refusé par `valider_surcharge`.
    valeur: bool | None = None


class SurchargeFait(BaseModel):
    """Une ligne de `faits_surcharges`, validée.

    `extra="ignore"` : la ligne porte aussi `modifie_par`, `created_at`,
    `updated_at`, qui ne disent rien du contenu servi.

    Un champ à `None` veut dire « pas de surcharge, garder le YAML » — et non
    « vider ». `options`, quand elle est présente, REMPLACE la liste entière.
    """

    model_config = ConfigDict(extra="ignore")

    fact_key: str
    question: str | None = None
    help: str | None = None
    options: list[OptionSurchargee] | None = None


#: Les seuls opérateurs que l'éditeur de prédicats sait rendre. Un menu plus
#: des cases à cocher : pas de combinateur, pas de seuil numérique.
OPERATEURS_PREDICAT = ("eq", "neq", "in", "not_in")

#: Motif d'une surcharge de prédicat — même borne que celle d'un retrait.
MOTIF_MAX = 500


class SurchargePredicat(BaseModel):
    """Une ligne de `conditions_predicats`, validée.

    Les trois derniers champs sont les TÉMOINS DE PÉREMPTION : ils mémorisent
    ce qui a motivé la décision humaine, pour le recomparer à chaque passage.
    Le patron vient de `traiter_acquittements` (scripts/veille_aides.py) —
    mémoriser la valeur qui a motivé la décision, la comparer, et laisser
    l'alerte revenir d'elle-même plutôt que de faire confiance à un « vu ».
    """

    model_config = ConfigDict(extra="ignore")

    aide_slug: str
    condition_id: str
    predicate: dict
    #: Texte de la condition au moment de la surcharge. S'il change, la décision
    #: a été prise sur une AUTRE condition : la ligne est périmée.
    condition_text: str
    #: Un retypage vers un autre fait rendrait le prédicat absurde sans toucher
    #: au texte.
    fact_key: str
    #: Prédicat YAML au moment de la surcharge. Ne périme pas la ligne, la
    #: marque « à revoir ».
    predicate_origine: dict
    motif: str | None = None


@dataclass(frozen=True)
class Catalogue:
    """Le catalogue tel qu'il est SERVI : YAML + surcouche, calculé une fois."""

    #: Aides du corpus, moins les retirées.
    aides: dict[str, Aide]
    #: Ontologie (facts + pending), surcharges appliquées.
    facts: dict[str, FactDef]
    #: slug → ligne brute de `aides_retirees` (motif, retiree_par, created_at).
    retirees: dict[str, dict]
    #: fact_key → surcharge validée.
    surcharges: dict[str, SurchargeFait]
    #: (aide_slug, condition_id) → verdict de la surcharge de prédicat.
    predicats: dict[tuple[str, str], VerdictPredicat]

    @cached_property
    def conditions_modifiables(self) -> list[tuple[Aide, Condition]]:
        """L'inventaire des conditions qu'on peut surcharger. PARESSEUX, sur le
        modèle de `index` : un diagnostic n'a pas à payer le balayage du corpus
        parce que son tour est venu de rafraîchir le cache."""
        return [
            (aide, condition)
            for _slug, aide in sorted(self.aides.items())
            for condition in aide.conditions
            if condition_modifiable(condition, self.facts)
        ]

    @cached_property
    def index(self) -> IndexFaits:
        """Quelles aides parlent de quel fait. PARESSEUX : seule
        l'administration en a besoin, et un diagnostic n'a pas à payer le
        balayage du corpus parce que son tour est venu de rafraîchir le cache.
        Le calcul est ensuite gardé pour toute la durée de vie du catalogue."""
        return construire_index(self.aides)


# ---------------------------------------------------------------------------
# Application de la surcouche — fonctions PURES, testables sans base
# ---------------------------------------------------------------------------


def retirer(aides: Mapping[str, Aide], slugs: Iterable[str]) -> dict[str, Aide]:
    """Le corpus moins ces slugs. Un slug inconnu est ignoré (le YAML a pu
    changer depuis le retrait — l'aide archivée est déjà partie)."""
    a_retirer = {slug for slug in slugs if slug in aides}
    if not a_retirer:
        return dict(aides)
    return {slug: aide for slug, aide in aides.items() if slug not in a_retirer}


def surcharger_fait(original: FactDef, surcharge: SurchargeFait) -> FactDef:
    """Le fait tel qu'il sera posé à l'utilisateur.

    Reconstruction par `model_validate` et non par `model_copy(update=)` : en
    Pydantic v2, `model_copy` NE RELANCE PAS les validateurs, et une liste
    d'options vide sur un enum passerait sans bruit (`_options_iff_enum`). Le
    coût est payé une fois par rafraîchissement du cache, pas par requête.
    """
    donnees = original.model_dump()
    if surcharge.question is not None:
        donnees["question"] = surcharge.question
    if surcharge.help is not None:
        donnees["help"] = surcharge.help
    if surcharge.options is not None:
        donnees["options"] = [o.model_dump() for o in surcharge.options]
    return FactDef.model_validate(donnees)


def surcharger_faits(
    facts: Mapping[str, FactDef], surcharges: Mapping[str, SurchargeFait]
) -> dict[str, FactDef]:
    """L'ontologie servie. Une surcharge invalide est ignorée, pas fatale."""
    effectifs = dict(facts)
    for key, surcharge in surcharges.items():
        original = facts.get(key)
        if original is None:
            logger.warning("surcharge ignorée : fait « %s » absent de l'ontologie", key)
            continue
        try:
            effectifs[key] = surcharger_fait(original, surcharge)
        except Exception:
            logger.warning("surcharge invalide sur « %s », fait YAML conservé", key, exc_info=True)
    return effectifs


def valider_surcharge(original: FactDef, brouillon: SurchargeFait) -> None:
    """Refuse un brouillon incohérent. `ValueError` → 422 côté route.

    Les options sont éditables sur un `enum`, un `multi_enum` ou un `boolean` ;
    seules les tranches d'un fait numérique restent CALCULÉES par le moteur
    depuis les seuils des aides (`_options_for_fact`) — elles ne viennent pas du
    YAML et une liste posée ici ne serait jamais lue.

    Sur un booléen, les règles reprennent celles de `FactDef` (R1, R2, R4) mais
    avec des messages écrits pour un humain devant un formulaire : le panneau
    doit pouvoir les afficher tels quels.

    Un libellé vide est refusé : il produirait une réponse invisible dans le
    QCM. Une question vide aussi. `help` vide, en revanche, est accepté — c'est
    le seul moyen de retirer une aide contextuelle devenue fausse.
    """
    if brouillon.question is not None and not brouillon.question.strip():
        raise ValueError("la question ne peut pas être vide")
    if brouillon.options is None:
        return
    if original.type not in TYPES_A_OPTIONS:
        raise ValueError(
            f"les réponses d'un fait {original.type} sont calculées par le moteur, "
            "elles ne se modifient pas ici"
        )
    if not brouillon.options:
        raise ValueError("un fait à choix doit garder au moins une réponse")
    ids = [o.id for o in brouillon.options]
    doublons = sorted({i for i in ids if ids.count(i) > 1})
    if doublons:
        raise ValueError(f"identifiants de réponse en doublon : {', '.join(doublons)}")
    vides = [o.id for o in brouillon.options if not o.label.strip()]
    if vides:
        raise ValueError(f"libellé vide pour la ou les réponses : {', '.join(vides)}")

    # R2 — sur un fait à choix, l'identifiant EST la valeur.
    if original.type in ENUM_FACT_TYPES:
        avec_valeur = [o.id for o in brouillon.options if o.valeur is not None]
        if avec_valeur:
            raise ValueError(
                "une valeur envoyée au moteur ne se pose que sur une question Oui/Non ; "
                f"réponse(s) concernée(s) : {', '.join(sorted(avec_valeur))}"
            )
        return

    # R4 — une réponse neutre ne tranche rien, par définition.
    neutres = [o.id for o in brouillon.options if o.unknown and o.valeur is not None]
    if neutres:
        raise ValueError(
            "une réponse neutre ne peut pas envoyer de valeur au moteur ; "
            f"réponse(s) concernée(s) : {', '.join(sorted(neutres))}"
        )

    # R1 — le couple implicite doit survivre : c'est ce qui rend l'ajout inerte
    # pour les réponses déjà enregistrées, et ce qui garde les deux valeurs de
    # vérité atteignables.
    par_id = {o.id: o for o in brouillon.options}
    for attendu in OPTIONS_BOOLEEN_IMPLICITES:
        presente = par_id.get(attendu.id)
        if presente is None:
            raise ValueError(
                f"la réponse « {attendu.id} » ne peut pas être supprimée : les réponses "
                "déjà enregistrées par les utilisateurs s'appuient dessus"
            )
        if presente.valeur is not attendu.valeur:
            raise ValueError(
                f"la réponse « {attendu.id} » doit garder la valeur "
                f"« {'Oui' if attendu.valeur else 'Non'} »"
            )


def _options_tuple(
    options: Iterable[OptionSurchargee],
) -> list[tuple[str, str, bool, bool | None]]:
    """Forme comparable d'une liste de réponses. `valeur` EN FAIT PARTIE : sans
    elle, `surcharge_utile` verrait « identique à l'original » un brouillon où
    seule une valeur change, et SUPPRIMERAIT la ligne au lieu de l'écrire."""
    return [(o.id, o.label, o.unknown, o.valeur) for o in options]


def options_editables(fact: FactDef) -> list[OptionSurchargee]:
    """Les réponses telles que l'administration les édite.

    Un fait `boolean` qui ne déclare rien rend le couple implicite plutôt qu'une
    liste vide : le panneau doit s'ouvrir sur Oui/Non, sinon l'administrateur
    croirait la question sans réponses et repartirait de zéro — en supprimant au
    passage les deux identifiants que les réponses persistées citent.
    """
    options = fact.options
    if options is None and fact.type == "boolean":
        options = list(OPTIONS_BOOLEEN_IMPLICITES)
    return [
        OptionSurchargee(id=o.id, label=o.label, unknown=o.unknown, valeur=o.valeur)
        for o in options or []
    ]


def surcharge_utile(original: FactDef, brouillon: SurchargeFait) -> SurchargeFait | None:
    """Le brouillon réduit à ce qui DIFFÈRE du YAML, ou `None` si rien n'en
    diffère.

    Une surcharge qui recopie le YAML est pire qu'inutile : elle fige la
    formulation, et une correction ultérieure de `facts.yaml` resterait sans
    effet en production sans que personne comprenne pourquoi. Le jour où tout
    revient à l'original, la ligne est supprimée (cf. `enregistrer_surcharge`).
    """
    question = (brouillon.question or "").strip() if brouillon.question is not None else None
    aide_ctx = brouillon.help.strip() if brouillon.help is not None else None
    utile = SurchargeFait(
        fact_key=brouillon.fact_key,
        question=question if question and question != original.question else None,
        help=aide_ctx if aide_ctx != (original.help or "") else None,
        options=None,
    )
    if brouillon.options is not None and _options_tuple(brouillon.options) != _options_tuple(
        options_editables(original)
    ):
        utile = utile.model_copy(update={"options": brouillon.options})
    if utile.question is None and utile.help is None and utile.options is None:
        return None
    return utile


# ---------------------------------------------------------------------------
# Impact d'une réponse sur les aides
# ---------------------------------------------------------------------------


def _gates_sur_fait(aide: Aide, fact_key: str) -> list[Condition]:
    """Conditions DIRIMANTES de cette aide portant sur ce fait — celles dont la
    réponse peut écarter l'aide (même sémantique que `eliminationsParOption`)."""
    return [
        c
        for c in aide.conditions
        if c.kind == "user_fact" and c.effect == "gate" and c.fact == fact_key and c.predicate
    ]


def _ids_cites(aide: Aide, fact_key: str) -> set[str]:
    """Identifiants de réponse que cette aide CITE pour ce fait.

    Trois emplacements citent un fait : la condition `user_fact` elle-même, sa
    clause d'applicabilité, et le périmètre de l'aide entière. Supprimer une
    réponse citée ici laisse un prédicat qui ne pourra plus jamais être
    satisfait — l'aide ne sortirait plus du questionnaire.
    """
    predicats = [
        c.predicate for c in aide.conditions if c.kind == "user_fact" and c.fact == fact_key
    ]
    clauses = [
        c.applies_if for c in aide.conditions if c.applies_if and c.applies_if.fact == fact_key
    ]
    if aide.applies_if and aide.applies_if.fact == fact_key:
        clauses.append(aide.applies_if)
    predicats.extend(clause.predicate for clause in clauses)

    cites: set[str] = set()
    for predicat in predicats:
        if predicat is None:
            continue
        for _op, valeur in predicate_leaves(predicat.root):
            valeurs = valeur if isinstance(valeur, list) else [valeur]
            cites.update(v for v in valeurs if isinstance(v, str))
    return cites


def _ref(aide: Aide) -> dict:
    return {"slug": aide.slug, "nom": aide.nom}


@dataclass(frozen=True)
class IndexFaits:
    """Quelles aides parlent de quel fait — calculé en UNE passe sur le corpus.

    Sans cet index, lister l'ontologie pour l'administration relisait les
    conditions des 330 aides pour chacun des 700 faits, soit près de trois
    secondes de CPU pur. Le backend tourne en un seul process : trois secondes
    de calcul, ce sont trois secondes où plus personne n'est servi.
    """

    #: fait → slug → gates sur ce fait, parmi les aides ENGINE-READY seulement
    #: (le moteur ne sert que celles-là : annoncer qu'une réponse écarte une
    #: aide non typée serait faux).
    gates: dict[str, dict[str, list[Condition]]]
    #: fait → slug → identifiants de réponse cités, sur TOUT le corpus (une
    #: citation dans une aide pas encore typée compte aussi).
    cites: dict[str, dict[str, set[str]]]
    aides: dict[str, Aide]


def construire_index(aides: Mapping[str, Aide]) -> IndexFaits:
    ready = engine_ready_aides(dict(aides))
    gates: dict[str, dict[str, list[Condition]]] = {}
    cites: dict[str, dict[str, set[str]]] = {}

    for slug, aide in aides.items():
        faits = {c.fact for c in aide.conditions if c.fact}
        faits |= {c.applies_if.fact for c in aide.conditions if c.applies_if and c.applies_if.fact}
        if aide.applies_if and aide.applies_if.fact:
            faits.add(aide.applies_if.fact)
        for fact_key in faits:
            ids = _ids_cites(aide, fact_key)
            if ids:
                cites.setdefault(fact_key, {})[slug] = ids
            if slug in ready:
                conds = _gates_sur_fait(aide, fact_key)
                if conds:
                    gates.setdefault(fact_key, {})[slug] = conds

    return IndexFaits(gates=gates, cites=cites, aides=dict(aides))


def _valeur_de_test(fait: FactDef, option: OptionSurchargee):
    """La valeur que le moteur injectera vraiment pour cette réponse.

    Sur un fait à choix, c'est l'identifiant — il EST la valeur. Sur un
    `boolean`, c'est la `valeur` déclarée : sans ce détour, l'écran annoncerait
    que « Oui » écarte les aides qui exigent `eq: true`, parce que
    `evaluate_predicate({"eq": True}, "oui")` vaut `False`. Miroir exact de
    `_normalize_answer` — les deux doivent bouger ensemble.

    `None` pour une réponse neutre et pour une réponse booléenne qui ne tranche
    pas : le fait reste inconnu, elle n'écarte rien.
    """
    if option.unknown:
        return None
    if fait.type == "boolean":
        return option.valeur
    return option.id


def impact_options(
    fact_key: str,
    options: list[OptionSurchargee],
    aides: Mapping[str, Aide],
    original: FactDef,
    index: IndexFaits | None = None,
) -> dict:
    """Ce que ces réponses feraient au catalogue, réponse par réponse.

    Deux questions, et ce sont exactement celles que se pose l'administrateur
    avant d'enregistrer :

      * « Qu'est-ce que cette réponse écarte ? » — les aides dont un gate sur
        ce fait devient FAUX à cette valeur. Calculé comme
        `eliminationsParOption` dans le moteur, en évaluant le prédicat à la
        valeur de l'option (cf. `_valeur_de_test`). Une réponse neutre
        (`unknown`), et sur un booléen une réponse qui ne tranche pas,
        n'écartent jamais rien. Seules les aides engine-ready comptent : les
        autres ne sont pas servies par le moteur, annoncer qu'on les écarte
        serait faux.
      * « Qu'est-ce que je casse en supprimant cette réponse ? » — les aides
        qui la citent dans un prédicat. Toutes les aides du corpus comptent
        ici : une citation dans une aide encore non typée est une bombe à
        retardement, pas un non-événement.

    Sans contexte de monument : ce sont TOUTES les aides qui gatent sur ce
    fait, pas seulement celles qu'un bien donné atteindrait.

    `index` évite de rebalayer le corpus quand on traite l'ontologie entière
    (cf. `IndexFaits`) ; sans lui, il est construit pour ce seul appel.
    """
    idx = index if index is not None else construire_index(aides)
    gates = idx.gates.get(fact_key, {})
    cites = idx.cites.get(fact_key, {})

    par_option = []
    for option in options:
        ecarte = []
        # Même valeur de test que le moteur (cf. `_valeur_de_test`) : l'id sur
        # un fait à choix — y compris en choix multiple, chaque case est évaluée
        # seule — et la valeur déclarée sur un booléen. `None` n'écarte rien.
        valeur = _valeur_de_test(original, option)
        if valeur is not None:
            for slug in sorted(gates):
                if any(
                    c.predicate and evaluate_predicate(c.predicate.root, valeur) is False
                    for c in gates[slug]
                ):
                    ecarte.append(_ref(idx.aides[slug]))
        par_option.append(
            {
                "id": option.id,
                "label": option.label,
                "unknown": option.unknown,
                "valeur": option.valeur,
                "ecarte": ecarte,
            }
        )

    gardes = {o.id for o in options}
    supprimees = []
    for originale in options_editables(original):
        if originale.id in gardes:
            continue
        referencee = [
            _ref(idx.aides[slug]) for slug in sorted(cites) if originale.id in cites[slug]
        ]
        supprimees.append(
            {"id": originale.id, "label": originale.label, "referenceePar": referencee}
        )

    return {"factKey": fact_key, "parOption": par_option, "supprimees": supprimees}


# ---------------------------------------------------------------------------
# Prédicats de conditions — fonctions PURES, testables sans base
# ---------------------------------------------------------------------------


def predicat_depuis(operateur: str, valeurs: Iterable[str]) -> dict:
    """`("in", ["b", "a"])` → `{"in": ["a", "b"]}`, canonisé."""
    return canoniser_predicat({operateur: sorted(set(valeurs))})


def operateur_et_valeurs(predicate: Mapping) -> tuple[str, list[str]]:
    """Réciproque de `predicat_depuis`. `{"eq": "a"}` → `("eq", ["a"])`.

    Un prédicat hors mandat (combinateur, valeur non-chaîne) rend une liste
    vide : c'est `condition_modifiable` et `valider_predicat` qui refusent, pas
    cette fonction — elle décrit, elle ne juge pas.
    """
    if len(predicate) != 1:
        return ("", [])
    operateur, brut = next(iter(dict(predicate).items()))
    valeurs = brut if isinstance(brut, list) else [brut]
    return (operateur, [v for v in valeurs if isinstance(v, str)])


def canoniser_predicat(predicate: Mapping) -> dict:
    """Forme normale d'un prédicat simple : valeurs triées, `in` à une seule
    valeur ramené à `eq` (et `not_in` à `neq`).

    Ce n'est pas cosmétique : 27 des 392 gates du corpus sont un `in` à une
    valeur. Sans canonisation, un administrateur qui RECOMPOSE le prédicat
    d'origine depuis le menu écrirait une ligne qui ne change rien — une
    surcharge inutile, qui figerait le YAML pour rien.
    """
    operateur, valeurs = operateur_et_valeurs(predicate)
    if not operateur or not valeurs:
        return dict(predicate)
    valeurs = sorted(set(valeurs))
    if len(valeurs) == 1:
        if operateur == "in":
            operateur = "eq"
        elif operateur == "not_in":
            operateur = "neq"
        return {operateur: valeurs[0]}
    if operateur == "eq":
        operateur = "in"
    elif operateur == "neq":
        operateur = "not_in"
    return {operateur: valeurs}


def condition_modifiable(condition: Condition, facts: Mapping[str, FactDef]) -> bool:
    """LE MANDAT, énoncé une seule fois — toutes les routes passent par lui.

    Un gate `user_fact` sur un fait à options, dont le prédicat est de forme
    simple. Les combinateurs sont hors mandat parce que l'interface ne sait pas
    les rendre : un éditeur qui ne peut pas AFFICHER ce qu'il modifie est une
    machine à casser des prédicats.

    Les faits numériques sont exclus : leurs tranches viennent des seuils, et
    déplacer un seuil depuis /admin est un autre geste que choisir des réponses.
    """
    if condition.kind != "user_fact" or condition.effect != "gate":
        return False
    if condition.predicate is None:
        return False
    fait = facts.get(condition.fact or "")
    if fait is None or fait.type not in ENUM_FACT_TYPES:
        return False
    operateur, valeurs = operateur_et_valeurs(condition.predicate.root)
    return operateur in OPERATEURS_PREDICAT and bool(valeurs)


def valider_predicat(
    condition: Condition,
    predicate: Mapping,
    facts: Mapping[str, FactDef],
) -> None:
    """Refuse un prédicat impossible. `ValueError` → 422 côté route.

    Trois gardes, dans cet ordre : pas de combinateur (hors mandat), puis
    `check_fact_predicate` MOT POUR MOT comme le lint — c'est la raison d'être
    de sa remontée dans `aides_schema` — puis le refus d'une liste vide.

    La validation porte sur l'ontologie EFFECTIVE, surcharges de faits
    comprises : un prédicat peut légitimement citer une réponse qui n'existe
    que dans `faits_surcharges`.
    """
    operateur, valeurs = operateur_et_valeurs(predicate)
    if operateur in COMBINATOR_OPS:
        raise ValueError(
            "un prédicat composé (any_of / all_of) ne se modifie pas ici : "
            "il se corrige dans le YAML de l'aide"
        )
    if operateur not in OPERATEURS_PREDICAT:
        raise ValueError(f"opérateur « {operateur} » hors des quatre admis")
    if not valeurs:
        raise ValueError("il faut cocher au moins une réponse")
    try:
        verifie = Predicate.model_validate(dict(predicate))
    except Exception as exc:
        raise ValueError(f"prédicat mal formé : {exc}") from exc
    erreurs = check_fact_predicate(f"{condition.id}", condition.fact, verifie, dict(facts))
    if erreurs:
        raise ValueError(" ; ".join(erreurs))


def predicat_utile(original: Mapping, neuf: Mapping) -> dict | None:
    """`None` si le prédicat neuf est CANONIQUEMENT égal à l'original.

    Miroir exact de `surcharge_utile` : une ligne qui recopie le YAML fige la
    version d'avant, et une correction ultérieure de l'aide resterait sans effet
    en production sans que personne comprenne pourquoi. Le jour où tout revient
    à l'original, la ligne est supprimée.
    """
    canonique = canoniser_predicat(neuf)
    if canonique == canoniser_predicat(original):
        return None
    return canonique


def _empreinte_texte(text: str) -> str:
    """Comparaison des textes de condition sur les mots, pas sur les octets.

    Un simple RE-REPLI du YAML (le même texte, coupé à une autre colonne)
    périmerait sinon toutes les surcharges de la fiche — un faux positif de
    masse, et la péremption cesserait d'être lue.
    """
    return " ".join((text or "").split())


#: Les états d'une surcharge de prédicat. Tous IGNORENT la ligne sauf `active`
#: et `a_revoir`.
ETATS_PREDICAT = (
    "active",  # appliquée, et le YAML n'a pas bougé
    "a_revoir",  # APPLIQUÉE quand même : le YAML a rattrapé, un humain tranche
    "perimee_texte",  # le texte de la condition a changé sous la décision
    "perimee_fait",  # la condition a été retypée sur un autre fait
    "aide_absente",  # l'aide a quitté le corpus
    "condition_absente",  # la condition a quitté l'aide
    "hors_mandat",  # la condition n'est plus un gate sur un fait à options
    "invalide",  # le prédicat ne passe plus la validation (option supprimée…)
)


@dataclass(frozen=True)
class VerdictPredicat:
    """Une ligne de surcouche, confrontée au YAML d'aujourd'hui."""

    ligne: SurchargePredicat
    etat: str
    #: Raison lisible, destinée au panneau d'administration.
    detail: str | None = None
    #: Le prédicat YAML actuel, pour l'afficher à côté du nouveau.
    predicate_yaml: dict | None = None
    #: Le texte actuel de la condition, idem.
    condition_text_actuel: str | None = None

    @property
    def appliquee(self) -> bool:
        """`a_revoir` s'applique AUSSI : si la veille corrige le prédicat YAML
        sans toucher au texte, ignorer la surcharge re-casserait en silence ce
        que l'administrateur avait réparé. On garde le correctif et on demande
        un arbitrage — c'est la seule asymétrie de la cascade."""
        return self.etat in ("active", "a_revoir")


def verdict_predicat(
    ligne: SurchargePredicat,
    aides: Mapping[str, Aide],
    facts: Mapping[str, FactDef],
) -> VerdictPredicat:
    """Confronte une ligne au YAML d'aujourd'hui et rend son état.

    L'ordre des tests va du plus grossier au plus fin : l'aide existe-t-elle
    encore, puis la condition, puis est-elle toujours dans le mandat, puis les
    trois témoins, puis le prédicat lui-même.
    """
    aide = aides.get(ligne.aide_slug)
    if aide is None:
        return VerdictPredicat(ligne, "aide_absente", "l’aide a quitté le catalogue")
    condition = next((c for c in aide.conditions if c.id == ligne.condition_id), None)
    if condition is None:
        return VerdictPredicat(ligne, "condition_absente", "la condition a quitté l’aide")

    actuel = condition.predicate.root if condition.predicate else None
    contexte = {
        "predicate_yaml": dict(actuel) if actuel else None,
        "condition_text_actuel": condition.text,
    }

    if not condition_modifiable(condition, facts):
        return VerdictPredicat(
            ligne, "hors_mandat", "la condition n’est plus un gate sur un fait à choix", **contexte
        )
    # Témoin 2 : un retypage vers un autre fait rendrait le prédicat absurde
    # sans rien changer au texte.
    if condition.fact != ligne.fact_key:
        return VerdictPredicat(
            ligne,
            "perimee_fait",
            f"la condition porte désormais sur « {condition.fact} » et non « {ligne.fact_key} »",
            **contexte,
        )
    # Témoin 1 : la décision a-t-elle été prise sur CE texte ?
    if _empreinte_texte(condition.text) != _empreinte_texte(ligne.condition_text):
        return VerdictPredicat(
            ligne,
            "perimee_texte",
            "le texte de la condition a changé depuis la surcharge",
            **contexte,
        )
    try:
        valider_predicat(condition, ligne.predicate, facts)
    except ValueError as exc:
        return VerdictPredicat(ligne, "invalide", str(exc), **contexte)
    # Témoin 3 : le YAML a-t-il rattrapé ? Ne périme pas, marque « à revoir ».
    if actuel is not None and canoniser_predicat(actuel) != canoniser_predicat(
        ligne.predicate_origine
    ):
        return VerdictPredicat(
            ligne,
            "a_revoir",
            "le prédicat du YAML a changé depuis la surcharge : à arbitrer",
            **contexte,
        )
    return VerdictPredicat(ligne, "active", None, **contexte)


def appliquer_predicats(
    aides: Mapping[str, Aide],
    predicats: Mapping[tuple[str, str], VerdictPredicat],
    facts: Mapping[str, FactDef],
) -> dict[str, Aide]:
    """Le corpus servi, prédicats surchargés substitués.

    Seules les aides CONCERNÉES sont reconstruites : zéro surcoût quand aucune
    ligne n'existe, ce qui est le cas courant.

    Reconstruction par `Aide.model_validate(aide.model_dump())` et JAMAIS par
    `model_copy(update=)` : en Pydantic v2, `model_copy` ne relance pas les
    validateurs, et un prédicat malformé passerait sans bruit jusque dans le
    moteur. Même leçon que `surcharger_fait`, déjà écrite dans sa docstring.

    Le coût (0,06 ms par aide reconstruite) est payé une fois par
    rafraîchissement de cache, pas par requête.
    """
    par_slug: dict[str, dict[str, dict]] = {}
    for (slug, condition_id), verdict in predicats.items():
        if verdict.appliquee:
            par_slug.setdefault(slug, {})[condition_id] = canoniser_predicat(
                verdict.ligne.predicate
            )
    if not par_slug:
        return dict(aides)

    effectives = dict(aides)
    for slug, remplacements in par_slug.items():
        aide = aides.get(slug)
        if aide is None:
            continue
        donnees = aide.model_dump()
        for condition in donnees.get("conditions", []):
            neuf = remplacements.get(condition.get("id"))
            if neuf is not None:
                condition["predicate"] = neuf
        try:
            effectives[slug] = Aide.model_validate(donnees)
        except Exception:
            logger.warning(
                "surcharge de prédicat invalide sur « %s », aide YAML conservée",
                slug,
                exc_info=True,
            )
    return effectives


def _avertissements(
    aide: Aide, condition: Condition, engine_ready: bool, retiree: bool
) -> list[str]:
    """Ce qui rend l'impact HONNÊTE, et qui compte plus que l'affichage.

    Un verdict de gate ne dit pas à lui seul ce qu'il advient de l'aide : cinq
    circonstances changent la conclusion, et les taire ferait croire à un effet
    qui n'existe pas.
    """
    avertissements = []
    if retiree:
        avertissements.append(
            "Cette aide est retirée du catalogue : le changement n’aura aucun effet."
        )
    elif not engine_ready:
        avertissements.append(
            "Cette aide n’est pas entièrement typée : le moteur ne la sert pas, "
            "le changement n’aura aucun effet."
        )
    if condition.derogation_possible:
        avertissements.append(
            "Dérogation possible sur cette condition : un échec ne refuse pas l’aide, "
            "il la fait passer en « à confirmer »."
        )
    if condition.applies_if:
        avertissements.append(
            "Cette condition ne s’applique qu’à certains profils "
            f"(applies_if sur « {condition.applies_if.fact or condition.applies_if.field} »)."
        )
    autres = [
        c.id
        for c in aide.conditions
        if c.id != condition.id
        and c.kind == "user_fact"
        and c.effect == "gate"
        and c.fact == condition.fact
    ]
    if autres:
        avertissements.append(
            "Cette aide porte un autre gate sur le même fait "
            f"({', '.join(autres)}) : elle reste écartée si celui-là échoue."
        )
    return avertissements


def impact_predicat(
    aide: Aide,
    condition: Condition,
    predicate: Mapping,
    facts: Mapping[str, FactDef],
    *,
    engine_ready: bool = True,
    retiree: bool = False,
) -> dict:
    """Ce que le nouveau prédicat change, réponse par réponse.

    Le « AVANT » se calcule contre le prédicat SERVI (celui de `condition`, donc
    surcharge comprise) et non contre le YAML : la question à laquelle
    l'administrateur veut une réponse est « qu'est-ce que ça change à partir de
    maintenant », pas « qu'est-ce que ça change par rapport à un état que plus
    personne ne voit ».

    Ce qu'on ne montre PAS, et qui est écrit dans le panneau : le nombre
    d'utilisateurs concernés. On annonce un verdict de critère, pas une
    prévision d'audience.
    """
    fait = facts.get(condition.fact or "")
    avant = condition.predicate.root if condition.predicate else {}
    apres = canoniser_predicat(predicate)

    par_reponse = []
    for option in options_editables(fait) if fait else []:
        valeur = _valeur_de_test(fait, option) if fait else None
        # Même valeur de test que le moteur (cf. `_valeur_de_test`).
        avant_ecarte = valeur is not None and evaluate_predicate(dict(avant), valeur) is False
        apres_ecarte = valeur is not None and evaluate_predicate(apres, valeur) is False
        par_reponse.append(
            {
                "id": option.id,
                "label": option.label,
                "avantEcarte": avant_ecarte,
                "apresEcarte": apres_ecarte,
                "changement": avant_ecarte != apres_ecarte,
            }
        )

    return {
        "aideSlug": aide.slug,
        "conditionId": condition.id,
        "factKey": condition.fact,
        "avant": dict(avant),
        "apres": apres,
        "parReponse": par_reponse,
        "avertissements": _avertissements(aide, condition, engine_ready, retiree),
    }


# ---------------------------------------------------------------------------
# Cache : YAML + surcouche, calculés une fois par TTL
# ---------------------------------------------------------------------------

_cache: Catalogue | None = None
_expire_a: float = 0.0


def invalider() -> None:
    """Force le prochain appel à relire les deux tables. Appelée après chaque
    écriture admin — et par les tests, en setUp ET en tearDown."""
    global _cache, _expire_a
    _cache = None
    _expire_a = 0.0


def _lignes(supabase: Client, table: str) -> list[dict]:
    """Toutes les lignes d'une table de la surcouche.

    `select("*")` nu, sans `in_` ni `order` : les deux tables comptent quelques
    lignes, et les faux clients des tests de routes n'implémentent que ça.

    Une lecture qui échoue (migration pas encore appliquée, base injoignable)
    rend une surcouche VIDE plutôt qu'une erreur : le diagnostic continue de
    servir les YAML. Un retrait est une correction éditoriale, pas une
    frontière de sécurité — le faire tomber en panne l'application entière
    serait un remède pire que le mal.
    """
    try:
        res = supabase.table(table).select("*").execute()
        return list((res.data if res else None) or [])
    except Exception:
        logger.warning("surcouche catalogue : lecture de %s impossible", table, exc_info=True)
        return []


def _retirees(supabase: Client) -> dict[str, dict]:
    lignes = {}
    for ligne in _lignes(supabase, TABLE_RETIREES):
        slug = ligne.get("slug")
        if isinstance(slug, str) and slug:
            lignes[slug] = ligne
        else:
            logger.warning("ligne %s sans slug exploitable : %r", TABLE_RETIREES, ligne)
    return lignes


def _surcharges(supabase: Client) -> dict[str, SurchargeFait]:
    surcharges = {}
    for ligne in _lignes(supabase, TABLE_SURCHARGES):
        try:
            surcharge = SurchargeFait.model_validate(ligne)
        except Exception:
            logger.warning("ligne %s illisible : %r", TABLE_SURCHARGES, ligne, exc_info=True)
            continue
        surcharges[surcharge.fact_key] = surcharge
    return surcharges


def _predicats(supabase: Client) -> list[SurchargePredicat]:
    lignes = []
    for ligne in _lignes(supabase, TABLE_PREDICATS):
        try:
            lignes.append(SurchargePredicat.model_validate(ligne))
        except Exception:
            logger.warning("ligne %s illisible : %r", TABLE_PREDICATS, ligne, exc_info=True)
    return lignes


def catalogue_effectif(supabase: Client) -> Catalogue:
    """Le catalogue servi : YAML en cache + surcouche, structures calculées
    UNE fois par TTL (et non par requête — le dashboard lance un diagnostic
    par projet)."""
    global _cache, _expire_a
    maintenant = time.monotonic()
    if _cache is not None and maintenant < _expire_a:
        return _cache

    retirees = _retirees(supabase)
    surcharges = _surcharges(supabase)

    # L'ORDRE compte, et chaque étape explique la suivante :
    #   1. retirer d'abord — inutile de reconstruire une aide qui ne sera pas
    #      servie, et une ligne de prédicat sur une aide retirée est sans objet ;
    #   2. l'ontologie effective ensuite — la validation des prédicats se fait
    #      contre les options RÉELLEMENT posées, surcharges de faits comprises ;
    #   3. l'application des prédicats enfin, sur ce corpus et cette ontologie.
    servies = retirer(load_all_aides(), retirees)
    facts = surcharger_faits({**load_facts(), **load_pending_facts()}, surcharges)
    verdicts = {
        (ligne.aide_slug, ligne.condition_id): verdict_predicat(ligne, servies, facts)
        for ligne in _predicats(supabase)
    }
    catalogue = Catalogue(
        aides=appliquer_predicats(servies, verdicts, facts),
        facts=facts,
        retirees=retirees,
        surcharges=surcharges,
        predicats=verdicts,
    )
    _cache = catalogue
    _expire_a = maintenant + TTL_SECONDES
    return catalogue


# ---------------------------------------------------------------------------
# Lectures d'administration — la forme servie au front
# ---------------------------------------------------------------------------


def _entree_aide(aide: Aide, retiree: dict | None, engine_ready: bool) -> dict:
    return {
        "slug": aide.slug,
        "nom": aide.nom,
        "organisme": aide.organisme,
        "categorie": aide.categorie,
        "regions": list(aide.hard_filters.regions),
        "engineReady": engine_ready,
        "disponibilite": aide_disponibilite(aide),
        "retiree": retiree is not None,
        "motif": (retiree or {}).get("motif"),
        "retireeLe": (retiree or {}).get("created_at"),
    }


def lister_aides_admin(supabase: Client) -> list[dict]:
    """TOUT le corpus, retirées comprises — sans elles, une aide retirée par
    erreur ne pourrait plus être republiée."""
    catalogue = catalogue_effectif(supabase)
    toutes = load_all_aides()
    ready = engine_ready_aides(toutes)
    return [
        _entree_aide(toutes[slug], catalogue.retirees.get(slug), slug in ready)
        for slug in sorted(toutes)
    ]


def _surcharge_dict(surcharge: SurchargeFait | None) -> dict | None:
    if surcharge is None:
        return None
    return {
        "question": surcharge.question,
        "help": surcharge.help,
        "options": (
            [o.model_dump() for o in surcharge.options] if surcharge.options is not None else None
        ),
    }


def _entree_fait(
    key: str,
    original: FactDef,
    catalogue: Catalogue,
    *,
    pending: bool,
) -> dict:
    effectif = catalogue.facts.get(key, original)
    options = options_editables(effectif)
    index = catalogue.index
    concernees = set(index.gates.get(key, {})) | set(index.cites.get(key, {}))
    return {
        "key": key,
        "type": original.type,
        "scope": original.scope,
        "pending": pending,
        "nbAides": len(concernees),
        "original": {
            "question": original.question,
            "help": original.help,
            "options": [o.model_dump() for o in options_editables(original)],
        },
        "surcharge": _surcharge_dict(catalogue.surcharges.get(key)),
        "impactParOption": impact_options(key, options, catalogue.aides, original, index),
    }


def lister_faits_admin(supabase: Client) -> list[dict]:
    """L'ontologie complète (faits validés + en attente), avec pour chacun son
    texte d'origine, sa surcharge éventuelle et l'impact de ses réponses."""
    catalogue = catalogue_effectif(supabase)
    en_attente = set(load_pending_facts())
    originaux = {**load_facts(), **load_pending_facts()}
    return [
        _entree_fait(key, originaux[key], catalogue, pending=key in en_attente)
        for key in sorted(originaux)
    ]


# ---------------------------------------------------------------------------
# Écritures — puis invalidation, pour que l'effet soit immédiat
# ---------------------------------------------------------------------------


def retirer_aide(supabase: Client, slug: str, motif: str | None, par: str) -> dict:
    """Retire une aide du catalogue. Idempotent (upsert sur la clé primaire)."""
    supabase.table(TABLE_RETIREES).upsert(
        {"slug": slug, "motif": (motif or "").strip() or None, "retiree_par": par}
    ).execute()
    invalider()
    return _entree_aide_courante(supabase, slug)


def republier_aide(supabase: Client, slug: str) -> dict:
    """Remet l'aide au catalogue. Idempotent : republier une aide qui n'a
    jamais été retirée ne fait rien et ne se plaint pas."""
    supabase.table(TABLE_RETIREES).delete().eq("slug", slug).execute()
    invalider()
    return _entree_aide_courante(supabase, slug)


def _entree_aide_courante(supabase: Client, slug: str) -> dict:
    """La ligne à jour, telle que la liste d'administration l'affiche : le
    front remplace la sienne avec, sans relister tout le catalogue.

    Un slug absent du corpus (aide archivée depuis son retrait) rend une ligne
    minimale plutôt qu'une erreur : c'est le cas d'une republication de
    nettoyage, et elle doit aboutir.
    """
    catalogue = catalogue_effectif(supabase)
    toutes = load_all_aides()
    retiree = catalogue.retirees.get(slug)
    aide = toutes.get(slug)
    if aide is None:
        return {
            "slug": slug,
            "nom": slug,
            "organisme": "",
            "categorie": "autre",
            "regions": [],
            "engineReady": False,
            "disponibilite": "maintenant",
            "retiree": retiree is not None,
            "motif": (retiree or {}).get("motif"),
            "retireeLe": (retiree or {}).get("created_at"),
            "absenteDuCorpus": True,
        }
    return _entree_aide(aide, retiree, slug in engine_ready_aides(toutes))


def enregistrer_surcharge(
    supabase: Client, fact_key: str, brouillon: SurchargeFait, par: str
) -> dict:
    """Enregistre la reformulation d'une question — ou supprime la ligne si le
    brouillon est revenu à l'original (cf. `surcharge_utile`)."""
    original = {**load_facts(), **load_pending_facts()}[fact_key]
    utile = surcharge_utile(original, brouillon)
    if utile is None:
        return retablir_fait(supabase, fact_key)
    supabase.table(TABLE_SURCHARGES).upsert(
        {
            "fact_key": fact_key,
            "question": utile.question,
            "help": utile.help,
            "options": (
                [o.model_dump() for o in utile.options] if utile.options is not None else None
            ),
            "modifie_par": par,
        }
    ).execute()
    invalider()
    return _entree_fait_courante(supabase, fact_key)


def retablir_fait(supabase: Client, fact_key: str) -> dict:
    """Rend au fait sa formulation YAML."""
    supabase.table(TABLE_SURCHARGES).delete().eq("fact_key", fact_key).execute()
    invalider()
    return _entree_fait_courante(supabase, fact_key)


def _entree_fait_courante(supabase: Client, fact_key: str) -> dict:
    catalogue = catalogue_effectif(supabase)
    en_attente = set(load_pending_facts())
    original = {**load_facts(), **load_pending_facts()}[fact_key]
    return _entree_fait(fact_key, original, catalogue, pending=fact_key in en_attente)


# ---------------------------------------------------------------------------
# Prédicats de conditions — lectures et écritures d'administration
# ---------------------------------------------------------------------------


def _entree_condition(
    aide: Aide,
    condition: Condition,
    catalogue: Catalogue,
    ready: Mapping[str, Aide],
) -> dict:
    """Une condition modifiable, telle que le panneau l'affiche.

    `predicate` est le prédicat SERVI (surcharge comprise) : c'est lui que
    l'éditeur ouvre, pas celui du YAML, sinon rouvrir une surcharge repartirait
    de l'état d'avant.
    """
    verdict = catalogue.predicats.get((aide.slug, condition.id))
    operateur, valeurs = operateur_et_valeurs(
        condition.predicate.root if condition.predicate else {}
    )
    fait = catalogue.facts.get(condition.fact or "")
    return {
        "aideSlug": aide.slug,
        "aideNom": aide.nom,
        "conditionId": condition.id,
        "text": condition.text,
        "factKey": condition.fact,
        "question": fait.question if fait else None,
        "reponses": [
            {"id": o.id, "label": o.label} for o in (options_editables(fait) if fait else [])
        ],
        "operateur": operateur,
        "valeurs": valeurs,
        "engineReady": aide.slug in ready,
        "retiree": aide.slug in catalogue.retirees,
        "derogationPossible": condition.derogation_possible,
        "surcharge": _verdict_dict(verdict),
    }


def _verdict_dict(verdict: VerdictPredicat | None) -> dict | None:
    if verdict is None:
        return None
    return {
        "etat": verdict.etat,
        "detail": verdict.detail,
        "appliquee": verdict.appliquee,
        "predicate": verdict.ligne.predicate,
        "predicateOrigine": verdict.ligne.predicate_origine,
        "predicateYaml": verdict.predicate_yaml,
        "conditionText": verdict.ligne.condition_text,
        "conditionTextActuel": verdict.condition_text_actuel,
        "factKey": verdict.ligne.fact_key,
        "motif": verdict.ligne.motif,
    }


def lister_conditions_admin(supabase: Client) -> dict:
    """L'inventaire des conditions modifiables, plus les surcharges ORPHELINES.

    Une ligne dont l'aide ou la condition a disparu n'apparaîtrait dans aucune
    entrée de l'inventaire : elle resterait invisible et insupprimable. On la
    remonte à part, pour qu'elle puisse partir.
    """
    catalogue = catalogue_effectif(supabase)
    ready = engine_ready_aides(catalogue.aides)
    conditions = [
        _entree_condition(aide, condition, catalogue, ready)
        for aide, condition in catalogue.conditions_modifiables
    ]
    connues = {(c["aideSlug"], c["conditionId"]) for c in conditions}
    orphelines = [
        {
            "aideSlug": cle[0],
            "conditionId": cle[1],
            "surcharge": _verdict_dict(verdict),
        }
        for cle, verdict in sorted(catalogue.predicats.items())
        if cle not in connues
    ]
    return {"conditions": conditions, "orphelines": orphelines}


def condition_servie(
    supabase: Client, slug: str, condition_id: str
) -> tuple[Aide, Condition, Catalogue]:
    """L'aide et la condition telles qu'elles sont SERVIES, ou `KeyError`.

    Trois refus distincts, parce que trois causes distinctes appellent trois
    messages distincts côté route : l'aide, la condition, le mandat.
    """
    catalogue = catalogue_effectif(supabase)
    aide = catalogue.aides.get(slug)
    if aide is None:
        raise KeyError(f"Aide inconnue « {slug} »")
    condition = next((c for c in aide.conditions if c.id == condition_id), None)
    if condition is None:
        raise KeyError(f"Condition inconnue « {condition_id} » dans « {slug} »")
    if not condition_modifiable(condition, catalogue.facts):
        raise KeyError(
            f"La condition « {condition_id} » ne se modifie pas ici : "
            "seuls les gates portant sur une question à choix sont concernés"
        )
    return aide, condition, catalogue


def enregistrer_predicat(
    supabase: Client,
    slug: str,
    condition_id: str,
    predicate: Mapping,
    motif: str | None,
    par: str,
) -> dict:
    """Écrit la surcharge — ou supprime la ligne si le prédicat est revenu à
    celui du YAML (cf. `predicat_utile`).

    La comparaison se fait contre le YAML et non contre le prédicat servi :
    c'est le YAML qui reste la vérité éditoriale, et une ligne qui le recopie
    figerait la version d'avant.
    """
    _aide, condition, _catalogue = condition_servie(supabase, slug, condition_id)
    yaml_condition = next(c for c in load_all_aides()[slug].conditions if c.id == condition_id)
    origine = yaml_condition.predicate.root if yaml_condition.predicate else {}
    utile = predicat_utile(origine, predicate)
    if utile is None:
        return retablir_predicat(supabase, slug, condition_id)
    supabase.table(TABLE_PREDICATS).upsert(
        {
            "aide_slug": slug,
            "condition_id": condition_id,
            "predicate": utile,
            # Les trois témoins, figés sur ce qui a MOTIVÉ la décision.
            "condition_text": yaml_condition.text,
            "fact_key": yaml_condition.fact,
            "predicate_origine": dict(origine),
            "motif": (motif or "").strip() or None,
            "modifie_par": par,
        }
    ).execute()
    invalider()
    return _entree_condition_courante(supabase, slug, condition_id)


def retablir_predicat(supabase: Client, slug: str, condition_id: str) -> dict:
    """Rend à la condition son prédicat d'origine.

    Ne renvoie JAMAIS 404, contrairement à l'écriture : une ligne orpheline
    (aide archivée, condition disparue) doit pouvoir partir.
    """
    (
        supabase.table(TABLE_PREDICATS)
        .delete()
        .eq("aide_slug", slug)
        .eq("condition_id", condition_id)
        .execute()
    )
    invalider()
    return _entree_condition_courante(supabase, slug, condition_id)


def _entree_condition_courante(supabase: Client, slug: str, condition_id: str) -> dict:
    """La ligne à jour, que le front substitue à la sienne. Une condition sortie
    du mandat (ou du corpus) rend une entrée minimale : le rétablissement de
    nettoyage doit aboutir."""
    catalogue = catalogue_effectif(supabase)
    aide = catalogue.aides.get(slug)
    condition = next((c for c in aide.conditions if c.id == condition_id), None) if aide else None
    if aide is None or condition is None or not condition_modifiable(condition, catalogue.facts):
        return {
            "aideSlug": slug,
            "conditionId": condition_id,
            "surcharge": _verdict_dict(catalogue.predicats.get((slug, condition_id))),
            "absenteDuMandat": True,
        }
    return _entree_condition(aide, condition, catalogue, engine_ready_aides(catalogue.aides))
