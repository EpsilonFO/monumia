"""
Moteur de diagnostic déterministe : évaluation des conditions typées
(aide_conditions). Seul moteur de matching du produit.

Aucun appel réseau, aucun LLM. Source de vérité : les YAML typés
(backend/data/aides/*.yaml) chargés via aides_schema. Ne traite QUE les aides
« engine-ready » : zéro condition `untyped`. Les autres sont ignorées (le
produit n'affichera que les aides dont la donnée est compilée).

Pipeline :
  1. hard_filters (périmètre géographique, protection, propriétaire, population)
  2. évaluation des conditions `gate` contre le contexte (monument + commune +
     réponses aux faits) → éligible / potentiel / non éligible
  3. génération des questions depuis les faits manquants (dédup par fait, tri
     par nombre d'aides débloquées), avec eliminationsParOption CALCULÉ.

La sortie a la forme AideDiagnosticResult attendue par le frontend. Attention au
champ `llmEvaluation` : le nom est un vestige, il ne contient rien de LLM, juste
les verdicts déterministes par condition. Le frontend le lit sous ce nom.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from aides_schema import (
    BLOCK_OPS,
    ENUM_FACT_TYPES,
    FAIT_PORTEUR,
    OPTIONS_BOOLEEN_IMPLICITES,
    ROLE_BY_TYPE,
    Aide,
    AppliesIf,
    Condition,
    FactDef,
    Fiche,
    MultiValue,
    RangeValue,
    evaluate_predicate,
    gate_porteur,
)
from labels import (
    DEPARTEMENT_LABELS,
    ETAT_LABELS,
    FAMILLES_HERITEES,
    OWNERSHIP_LABELS,
    PROTECTION_LABELS,
    REGION_LABELS,
    TRAVAUX_LABELS,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Contexte d'évaluation
# ---------------------------------------------------------------------------


def split_reserved_answers(
    answers: dict[str, object] | None,
) -> tuple[dict[str, object], dict[str, object]]:
    """Sépare les réponses aux faits des clés RÉSERVÉES, préfixées « _ ».

    Le front transporte les métadonnées du diagnostic (aujourd'hui `_raisons`,
    les intentions de projet) dans le même dict que les réponses, parce que ce
    dict est persisté tel quel dans `monuments.questionnaire` et retransmis à
    chaque appel. Aucune clé de l'ontologie ne commence par « _ » : le préfixe
    est donc un espace de noms sûr. Les réservées ne doivent jamais atteindre
    `build_context`, sinon elles seraient traitées comme des faits inconnus.
    """
    facts_answers: dict[str, object] = {}
    reserved: dict[str, object] = {}
    for key, value in (answers or {}).items():
        (reserved if key.startswith("_") else facts_answers)[key] = value
    return facts_answers, reserved


def build_context(
    monument: dict,
    population: int | None,
    answers: dict[str, object] | None = None,
) -> dict[str, object]:
    """Construit le contexte : chemins FIELD_REGISTRY → valeur connue, sinon absent.

    Un chemin absent du dict (commune.programmes, commune.eligible_detr tant que
    l'enrichissement n'existe pas) ⇒ valeur None à l'évaluation ⇒ incertitude
    (fail-closed). `answers` mappe fact_key → réponse de l'utilisateur.

    `commune.epci` est posé par l'enrichissement commune (cf.
    routers.monuments.enrich_monument_with_population) quand la commune a un
    SIREN d'EPCI : absent pour une commune isolée, ce qui laisse les aides
    intercommunales en incertitude plutôt que de les déclarer non éligibles.
    """
    ctx: dict[str, object] = {
        "monument.nom": monument.get("nom"),
        "monument.protection": monument.get("protection"),
        "monument.proprietaire": monument.get("proprietaire"),
        "monument.etat_conservation": monument.get("etat_conservation"),
        "monument.region": monument.get("region"),
        "monument.departement_num": monument.get("departement_num"),
        "monument.travaux_envisages": monument.get("travaux_envisages") or [],
        "monument.siecle_construction": monument.get("siecle_construction"),
        "commune.population": population,
    }
    # Champs d'enrichissement commune : présents seulement si la donnée existe.
    for path in ("commune.programmes", "commune.eligible_detr", "commune.epci"):
        if path in monument:
            ctx[path] = monument[path]
    ctx["_answers"] = dict(answers or {})
    return ctx


# ---------------------------------------------------------------------------
# Évaluation d'une aide
# ---------------------------------------------------------------------------

# Verdicts par condition. oui/non/incertitude pilotent l'éligibilité ; `info`
# est un statut neutre pour les conditions non dirimantes (info, discrétionnaire,
# modulateur) — affichées pour que l'utilisateur voie TOUTES les conditions de
# l'aide, sans peser sur le verdict.
OUI, NON, INCERTITUDE, INFO = "oui", "non", "incertitude", "info"


@dataclass
class AideVerdict:
    aide: Aide
    status: str  # "eligible" | "atteignable" | "potentiel" | "non_eligible"
    criteres_remplis: list[str] = field(default_factory=list)
    criteres_non_remplis: list[str] = field(default_factory=list)
    # Sous-ensemble de criteres_non_remplis venant des hard_filters, gardé à part
    # parce qu'eux seuls sont absents de `evaluations` : sans ça, impossible de
    # savoir après coup si un refus est déductible de la seule fiche du monument.
    hard_fails: list[str] = field(default_factory=list)
    raison_ineligibilite: str | None = None
    evaluations: list[dict] = field(default_factory=list)
    # fact_key → liste de (condition, predicate) des gates user_fact en incertitude
    missing_facts: dict[str, list[Condition]] = field(default_factory=dict)
    # Plans d'action des gates en échec sur un fait porteur d'un `levier`
    # (cf. aides_schema.Levier) — ce sont eux qui rendent l'aide « atteignable ».
    leviers: list[dict] = field(default_factory=list)
    # fact_key → conditions SYNTHÉTIQUES portant le prédicat d'applicabilité, pour
    # les faits « passerelles » : ceux qu'un `applies_if.fact` interroge sans que
    # personne ne les pose. Sans eux, une condition dont l'applicabilité est
    # indéterminée reste éternellement en incertitude (cf. _gateway_condition).
    gateway_facts: dict[str, list[Condition]] = field(default_factory=dict)


def _tranche_repr(option_id: str):
    """Valeur représentative d'une tranche numérique depuis son id d'option.

    Miroir exact de `_numeric_tranches` (lt{n}→n-1, ge{n}→n, {lo}_{hi}→lo) : la
    valeur de vérité d'un prédicat de seuil est constante dans la tranche, donc
    évaluer au représentant est exact. None si l'id n'est pas une tranche connue.
    """

    def _num(s: str):
        return float(s) if "." in s else int(s)

    try:
        if option_id.startswith("lt"):
            return _num(option_id[2:]) - 1
        if option_id.startswith("ge"):
            return _num(option_id[2:])
        if "_" in option_id:
            return _num(option_id.split("_", 1)[0])
    except (ValueError, TypeError):
        return None
    return None


def _normalize_answer(fact: FactDef | None, raw):
    """Convertit une réponse du QCM (id d'option) vers la valeur typée attendue
    par les prédicats : réponse d'un booléen → sa `valeur` déclarée, tranche
    numérique → représentant, enum → id (déjà la valeur), multi_enum →
    MultiValue des ids cochés, `skip`/option `unknown` → None (fait non
    renseigné).

    Sans cette normalisation, passer l'id brut « non » à un prédicat `eq: false`
    donnerait `"non" == False` → False, marquant l'aide non éligible à tort.

    Un fait `boolean` qui ne déclare rien retombe sur OPTIONS_BOOLEEN_IMPLICITES
    (« oui » → True, « non » → False) : ajouter des options à un booléen est donc
    strictement inerte pour les réponses déjà persistées, puisque R1 impose que
    le couple y survive. Une option de `valeur` nulle rend None — le fait reste
    inconnu, l'aide n'est jamais écartée.

    Un id d'option INCONNU du fait vaut fait non renseigné, jamais valeur
    brute : les réponses sont persistées dans `projets.questionnaire` et les
    options d'un fait peuvent changer sous elles (correction de `facts.yaml`,
    reformulation depuis /admin). Une réponse devenue orpheline éliminerait
    sinon des aides pour toujours, sans que personne puisse la corriger — c'est
    exactement le cas que le principe fail-closed du moteur doit couvrir.
    """
    if raw is None or raw == "skip":
        return None
    if fact is None:
        return raw
    if fact.type == "boolean":
        if isinstance(raw, bool):
            return raw
        for opt in fact.options or OPTIONS_BOOLEEN_IMPLICITES:
            if opt.id == raw:
                return None if opt.unknown else opt.valeur
        return None
    if fact.type == "multi_enum":
        # Le front envoie une liste d'ids ; une réponse d'avant le passage en
        # choix multiple (chaîne unique, déjà persistée dans
        # `monuments.questionnaire`) reste lisible telle quelle.
        raws = raw if isinstance(raw, (list, tuple)) else [raw]
        connues = {o.id for o in fact.options or [] if not o.unknown}
        kept = [v for v in raws if isinstance(v, str) and v in connues]
        return MultiValue(kept) if kept else None
    if fact.type == "enum":
        for opt in fact.options or []:
            if opt.id == raw:
                return None if opt.unknown else raw
        return None
    if fact.type in ("integer", "number"):
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            return raw
        return _tranche_repr(raw) if isinstance(raw, str) else None
    return raw


# Siècles tels qu'ils s'écrivent dans les notices Mérimée et dans le champ libre
# de la fiche : « 15e siècle », « XVIIe siècle », « 12e s.;13e s. », « 14e - 18e
# siècle », « 2e moitié 19e siècle ». Le mot « siècle » (ou « s. ») est exigé
# APRÈS l'ordinal, sinon « 1ère moitié 19e siècle » se lirait comme le 1er
# siècle ; la frontière de mot en tête écarte les fins de mots (« Vieux siècle »
# n'est pas un 10e siècle).
#
# Le premier groupe capture la CHAÎNE d'ordinaux qui partagent le mot « siècle »
# final (« 14e - 18e siècle », « 14e, 15e et 16e siècles ») : sans lui, seul le
# dernier serait lu, et une fourchette de cinq siècles se réduirait au dernier —
# un intervalle trop étroit tranche des critères qu'il ne devrait pas trancher.
_ORDINAL = r"(?:\d{1,2}|[ivx]{1,5})\s*(?:er|ère|ere|ème|eme|e)?"
_SEPARATEUR = r"(?:[-–—/,;]|à|au|et)"
_SIECLE_RE = re.compile(
    rf"\b((?:{_ORDINAL}\s*{_SEPARATEUR}\s*)*)({_ORDINAL})\s*(?:s\.|siècles?|siecles?)",
    re.IGNORECASE,
)
_ORDINAL_RE = re.compile(r"\b(\d{1,2}|[ivx]{1,5})", re.IGNORECASE)

_ROMAINS = {"i": 1, "v": 5, "x": 10}


def _siecle_romain(brut: str) -> int | None:
    """« XVII » → 17. None si ce n'est pas un nombre romain bien formé."""
    total, precedent = 0, 0
    for lettre in reversed(brut.lower()):
        valeur = _ROMAINS.get(lettre)
        if valeur is None:
            return None
        total += -valeur if valeur < precedent else valeur
        precedent = max(precedent, valeur)
    return total or None


def _annee_depuis_siecle(brut: object) -> RangeValue | None:
    """« 14e - 18e siècle » → intervalle d'années 1301-1400, ou None si illisible.

    Deux principes, l'un sémantique et l'autre prudentiel :

    - Quand la notice cite PLUSIEURS siècles, ce sont les campagnes successives
      du bâtiment. Sa construction, elle, est la PREMIÈRE : un édifice « 14e -
      18e siècle » est bâti au 14e puis remanié jusqu'au 18e. C'est le sens de
      la question posée à l'utilisateur (« en quelle année le bâtiment a-t-il
      été construit ? »), et c'est ce que vérifient les financeurs qui exigent
      un édifice « antérieur à 1800 ».
    - Un siècle ne donne pas une année : il donne une fourchette, rendue telle
      quelle plutôt que réduite à une médiane inventée. Le moteur ne tranche
      alors que les seuils réellement tranchés — « antérieur à 1800 » est acquis
      pour tout le 14e siècle — et pose la question pour les autres. Aucune
      élimination sur une approximation.

    Les mentions non chiffrées des notices (« Moyen Age », « Antiquité ») ne
    donnent rien : la question reste posée, comme avant.
    """
    if not isinstance(brut, str):
        return None
    siecles = []
    for chaine, dernier in _SIECLE_RE.findall(brut):
        for token in _ORDINAL_RE.findall(chaine) + _ORDINAL_RE.findall(dernier):
            siecle = int(token) if token.isdigit() else _siecle_romain(token)
            if siecle is not None and 1 <= siecle <= 21:
                siecles.append(siecle)
    if not siecles:
        return None
    premier = min(siecles)
    return RangeValue(((premier - 1) * 100 + 1, premier * 100))


# Noms d'édifices religieux, tels qu'ils s'écrivent en tête d'une notice
# Mérimée ou d'une fiche saisie à la main : « Église Saint-Martin », « Ancienne
# chapelle des Pénitents », « L\'église paroissiale ».
_TETE_RELIGIEUSE_RE = re.compile(
    r"^(?:(?:l|la|le|les|ancien|ancienne|vieux|vieille|petit|petite|grand|grande)\s+)*"
    r"(?:eglises?|chapelles?)\b"
)


def _sans_accents(texte: str) -> str:
    """Minuscules, sans accents, ponctuation ramenée à des espaces."""
    nfkd = unicodedata.normalize("NFKD", texte.lower())
    sans = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", sans).strip()


def _eglise_ou_chapelle_depuis_nom(brut: object) -> bool | None:
    """« Église Saint-Martin » → True. None quand le nom ne dit rien.

    Jamais False : un nom qui ne porte pas le mot ne prouve pas que l'édifice
    n'est pas une église (« Notre-Dame de X », « Collégiale », un nom donné par
    le propriétaire). L'absence laisse donc la question posée — fail-closed.

    Le mot doit être la TÊTE du nom : « Château de la Chapelle-Rainsouin » est
    un toponyme, pas une chapelle. C'est aussi la forme des notices Mérimée,
    qui commencent toujours par le type d'édifice.
    """
    if not isinstance(brut, str):
        return None
    return True if _TETE_RELIGIEUSE_RE.match(_sans_accents(brut)) else None


# Comment un fait lit son `auto_source` quand la valeur brute de la fiche n'a
# pas son type (un siècle n'est pas une année, un nom n'est pas un booléen).
# Sans entrée ici, la valeur du contexte est reprise telle quelle.
AUTO_SOURCE_DERIVERS = {
    "annee_construction": _annee_depuis_siecle,
    "edifice_eglise_ou_chapelle": _eglise_ou_chapelle_depuis_nom,
    # Une église ou une chapelle est, par construction, un édifice cultuel.
    "edifice_cultuel": _eglise_ou_chapelle_depuis_nom,
}


def _faire_vivre_depuis_raisons(raisons: set[str]) -> bool | None:
    """Une intention non cochée répond d'avance : pas de « faire vivre le lieu »,
    donc ni festival, ni projet artistique ou culturel.

    L'inverse n'est jamais vrai — « Faire vivre et ouvrir le lieu » couvre
    autant des visites pérennes qu'une exposition d'un été —, d'où le None qui
    laisse la question posée là où elle discrimine vraiment.
    """
    return None if "valorisation_rayonnement" in raisons else False


# Faits que l'étape « Votre projet » répond d'avance, par déduction des
# intentions cochées. Pendant de AUTO_SOURCE_DERIVERS : même principe (ne pas
# demander ce que l'on sait déjà), mais la source est l'intention déclarée et
# non la fiche du monument. Ne jamais y mettre une déduction qui pourrait
# ÉCARTER une aide : une intention non cochée est une indication sur le projet,
# pas une preuve — fail-closed, la déduction rend None et la question survit.
FAITS_DEDUITS_DES_RAISONS: dict[str, Callable[[set[str]], object]] = {
    "projet_evenementiel_ponctuel": _faire_vivre_depuis_raisons,
    # Même déduction : un projet ou une action artistique ou culturelle
    # (exposition, spectacle, résidence…) relève de « faire vivre le lieu ».
    # Cohérent avec le `help` du fait : « répondez non si votre projet porte
    # uniquement sur des travaux sur le bâtiment ».
    "projet_artistique_ou_culturel": _faire_vivre_depuis_raisons,
    # `prevoit_programme_valorisation` y avait une déduction positive (cocher
    # « Faire vivre le lieu » EST un programme de valorisation). Le fait est
    # devenu une promesse le 2026-09-23 et ne se demande plus : la déduction
    # est partie avec lui.
}


def deduire_faits_des_raisons(
    raisons: set[str],
    answers: dict[str, object],
    facts: dict[str, FactDef],
) -> dict[str, object]:
    """Complète les réponses par les faits déductibles des intentions déclarées.

    Poser à un propriétaire qui refait sa toiture « votre projet est-il un
    festival ? » se lit comme une panne : l'étape « Votre projet » a déjà dit
    non. Le filtrage `hors_projet` ne suffit pas, parce qu'une aide multi-raison
    (Fondation CA Pays de France : restauration ET valorisation) reste candidate
    pour un pur chantier et traîne ses faits événementiels avec elle.

    La réponse de l'utilisateur prime toujours : la déduction ne remplit qu'un
    fait qu'il n'a pas renseigné (une réponse « je ne sais pas » n'en est pas
    une). `raisons` vide ⇒ aucune déduction, comme `hors_projet` ne filtre rien :
    un questionnaire d'avant l'étape ne dit rien des intentions.
    """
    if not raisons:
        return answers
    complete = dict(answers)
    for fact_key, deduire in FAITS_DEDUITS_DES_RAISONS.items():
        if _normalize_answer(facts.get(fact_key), complete.get(fact_key)) is not None:
            continue
        valeur = deduire(raisons)
        if valeur is not None:
            complete[fact_key] = valeur
    return complete


# Faits de PÉRIMÈTRE qu'une famille cochée rend plausibles : fait → familles qui
# le rendent plausible. Pendant de FAITS_DEDUITS_DES_RAISONS un cran plus fin —
# avoir coché « spectacles » répond d'avance « non » à « votre projet est-il un
# hébergement touristique ? ».
#
# Deux faits de scope `monument` (`bien_parc_jardin_ou_arboretum`,
# `possede_orgue_a_tuyaux`) et le `multi_enum` `projet_dimension_environnementale`
# sont volontairement ABSENTS : les deux premiers décrivent le bien et non le
# projet (un jardin ne cesse pas d'exister parce qu'on monte un festival), le
# troisième n'est pas un périmètre.
FAITS_DEDUITS_DES_FAMILLES: dict[str, frozenset[str]] = {
    "projet_lieu_diffusion_culturelle": frozenset({"spectacles_manifestations"}),
    "porteur_compagnie_artistique": frozenset({"spectacles_manifestations"}),
    "porteur_structure_musicale": frozenset({"spectacles_manifestations"}),
    "projet_hebergement_touristique": frozenset({"hebergement_touristique"}),
    "projet_developpement_touristique": frozenset(
        {"hebergement_touristique", "tourisme_visite", "activite_economique_lieu"}
    ),
    "projet_equipement_culturel": frozenset(
        {"mediation_numerique_expositions", "spectacles_manifestations"}
    ),
    "projet_artistique_ou_culturel": frozenset(
        {"mediation_numerique_expositions", "spectacles_manifestations"}
    ),
    "projet_lie_chasse_peche_nature": frozenset({"eau_nature_domaine", "parcs_jardins_paysages"}),
    "projet_amenagement_urbain_nature_en_ville": frozenset({"parcs_jardins_paysages"}),
    "projet_support_insertion_ou_formation": frozenset(
        {"restauration_bati", "activite_economique_lieu"}
    ),
}


# Miroir POSITIF, et volontairement beaucoup plus étroit : les faits qu'une
# famille COCHÉE ne rend pas seulement plausibles mais certains, parce qu'ils
# redisent ce que la famille déclare déjà. Cocher « Spectacles et
# manifestations » puis s'entendre demander « votre projet est-il une action
# artistique ou culturelle ? » se lit comme une panne. Même condition que pour
# toute déduction positive : elle ne doit pouvoir écarter AUCUNE aide.
#
# Trois entrées, et la garde de `_retournerait_contre` les revérifie à chaque
# diagnostic plutôt que de faire confiance à cette liste. Mesuré sur le corpus
# au 2026-09-18 : 9 et 35 références pour les deux premières, aucune qu'un
# « oui » réfute.
#
# La troisième, `projet_hebergement_touristique`, n'a pu entrer qu'après la
# SCISSION de `tourisme_hebergement` (2026-09-22) : tant que la même famille
# couvrait les gîtes ET les sites de visite, cocher la tuile ne disait pas que
# le projet était un hébergement, et trois aides qui gatent `eq: false` sur ce
# fait faisaient tomber la garde pour tout le monde. Deux d'entre elles sont
# désormais `tourisme_visite` et sortent par `hors_famille` avant la déduction ;
# qui coche les DEUX tuiles garde donc la question, et c'est légitime — c'est
# alors elle qui tranche entre les aides d'hébergement et les autres.
#
# `projet_evenementiel_ponctuel` n'y est PAS, et c'est le cas intéressant :
# cinq aides le gatent `eq: false`, un « oui » déduit les ferait tomber
# « écartées par vos réponses » sur une question jamais posée. Ponctuel ou
# pérenne est précisément ce que « spectacles » ne dit pas — la question reste
# donc posée, et elle est la seule des trois à discriminer.
#
# On ne lit ici que les familles DÉCLARÉES : celles qu'une finalité implique
# sont une indication, pas une déclaration, et ne peuvent pas porter un « oui ».
FAITS_DEDUITS_VRAI_DES_FAMILLES: dict[str, frozenset[str]] = {
    "projet_artistique_ou_culturel": frozenset(
        {"spectacles_manifestations", "mediation_numerique_expositions"}
    ),
    "projet_lieu_diffusion_culturelle": frozenset({"spectacles_manifestations"}),
    "projet_hebergement_touristique": frozenset({"hebergement_touristique"}),
}


def _retournerait_contre(aide: Aide, fact_key: str, valeur: bool = False) -> bool:
    """Répondre `valeur` à ce fait retournerait-il cette aide contre elle-même ?

    Deux façons : son PÉRIMÈTRE porte sur le fait et la réponse l'en sort
    (`hors_perimetre` l'écarte alors du résultat), ou l'un de ses GATES porte
    sur le fait et la réponse le réfute (l'aide tombe « écartée par vos
    réponses », sur une question que l'utilisateur n'a jamais vue).

    Forme exacte de la garde de `deduire_faits_des_familles`, dans les deux
    sens, et plus sûre que la coïncidence des tags : elle ne suppose rien du
    catalogue, et elle vaut donc aussi pendant que le backfill des familles est
    en cours. `valeur` par défaut à `False` : c'est la déduction négative, de
    loin la plus fréquente.
    """
    if (
        aide.applies_if
        and aide.applies_if.fact == fact_key
        and evaluate_predicate(aide.applies_if.predicate.root, valeur) is False
    ):
        return True
    return any(
        c.fact == fact_key
        and c.effect == "gate"
        and c.predicate is not None
        and evaluate_predicate(c.predicate.root, valeur) is False
        for c in aide.conditions
    )


def deduire_faits_des_familles(
    effectives: set[str],
    declarees: set[str],
    answers: dict[str, object],
    facts: dict[str, FactDef],
    candidates: dict[str, Aide],
) -> dict[str, object]:
    """Répond « non » d'avance aux faits de périmètre qu'aucune famille cochée
    ne rend plausibles — mais seulement quand c'est SÛR.

    La garde est le cœur de la fonction. `hors_famille` promet un fail-open PAR
    AIDE : une aide non taguée passe toujours. Or la déduction agit PAR FAIT, et
    répondre « non » à un fait écarte du même coup, via `hors_perimetre` ou via
    un gate, les aides que le filtrage venait de garder. On ne déduit donc que si
    la valeur déduite ne RETOURNE aucune aide candidate contre elle-même
    (cf. `_retournerait_contre`). Sinon `None` : la question reste posée
    (fail-closed).

    Sans cette garde : `feder-normandie-tourisme-responsable` (périmètre
    `projet_developpement_touristique`, pas de famille) serait écartée par la
    bande ; une aide « festival touristique » taguée `spectacles` serait gardée
    par `hors_famille` puis tuée par la déduction ; et les treize aides du
    corpus qui gatent `eq: true` sur un fait de la table sans en faire leur
    périmètre tomberaient « écartées par vos réponses » sans réponse.

    Ce qui reste permis, et c'est tout le gain : résoudre une EXCLUSION. Une
    aide de spectacles qui exige « le projet n'est pas un hébergement
    touristique » n'a plus besoin de poser la question à qui vient de cocher
    « spectacles ».
    """
    if not declarees:
        return answers
    complete = dict(answers)
    for fact_key, familles_du_fait in FAITS_DEDUITS_DES_FAMILLES.items():
        if _normalize_answer(facts.get(fact_key), complete.get(fact_key)) is not None:
            continue
        if familles_du_fait & effectives:
            continue  # une famille cochée rend le fait plausible : on demande
        if any(_retournerait_contre(a, fact_key) for a in candidates.values()):
            continue
        complete[fact_key] = False
    for fact_key, familles_du_fait in FAITS_DEDUITS_VRAI_DES_FAMILLES.items():
        if _normalize_answer(facts.get(fact_key), complete.get(fact_key)) is not None:
            continue
        if not (familles_du_fait & declarees):
            continue  # aucune famille cochée ne l'affirme : on demande
        if any(_retournerait_contre(a, fact_key, True) for a in candidates.values()):
            continue
        complete[fact_key] = True
    return complete


# Faits qu'une AUTRE réponse du questionnaire rend inutiles à demander. Pendant
# de FAITS_DEDUITS_DES_RAISONS, avec une réponse pour source au lieu de
# l'intention : fait déduit → (fait source, {réponse source → valeur déduite}).
#
# « Fermé au public, sans projet d'ouverture » répond d'avance « ouvert 0 jour
# par an » : poser la seconde question juste après la première se lit comme une
# panne. L'inverse ne se déduit pas — 0 jour aujourd'hui peut devenir accessible
# après les travaux.
#
# La source est ici un fait à choix MULTIPLE : la déduction ne vaut que si la
# case déduisante est la SEULE cochée (cf. deduire_faits_des_faits). C'est ce que
# veut la sémantique existentielle du MultiValue, et la table garde des
# identifiants d'option nus, ceux-là mêmes que compare _depends_on_deduction.
#
# Deux effets, qui doivent rester d'accord : côté serveur la valeur déduite
# entre dans le contexte comme une réponse (celle de l'utilisateur prime) ;
# côté questionnaire la question déduite se branche sur sa source (`dependsOn`,
# cf. _depends_on_deduction) et se pose avant elle, si bien que le front ne la
# montre plus dès que la source y répond.
FAITS_DEDUITS_DES_FAITS: dict[str, tuple[str, dict[object, object]]] = {
    "jours_ouverture_public_par_an": ("ouverture_public", {"aucune": 0}),
    # « Ce projet ne comporte pas de travaux » répond d'avance « budget de
    # travaux : 0 € » : les gates `gte` d'un programme de chantier échouent
    # (l'aide part en « écartée par vos réponses », ce qu'elle est), et la
    # question disparaît du QCM au profit de sa source.
    "budget_travaux_estime": ("etat_travaux", {"aucun": 0}),
    # « Mes travaux relèvent de l'entretien courant » répond d'avance « non »
    # à « mon programme est-il une création / extension / rénovation
    # fondamentale ? », qui exclut l'entretien courant dans son énoncé même.
    # Sans ça, les deux questions se suivaient en se contredisant.
    #
    # Dans CE sens seulement, et pour deux raisons. La réciproque serait tout
    # aussi vraie (une rénovation fondamentale n'est pas de l'entretien
    # courant), mais la SOURCE d'une déduction se pose avant sa cible : c'est
    # la question la plus partagée qui doit passer devant (13 aides contre 5),
    # pas une question d'hôtellerie posée à tout le monde. Et deux entrées
    # croisées feraient un cycle dans la table, que ni l'ordre des questions ni
    # `_depends_on_deduction` ne savent trancher.
    #
    # Les deux faits ne se FUSIONNENT pas pour autant : « mise aux normes
    # seule » et « simple rafraîchissement » ne sont ni l'un ni l'autre, et
    # répondent non aux deux questions.
    "projet_renovation_fondamentale": ("travaux_entretien_courant", {True: False}),
}


def _meme_valeur(a: object, b: object) -> bool:
    """Égalité stricte de type : `0 == False` en Python, pas ici."""
    return type(a) is type(b) and a == b


def deduire_faits_des_faits(
    answers: dict[str, object],
    facts: dict[str, FactDef],
) -> dict[str, object]:
    """Complète les réponses par les faits déductibles d'une autre réponse.

    La réponse de l'utilisateur prime toujours : la déduction ne remplit qu'un
    fait qu'il n'a pas renseigné. Source inconnue (non répondue, « je ne sais
    pas ») ⇒ rien n'est déduit et la question survit (fail-closed).
    """
    complete = dict(answers)
    for fact_key, (source_key, table) in FAITS_DEDUITS_DES_FAITS.items():
        if _normalize_answer(facts.get(fact_key), complete.get(fact_key)) is not None:
            continue
        source = _normalize_answer(facts.get(source_key), complete.get(source_key))
        if source is None:
            continue
        # Source à choix multiple : on ne conclut que d'une sélection d'UNE case,
        # et la table se compare alors à son identifiant nu. Cocher « fermé au
        # public » EN PLUS d'« ouvert lors des Journées du patrimoine » est une
        # sélection qui se contredit : on n'en déduit rien (fail-closed).
        if isinstance(source, MultiValue):
            if len(source) != 1:
                continue
            source = source[0]
        for valeur_source, deduit in table.items():
            if _meme_valeur(source, valeur_source):
                complete[fact_key] = deduit
                break
    return complete


def _answered_value(ctx: dict, fact_key: str, facts: dict[str, FactDef]):
    """Valeur RÉPONDUE par l'utilisateur pour ce fait (None si non renseignée)."""
    return _normalize_answer(facts.get(fact_key), ctx.get("_answers", {}).get(fact_key))


def _auto_fact_value(fact_key: str, fact: FactDef | None, ctx: dict):
    """Valeur d'un fait DÉDUITE de la fiche, via son `auto_source` (None sinon).

    C'est ce qui évite de demander l'année de construction d'un monument dont la
    notice donne déjà le siècle. La réponse de l'utilisateur, elle, prime
    toujours : elle est plus précise que la déduction.
    """
    if fact is None or not fact.auto_source:
        return None
    brut = ctx.get(fact.auto_source)
    if brut is None:
        return None
    deriver = AUTO_SOURCE_DERIVERS.get(fact_key)
    return deriver(brut) if deriver else brut


def _resolve_fact_value(ctx: dict, fact_key: str, facts: dict[str, FactDef]):
    """Valeur typée d'un fait : la réponse de l'utilisateur, sinon la fiche."""
    valeur = _answered_value(ctx, fact_key, facts)
    if valeur is not None:
        return valeur
    return _auto_fact_value(fact_key, facts.get(fact_key), ctx)


def _evaluate_clause(clause: AppliesIf | None, ctx: dict, facts: dict[str, FactDef]) -> bool | None:
    """Évalue une clause d'applicabilité. None = indéterminé (fail-closed).

    Sert aux deux niveaux : la condition (`Condition.applies_if`) et l'aide
    entière (`Aide.applies_if`, son périmètre).
    """
    if clause is None:
        return True
    pred = clause.predicate.root
    if clause.field:
        return evaluate_predicate(pred, ctx.get(clause.field))
    return evaluate_predicate(pred, _resolve_fact_value(ctx, clause.fact, facts))


def _applies(cond: Condition, ctx: dict, facts: dict[str, FactDef]) -> bool | None:
    """La condition s'applique-t-elle à ce profil ? None = indéterminé (fail-closed)."""
    return _evaluate_clause(cond.applies_if, ctx, facts)


# Fait « vide », pour que `_pertinence` et `_scoped_conditions` lisent
# `pertinent_si` sans un `if` de plus : une condition peut citer un fait absent
# de l'ontologie (le lint le refuse, mais le moteur ne doit pas casser pour
# autant).
_SANS_FAIT = FactDef(type="boolean", scope="projet", question="")


def _pertinence(fact_key: str | None, ctx: dict, facts: dict[str, FactDef]) -> bool | None:
    """Le fait a-t-il une valeur pour ce profil ? (clause `pertinent_si` du fait)

    Une seule question, posée aux trois endroits qui en tirent une conséquence :
    le BRANCHEMENT de la question (`_depends_on_pertinence`), l'évaluation de
    la CONDITION qui cite le fait, et le PÉRIMÈTRE d'une aide posé dessus.

    True quand le fait ne déclare pas de porte — le cas courant. False dit que
    le fait n'a pas de valeur ici : « quel type d'hébergement ? » ne veut rien
    dire sans projet d'hébergement, et une exclusion posée dessus ne doit
    écarter personne. None = la porte est inconnue (fail-closed).
    """
    clause = (facts.get(fact_key or "") or _SANS_FAIT).pertinent_si
    if clause is None:
        return True
    return _evaluate_clause(clause, ctx, facts)


def hors_perimetre(aide: Aide, ctx: dict, facts: dict[str, FactDef]) -> bool:
    """Vrai si l'utilisateur a répondu que cette aide ne concerne pas son projet.

    Fail-closed : tant que le fait de périmètre est inconnu, l'aide reste
    candidate (et la question est posée). Seule une réponse explicitement
    négative l'écarte.

    Une PORTE fermée vaut réponse négative : une aide dont tout le périmètre est
    « votre hébergement est-il un hôtel ? » ne concerne pas quelqu'un qui n'a
    pas de projet d'hébergement. Sans cette règle, l'aide restait « potentielle »
    pour toujours — son périmètre en incertitude sur un fait qu'on ne lui
    demanderait jamais.
    """
    if aide.applies_if is None:
        return False
    if _pertinence(aide.applies_if.fact, ctx, facts) is False:
        return True
    return _evaluate_clause(aide.applies_if, ctx, facts) is False


def _scoped_conditions(aide: Aide, facts: dict[str, FactDef]) -> list[Condition]:
    """Conditions de l'aide, chacune héritant de la clause qui la gouverne.

    Deux clauses peuvent être reportées, par ordre de priorité DÉCROISSANTE :

    1. la clause PROPRE de la condition, toujours gardée : elle est la plus
       spécifique, et le branchement conditionnel se désactive alors de lui-même
       (fail-closed, la question est posée) ;
    2. le PÉRIMÈTRE de l'aide (`Aide.applies_if`), reporté sur chacune de ses
       conditions : le fait de périmètre est posé comme fait passerelle, et
       chaque question de l'aide en hérite d'un `dependsOn`. Une aide de 27
       conditions se déclare ainsi en une ligne de YAML ;
    3. la DÉPENDANCE INTRINSÈQUE du fait gaté (`FactDef.pertinent_si`) :
       « depuis combien d'années les travaux sont-ils achevés ? » n'a de sens
       que si `etat_travaux = acheves`. Déclarée UNE FOIS sur le fait au lieu
       d'être recopiée sur chaque condition qui le cite.

    Le périmètre passe avant la dépendance du fait parce qu'une condition ne
    porte qu'UNE clause, et que la première question à trancher est « cette aide
    me concerne-t-elle ? ».

    Cette fonction n'est plus le seul lecteur de `pertinent_si`, et ce report
    n'en est plus que la voie la plus COURTE — celle qui ne coûte aucun cas
    particulier quand la condition n'a pas de clause. Les deux clauses plus
    spécifiques lui prennent sa place sans rien lui faire perdre : `_pertinence`
    est consultée à part dans `evaluate_aide` (la condition est ignorée, l'aide
    sort du périmètre) et dans `_depends_on_pertinence` (la question se branche
    sur la porte). Perdre le report ne coûte donc plus rien du tout.

    Un gate qui porte sur le fait de sa propre clause n'hérite de rien : il
    serait sa propre condition d'applicabilité.
    """

    def clause_de(cond: Condition) -> AppliesIf | None:
        if cond.applies_if is not None:
            return None  # la sienne, plus spécifique, est gardée
        for clause in (aide.applies_if, (facts.get(cond.fact or "") or _SANS_FAIT).pertinent_si):
            if clause is not None and cond.fact != clause.fact:
                return clause
        return None

    reportees = [(c, clause_de(c)) for c in aide.conditions]
    if all(clause is None for _, clause in reportees):
        return aide.conditions
    return [
        c if clause is None else c.model_copy(update={"applies_if": clause})
        for c, clause in reportees
    ]


def _fmt_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(round(value, 2))


def _numeric_gap(predicate: dict, value, fact: FactDef) -> str | None:
    """Écart chiffré entre la réponse et le seuil d'un gate numérique en échec.

    « Il vous manque 8 jours/an » vaut mieux que « critère non satisfait » : le
    propriétaire sait immédiatement si l'effort est à sa portée. On réutilise
    `_normalize_boundary` pour que les seuils STRICTS donnent le bon écart
    (`gt: 0` sur un entier ⇒ frontière 1, donc il manque 1 et pas 0).

    None dès que l'écart n'a pas de sens : booléen, enum, combinateur, seuil non
    numérique. Jamais d'approximation.
    """
    if len(predicate) != 1:
        return None
    op, bound = next(iter(predicate.items()))
    if op not in ("gte", "gt", "lte", "lt"):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(bound, bool) or not isinstance(bound, (int, float)):
        return None

    is_integer = fact.type == "integer"
    frontier = _normalize_boundary(op, bound, is_integer)
    unit = f" {fact.unit}" if fact.unit else ""
    if op in ("gte", "gt"):
        missing = frontier - value
        return f"Il en manque {_fmt_number(missing)}{unit}" if missing > 0 else None
    excess = value - frontier + (1 if is_integer else 0)
    return f"Vous dépassez de {_fmt_number(excess)}{unit}" if excess > 0 else None


def _levier_plan(cond: Condition, fact: FactDef, value) -> dict:
    """Plan d'action d'un fait à levier : gate en échec, ou démarche d'un
    `manual_check` qui cite ce levier (`cond.levier`)."""
    levier = fact.levier
    assert levier is not None  # garanti par l'appelant
    plan = {
        "factId": cond.fact or cond.levier,
        "critere": cond.text,
        "conditionId": cond.id,
        "resume": levier.resume,
        "demarche": levier.demarche,
        "organisme": levier.organisme,
        "cout": levier.cout,
        "delai": levier.delai,
        "url": levier.url,
    }
    ecart = _numeric_gap(cond.predicate.root, value, fact) if cond.predicate else None
    if ecart:
        plan["ecart"] = ecart
    return plan


def _perimetre_texte(fact: FactDef | None) -> str:
    """Libellé du critère de périmètre, affiché dans l'analyse d'éligibilité."""
    return fact.question if fact else "Cette aide ne concerne que certains projets."


def _perimetre_condition(aide: Aide, fact: FactDef | None) -> Condition:
    """Gate synthétique sur le fait de périmètre d'une aide, pour le poser."""
    assert aide.applies_if is not None and aide.applies_if.fact  # garanti par l'appelant
    return Condition.model_validate(
        {
            "id": "perimetre",
            "text": _perimetre_texte(fact),
            "kind": "user_fact",
            "fact": aide.applies_if.fact,
            "predicate": aide.applies_if.predicate.root,
        }
    )


def _gateway_condition(cond: Condition) -> Condition:
    """Projette une condition sur son fait PASSERELLE (`applies_if.fact`).

    La condition d'origine porte son prédicat sur son propre fait ; ce qu'on veut
    poser à l'utilisateur, c'est le fait qui décide si elle s'applique. On
    fabrique donc un gate synthétique { fact: applies_if.fact, predicate:
    applies_if.predicate } : le générateur de questions en tire des options
    correctes (bornes numériques, options d'enum) sans cas particulier.

    Ce gate synthétique ne sert QU'À poser la question : il ne participe pas au
    calcul des éliminations (répondre « la condition ne s'applique pas » libère
    l'aide, ça ne l'élimine jamais).
    """
    assert cond.applies_if is not None and cond.applies_if.fact  # garanti par l'appelant
    return Condition.model_validate(
        {
            "id": cond.id,
            "text": cond.text,
            "kind": "user_fact",
            "fact": cond.applies_if.fact,
            "predicate": cond.applies_if.predicate.root,
        }
    )


def _porte_condition(clause: AppliesIf, fact: FactDef | None) -> Condition:
    """Gate synthétique sur la PORTE d'un fait (`FactDef.pertinent_si`)."""
    assert clause.fact  # garanti par l'appelant
    return Condition.model_validate(
        {
            "id": "pertinence",
            "text": _perimetre_texte(fact),
            "kind": "user_fact",
            "fact": clause.fact,
            "predicate": clause.predicate.root,
        }
    )


def _poser_porte(
    gateway_facts: dict[str, list[Condition]],
    fact_key: str | None,
    ctx: dict,
    facts: dict[str, FactDef],
) -> None:
    """Pose la PORTE d'un fait comme fait passerelle, tant qu'elle est inconnue.

    Sans elle, la question du fait porté n'aurait rien à quoi se brancher —
    `_depends_on_pertinence` renonce (fail-closed) et la question part à tout
    le monde. `_scoped_conditions` reporte déjà la porte sur les conditions qui
    n'ont pas de clause propre ; cette fonction couvre les deux cas où une
    clause plus spécifique lui a pris la place : le PÉRIMÈTRE d'une aide et la
    clause PROPRE d'une condition.

    Ne repose rien si le fait de la porte est déjà posé : une question suffit.
    """
    clause = (facts.get(fact_key or "") or _SANS_FAIT).pertinent_si
    if clause is None or not clause.fact or clause.fact in gateway_facts:
        return
    if _evaluate_clause(clause, ctx, facts) is not None:
        return  # porte tranchée : soit le fait est pertinent, soit tout est écarté
    gateway_facts[clause.fact] = [_porte_condition(clause, facts.get(clause.fact))]


# ---------------------------------------------------------------------------
# Le marqueur `porteurs_concernes`, rendu exécutable
# ---------------------------------------------------------------------------


def _porteur_admis(fact: FactDef, ctx: dict, facts: dict[str, FactDef]) -> bool | None:
    """Le porteur déclaré fait-il partie de ceux que ce fait concerne ?

    `True` : il en fait partie (ou le fait ne marque personne — le cas courant).
    `False` : il n'en fait pas partie, la condition doit ÉCHOUER.
    `None` : le porteur est inconnu, la condition reste une incertitude et la
    question du porteur est posée.

    Fail-closed, comme tout le moteur : une valeur inconnue ne rend jamais
    `False`. C'est la différence entre « cette aide n'est pas pour vous » et
    « dites-nous qui vous êtes ».
    """
    marques = fact.porteurs_concernes
    if not marques:
        return True
    valeur = _resolve_fact_value(ctx, FAIT_PORTEUR, facts)
    if valeur is None:
        return None
    return evaluate_predicate({"in": list(marques)}, valeur)


def _porteur_condition(cond: Condition, fact: FactDef) -> Condition:
    """Le gate SYNTHÉTIQUE qui pose la question du porteur à la place de `cond`.

    Miroir éliminant de `_gateway_condition` : celui-là ne sert qu'à poser une
    question (« la condition s'applique-t-elle ? »), celui-ci ÉLIMINE — un
    porteur hors du marqueur ferme l'aide. La distinction porte tout
    `eliminationsParOption` : le front calcule les éliminations depuis le
    prédicat, et un gate qui n'élimine pas ne doit pas y entrer.

    Le `text` reprend celui de la condition d'origine : c'est lui que
    l'utilisateur lira dans « critères non remplis », et « réservé aux porteurs :
    société, entreprise individuelle » sans dire de quel critère il s'agit ne
    renseignerait personne.
    """
    marques = list(fact.porteurs_concernes or [])
    return Condition.model_validate(
        {
            "id": f"{cond.id}--porteur",
            "text": cond.text,
            "kind": "user_fact",
            "effect": "gate",
            "fact": FAIT_PORTEUR,
            "predicate": {"in": marques},
        }
    )


def conditions_porteur_derivees(
    aide: Aide, facts: dict[str, FactDef]
) -> list[tuple[Condition, Condition]]:
    """(condition d'origine, gate porteur dérivé) pour chaque fait marqué qu'elle gate.

    Vide si l'aide pose déjà un gate porteur EXPLICITE : celui-ci a précédence,
    et c'est mesuré — 138 aides du corpus ont un gate plus large que le marqueur
    d'un fait qu'elles gatent, dont 31 qui admettent `public_commune`. Les
    cumuler refuserait une commune que la source admet noir sur blanc.

    Partagé avec `services/catalogue_admin.construire_index` : l'écran
    « impact des réponses » de `/admin` doit voir les mêmes gates que le moteur,
    sinon il sous-déclare ce que « Commune » écarte.
    """
    if gate_porteur(aide):
        return []
    derivees: list[tuple[Condition, Condition]] = []
    for cond in aide.conditions:
        if cond.effect != "gate" or not cond.fact:
            continue
        fact = facts.get(cond.fact)
        if fact is None or not fact.porteurs_concernes:
            continue
        derivees.append((cond, _porteur_condition(cond, fact)))
    return derivees


def _evaluate_hard_filters(
    aide: Aide, monument: dict, population: int | None
) -> tuple[list[str], list[str]]:
    """Évalue les hard_filters, SANS court-circuit.

    Retourne (critères structurels satisfaits, critères éliminatoires). Tout
    critère éliminatoire rend l'aide non éligible — mais on continue d'évaluer
    les conditions pour offrir un panorama complet même sur une aide refusée.
    """
    hf = aide.hard_filters
    remplis: list[str] = []
    non_remplis: list[str] = []

    membership = [
        (
            hf.protections,
            monument.get("protection"),
            PROTECTION_LABELS,
            "Protection",
            "Protection requise",
        ),
        (
            hf.proprietaires,
            monument.get("proprietaire"),
            OWNERSHIP_LABELS,
            "Type de propriétaire",
            "Propriétaire éligible",
        ),
        (hf.regions, monument.get("region"), REGION_LABELS, "Région", "Région requise"),
        (
            hf.departements,
            monument.get("departement_num"),
            DEPARTEMENT_LABELS,
            "Département",
            "Département requis",
        ),
        (
            hf.etats_conservation,
            monument.get("etat_conservation"),
            ETAT_LABELS,
            "État de conservation",
            "État requis",
        ),
    ]
    for allowed, value, mapping, ok_prefix, ko_prefix in membership:
        if not allowed:
            continue
        if value in allowed:
            remplis.append(f"{ok_prefix} : {mapping.get(value, value)}")
        else:
            non_remplis.append(f"{ko_prefix} : {', '.join(mapping.get(v, v) for v in allowed)}")

    if hf.travaux:
        monument_travaux = monument.get("travaux_envisages") or []
        if not monument_travaux or (set(hf.travaux) & set(monument_travaux)):
            remplis.append("Types de travaux compatibles")
        else:
            non_remplis.append(
                f"Travaux éligibles : {', '.join(TRAVAUX_LABELS.get(t, t) for t in hf.travaux)}"
            )

    if hf.commune_max_population is not None and population is not None:
        if population <= hf.commune_max_population:
            remplis.append(f"Commune ≤ {hf.commune_max_population:,} hab.")
        else:
            non_remplis.append(f"Réservé aux communes ≤ {hf.commune_max_population:,} hab.")

    return remplis, non_remplis


def _condition_nature(cond: Condition) -> str:
    """Nature affichable d'une condition — pilote le regroupement côté front.

    Renvoie : auto | user_fact | manual_check | discretionary | modulateur | info.
    """
    if cond.kind == "discretionary":
        return "discretionary"
    if cond.effect == "modulateur":
        return "modulateur"
    if cond.kind == "info":
        return "info"
    return cond.kind  # auto | user_fact | manual_check (gates)


def evaluate_aide(
    aide: Aide,
    monument: dict,
    population: int | None,
    ctx: dict,
    facts: dict[str, FactDef],
) -> AideVerdict:
    """Évalue une aide : hard_filters, puis TOUTES les conditions (sans court-circuit).

    Seuls les gates et les hard_filters pilotent le statut. Chaque évaluation
    porte une `nature` pour que le front regroupe l'analyse en sections (à
    vérifier / financeur / validé / auto / infos). On évalue aussi les
    conditions des aides éliminées par un hard_filter, pour afficher le panorama
    complet (« le reste ») sous les critères éliminatoires.
    """
    verdict = AideVerdict(aide=aide, status="eligible")

    remplis, hard_fails = _evaluate_hard_filters(aide, monument, population)
    verdict.criteres_remplis = remplis
    verdict.criteres_non_remplis = list(hard_fails)
    verdict.hard_fails = list(hard_fails)
    if hard_fails:
        verdict.raison_ineligibilite = hard_fails[0]

    has_non = bool(hard_fails)
    has_incertitude = False
    has_levier = False

    # Périmètre de l'aide encore inconnu : on ne peut pas conclure, même si
    # toutes ses conditions sont satisfaites. On pose la question (fait
    # passerelle) et on maintient l'aide en incertitude.
    if aide.applies_if is not None and _evaluate_clause(aide.applies_if, ctx, facts) is None:
        perimetre_fact = facts.get(aide.applies_if.fact or "")
        has_incertitude = True
        verdict.gateway_facts.setdefault(aide.applies_if.fact or "", []).append(
            _perimetre_condition(aide, perimetre_fact)
        )
        # Le fait de périmètre a lui-même une porte, encore inconnue : sans
        # elle, l'aide n'aurait AUCUNE question — sa question de périmètre se
        # brancherait sur une porte absente du questionnaire.
        _poser_porte(verdict.gateway_facts, aide.applies_if.fact, ctx, facts)
        verdict.evaluations.append(
            {
                "critere": _perimetre_texte(perimetre_fact),
                "verdict": INCERTITUDE,
                "explication": "Cette aide ne s'adresse qu'à certains projets.",
                "detail": _perimetre_texte(perimetre_fact),
                "clarified": False,
                "nature": "user_fact",
                "categorie": aide.applies_if.fact,
            }
        )

    # Calculé UNE fois : un gate porteur explicite désarme la dérivation pour
    # toute l'aide (cf. `conditions_porteur_derivees`).
    gate_explicite = gate_porteur(aide)

    for cond in _scoped_conditions(aide, facts):
        # La porte du FAIT (`pertinent_si`) tranche avant toute clause : un fait
        # sans valeur pour ce profil n'a pas à être évalué, même quand la
        # condition porte sa propre clause — `_scoped_conditions` a alors gardé
        # celle-ci et perdu la porte. Une exclusion « pas de gîte » ne bloque
        # plus quelqu'un qui n'a aucun projet d'hébergement.
        pertinent = _pertinence(cond.fact, ctx, facts)
        if pertinent is False:
            continue  # le fait n'a pas de valeur ici → ni gate, ni affichée
        if pertinent is None and cond.effect == "gate" and cond.applies_if is not None:
            _poser_porte(verdict.gateway_facts, cond.fact, ctx, facts)

        applies = _applies(cond, ctx, facts)
        if applies is False:
            continue  # condition non applicable à ce profil → ni gate, ni affichée

        # Applicabilité indéterminée faute de connaître le fait passerelle : on
        # le pose, sinon la condition reste bloquée en incertitude pour toujours.
        if (
            applies is None
            and cond.effect == "gate"
            and cond.applies_if is not None
            and cond.applies_if.fact
        ):
            verdict.gateway_facts.setdefault(cond.applies_if.fact, []).append(
                _gateway_condition(cond)
            )

        nature = _condition_nature(cond)

        # Conditions non dirimantes : affichées pour information, sans gater.
        if cond.effect != "gate":
            if nature == "discretionary":
                explication = "Apprécié par le financeur — point de vigilance pour le dossier."
            elif nature == "modulateur":
                explication = "Peut moduler le taux ou le montant (n'affecte pas l'éligibilité)."
            elif nature == "manual_check":
                # Vraie condition, qu'on ne demande pas : soit une démarche à
                # faire avant le dépôt (audit, architecte, adhésion), soit une
                # exigence que le propriétaire ne peut pas trancher seul (avis
                # d'un comité, liste fermée de sites). Elle ne gate pas, mais
                # elle n'est pas « sans incidence » pour autant.
                explication = (
                    "À faire ou à faire confirmer par l'organisme avant le dépôt du dossier."
                )
            else:
                explication = "Information sur l'aide."
            evaluation = {
                "critere": cond.text,
                "conditionId": cond.id,
                "verdict": INFO,
                "explication": explication,
                "nature": nature,
            }
            # Démarche à accomplir : le plan d'action vient du levier du fait
            # cité, écrit une fois dans facts.yaml pour toutes les aides.
            fait_levier = facts.get(cond.levier) if cond.levier else None
            if fait_levier is not None and fait_levier.levier is not None:
                evaluation["demarche"] = _levier_plan(cond, fait_levier, None)
                evaluation["explication"] = fait_levier.levier.resume
            verdict.evaluations.append(evaluation)
            continue

        fact: FactDef | None = None
        value = None
        porteur_inconnu = False
        # Gate tranché sur la FICHE (auto_source) et non sur une réponse : son
        # refus n'est pas imputable à l'utilisateur (cf. _match_result).
        issu_fiche = False
        if cond.kind == "auto":
            result = evaluate_predicate(cond.predicate.root, ctx.get(cond.field))
            cat = None
        elif cond.kind == "user_fact":
            fact = facts.get(cond.fact or "")
            # Le marqueur `porteurs_concernes` du fait gaté, rendu exécutable :
            # une commune ne s'entend plus demander son effectif salarié, et
            # l'aide qui l'exige lui est fermée sans qu'elle ait à répondre.
            # Placé AVANT les branches `derogation_possible` et `levier` : un
            # porteur hors du marqueur n'est pas un critère qu'on peut lever,
            # c'est le mauvais destinataire.
            admis = (
                _porteur_admis(fact, ctx, facts)
                if fact is not None and cond.effect == "gate" and not gate_explicite
                else True
            )
            if admis is False:
                has_non = True
                marques = ", ".join(fact.porteurs_concernes or []) if fact else ""
                verdict.criteres_non_remplis.append(cond.text)
                verdict.raison_ineligibilite = verdict.raison_ineligibilite or cond.text
                verdict.evaluations.append(
                    {
                        "critere": cond.text,
                        "conditionId": cond.id,
                        "verdict": NON,
                        "explication": f"Réservé aux porteurs : {marques}.",
                        "nature": nature,
                    }
                )
                continue
            if admis is None:
                # Le porteur est inconnu : on POSE sa question (éliminante,
                # donc `eliminationsParOption` exact par construction) et on
                # laisse la condition en incertitude sans demander son fait.
                assert fact is not None
                verdict.missing_facts.setdefault(FAIT_PORTEUR, []).append(
                    _porteur_condition(cond, fact)
                )
            porteur_inconnu = admis is None
            value = _resolve_fact_value(ctx, cond.fact, facts)
            issu_fiche = value is not None and _answered_value(ctx, cond.fact, facts) is None
            result = evaluate_predicate(cond.predicate.root, value)
            cat = cond.fact
        else:  # manual_check (ou untyped résiduel) : non évaluable → incertitude
            result = None
            cat = None

        # Le FAIT tranche-t-il, indépendamment de l'applicabilité ? Un fait déjà
        # connu (réponse ou fiche) ne se redemande pas : l'inconnue restante est
        # alors le fait passerelle — ou le PORTEUR —, posé de son côté.
        fait_tranche = result is not None

        # applies_if indéterminé : la condition s'applique peut-être (fail-closed)
        # → si on n'a pas pu trancher le gate, on reste en incertitude. Même
        # geste pour un porteur inconnu : tant qu'on ignore si l'aide s'adresse
        # à lui, un critère satisfait ne la rend pas éligible.
        if (applies is None or porteur_inconnu) and result is True:
            result = None

        if result is True:
            verdict.evaluations.append(
                {
                    "critere": cond.text,
                    "conditionId": cond.id,
                    "verdict": OUI,
                    "explication": "Critère satisfait.",
                    "nature": nature,
                }
            )
        elif result is False and cond.derogation_possible:
            # Gate souple : l'échec n'est pas dirimant (échappatoire « dérogation »).
            # On dégrade en incertitude SANS categorie → pas de re-question (le fait
            # est déjà répondu), mais l'aide reste potentielle, à vérifier.
            has_incertitude = True
            verdict.evaluations.append(
                {
                    "critere": cond.text,
                    "conditionId": cond.id,
                    "verdict": INCERTITUDE,
                    "explication": "Non satisfait, mais une dérogation est possible — "
                    "à vérifier auprès du financeur.",
                    "detail": cond.text,
                    "clarified": False,
                    "nature": nature,
                }
            )
        elif result is False and fact is not None and fact.levier is not None:
            # Gate en échec sur un fait ACTIONNABLE : l'aide n'est pas perdue,
            # elle est à débloquer. On n'alimente ni criteres_non_remplis ni
            # raison_ineligibilite — le front l'afficherait en rouge, alors que
            # c'est une opportunité assortie d'une démarche.
            has_levier = True
            plan = _levier_plan(cond, fact, value)
            verdict.leviers.append(plan)
            verdict.evaluations.append(
                {
                    "critere": cond.text,
                    "conditionId": cond.id,
                    "verdict": NON,
                    "explication": plan["resume"],
                    "nature": nature,
                    "levier": True,
                }
            )
        elif result is False:
            has_non = True
            verdict.criteres_non_remplis.append(cond.text)
            verdict.raison_ineligibilite = verdict.raison_ineligibilite or cond.text
            verdict.evaluations.append(
                {
                    "critere": cond.text,
                    "conditionId": cond.id,
                    "verdict": NON,
                    "explication": "Critère non satisfait.",
                    "nature": nature,
                    **({"fiche": True} if issu_fiche else {}),
                }
            )
        else:  # None → incertitude
            has_incertitude = True
            ev = {
                "critere": cond.text,
                "conditionId": cond.id,
                "verdict": INCERTITUDE,
                "explication": (
                    "À vérifier auprès du financeur."
                    if cond.kind == "manual_check"
                    else "Information manquante."
                ),
                "detail": cond.text,
                "clarified": False,
                "nature": nature,
            }
            if cat and not fait_tranche:
                ev["categorie"] = cat
                verdict.missing_facts.setdefault(cat, []).append(cond)
            verdict.evaluations.append(ev)

    # Précédence : un refus ferme (hard_filter ou gate sans levier) l'emporte sur
    # tout. Sinon un échec « à débloquer » prime sur l'incertitude : c'est
    # l'information la plus actionnable, et le QCM continue d'alimenter l'aide.
    if has_non:
        verdict.status = "non_eligible"
    elif has_levier:
        verdict.status = "atteignable"
    elif has_incertitude:
        verdict.status = "potentiel"
    else:
        verdict.status = "eligible"
    return verdict


# ---------------------------------------------------------------------------
# Génération des questions (déterministe)
# ---------------------------------------------------------------------------


def _normalize_boundary(op: str, val: float, is_integer: bool) -> float | None:
    """Convertit un (opérateur, valeur de seuil) en une BORNE `b` telle que la
    bande basse `{x < b}` et la bande haute `{x >= b}` aient chacune une valeur
    de vérité CONSTANTE pour ce prédicat — le point de bascule tombe pile sur la
    frontière de tranche, jamais à l'intérieur.

    C'est nécessaire pour les seuils STRICTS : `gt: 0` bascule entre 0 (faux) et
    1 (vrai), donc sa frontière utile est 1, pas 0. Sans ce décalage, la tranche
    haute « 0 ou plus » a pour représentant 0, qui échoue `gt: 0` → l'aide
    devenait inatteignable et le label « Moins de 0 » était absurde.

    Sur les entiers : `gt: n` → `n+1`, `lte: n` → `n+1`. `gte`/`lt`/`eq` gardent
    `n` (déjà sur la frontière). Sur les flottants on ne décale pas (pas de seuil
    strict dans le corpus, et un epsilon polluerait les libellés).
    """
    step = 1 if is_integer else 0
    if op == "gt":
        return val + step  # x > n  ⇔  x >= n+1  (entiers)
    if op == "lte":
        return val + step  # x <= n ⇔  x <  n+1  (entiers)
    return val  # gte, lt, eq, neq… : la valeur est déjà la frontière


def _unite_singulier(unit: str) -> str:
    """Forme singulière d'une unité : « 1 jour », pas « 1 jours ».

    En français le pluriel du nom compté se marque par un -s final ; `mois` est
    invariable, et une unité composée ne s'accorde que sur son premier segment
    (« jours/an » → « jour/an »).
    """
    tete, _, queue = unit.partition("/")
    if tete != "mois" and tete.endswith("s"):
        tete = tete[:-1]
    return f"{tete}/{queue}" if queue else tete


def _fmt_borne(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else str(v)


def _suffixe_unite(v: float, unit: str | None) -> str:
    """Unité accordée au nombre qui la précède."""
    if not unit:
        return ""
    if unit == "€":
        return unit
    return f" {_unite_singulier(unit) if abs(v) == 1 else unit}"


# Les trois formes de libellé d'une tranche, définies UNE FOIS : elles servent à
# fabriquer les options (`_numeric_tranches`) et à les relire depuis leur seul
# identifiant (`libelle_tranche`). Deux définitions dériveraient, et un libellé
# relu qui ne dirait pas la même chose que celui qu'on a montré à l'utilisateur
# serait pire que pas de libellé du tout.
def _libelle_basse(borne: float, unit: str | None) -> str:
    # Seuil à 1 sur un compteur : la bande ne contient que 0. « Moins de 1 jour »
    # se lit comme un arrondi ; « Aucun (0) » dit ce qu'elle est.
    if borne == 1:
        return "Aucun (0)"
    return f"Moins de {_fmt_borne(borne)}{_suffixe_unite(borne, unit)}"


def _libelle_intermediaire(lo: float, hi: float, unit: str | None) -> str:
    # L'unité s'accorde sur la borne HAUTE, celle qu'elle suit dans le libellé.
    return f"De {_fmt_borne(lo)} à {_fmt_borne(hi)}{_suffixe_unite(hi, unit)}"


def _libelle_haute(borne: float, unit: str | None) -> str:
    return f"{_fmt_borne(borne)}{_suffixe_unite(borne, unit)} ou plus"


# Identifiants produits par `_numeric_tranches` : `lt<borne>`, `<lo>_<hi>`,
# `ge<borne>`. Les bornes peuvent être décimales (`fmt` rend `2.5` tel quel).
_NOMBRE = r"\d+(?:\.\d+)?"
_TRANCHE_BASSE = re.compile(rf"^lt({_NOMBRE})$")
_TRANCHE_INTERMEDIAIRE = re.compile(rf"^({_NOMBRE})_({_NOMBRE})$")
_TRANCHE_HAUTE = re.compile(rf"^ge({_NOMBRE})$")


def libelle_tranche(option_id: str, unit: str | None) -> str | None:
    """Relit le libellé d'une tranche depuis son seul IDENTIFIANT.

    Utile là où les options ne sont pas reconstructibles : une réponse persistée
    dans `projets.questionnaire` vaut `ge5`, et les tranches sont fabriquées
    depuis les seuils des aides CANDIDATES — hors diagnostic, on ne les a pas.

    Mais l'identifiant porte ses propres bornes (`lt5`, `5_9`, `ge5`) : le
    libellé se reconstruit donc à l'identique, sans rien supposer du catalogue.
    C'est ce qui permet de montrer « 5 ans ou plus » plutôt qu'un laconique
    « réponse déjà donnée » quand on rappelle à l'utilisateur ce qu'il a répondu.

    Rend None sur un identifiant d'une autre forme (réponse d'avant les
    tranches, valeur écrite à la main) : on n'invente pas de libellé.
    """
    if m := _TRANCHE_BASSE.match(option_id):
        return _libelle_basse(float(m.group(1)), unit)
    if m := _TRANCHE_INTERMEDIAIRE.match(option_id):
        return _libelle_intermediaire(float(m.group(1)), float(m.group(2)), unit)
    if m := _TRANCHE_HAUTE.match(option_id):
        return _libelle_haute(float(m.group(1)), unit)
    return None


def _numeric_tranches(boundaries: list[float], unit: str | None) -> list[dict]:
    """Construit des options MECE à partir de bornes triées (cf.
    `_normalize_boundary`). Chaque option porte un `repr` (valeur représentative
    de la tranche), strictement intérieur à la bande, donc évaluer un prédicat de
    seuil au représentant est exact.
    """
    ts = sorted(set(boundaries))
    fmt = _fmt_borne

    options = []
    # Tranche basse : strictement sous la plus petite borne. Omise si elle ne
    # contient aucune valeur atteignable (borne basse <= 0 pour un compteur).
    if ts[0] - 1 >= 0:
        options.append(
            {"id": f"lt{fmt(ts[0])}", "label": _libelle_basse(ts[0], unit), "repr": ts[0] - 1}
        )
    # Tranches intermédiaires.
    for lo, hi in zip(ts, ts[1:], strict=False):
        options.append(
            {
                "id": f"{fmt(lo)}_{fmt(hi)}",
                "label": _libelle_intermediaire(lo, hi, unit),
                "repr": lo,
            }
        )
    # Tranche haute : au-dessus de la plus grande borne (incluse).
    options.append(
        {
            "id": f"ge{fmt(ts[-1])}",
            "label": _libelle_haute(ts[-1], unit),
            "repr": ts[-1],
        }
    )
    return options


def _options_for_fact(fact: FactDef, gate_conds: list[Condition]) -> list[dict]:
    """Options d'une question, selon le type du fait. Chaque option a `value`
    (à injecter pour calculer l'élimination) ou `repr` (numérique)."""
    if fact.type == "boolean":
        # Un booléen peut déclarer plus de deux réponses, chacune disant la
        # valeur qu'elle envoie aux prédicats (cf. FactOption.valeur). Sans
        # déclaration, le couple implicite — même liste que `_normalize_answer`.
        return [
            {"id": o.id, "label": o.label, "value": o.valeur, "unknown": o.unknown}
            for o in fact.options or OPTIONS_BOOLEEN_IMPLICITES
        ]
    if fact.type in ENUM_FACT_TYPES:
        return [
            {"id": o.id, "label": o.label, "value": o.id, "unknown": o.unknown}
            for o in fact.options or []
        ]
    # integer / number : tranches à partir des seuils des prédicats des gates.
    # On normalise selon l'OPÉRATEUR (cf. _normalize_boundary) pour gérer les
    # seuils stricts ; sans ça `gt: 0` produisait « Moins de 0 / 0 ou plus ».
    is_integer = fact.type == "integer"
    boundaries = []
    for c in gate_conds:
        for op, val in c.predicate.root.items():
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                boundaries.append(_normalize_boundary(op, val, is_integer))
    if not boundaries:
        return []
    return _numeric_tranches(boundaries, fact.unit)


def _depends_on(
    fact_conds: list[Condition],
    built: dict[str, dict],
    options_by_fact: dict[str, list[dict]],
) -> dict | None:
    """Branchement conditionnel d'une question sur une autre.

    Si TOUTES les conditions candidates d'un fait ne s'appliquent que sous la
    même clause `applies_if.fact = G`, la question n'a de sens que pour les
    réponses à G qui rendent au moins une de ces conditions applicable : le
    front saute la question sinon. Une seule condition sans `applies_if` (ou
    portant sur un autre fait passerelle) suffit à annuler le branchement —
    fail-closed : dans le doute, on pose la question.
    """
    gateways = {c.applies_if.fact for c in fact_conds if c.applies_if and c.applies_if.fact}
    if len(gateways) != 1 or any(c.applies_if is None or not c.applies_if.fact for c in fact_conds):
        return None
    gateway = gateways.pop()
    if gateway not in built:
        return None  # G n'est pas posé : rien à quoi se brancher

    show_for = []
    for opt in options_by_fact[gateway]:
        # Option « je ne sais pas » : le fait reste inconnu, donc la condition
        # peut s'appliquer — on garde la question (fail-closed).
        applicable = opt.get("unknown") or any(
            evaluate_predicate(c.applies_if.predicate.root, opt.get("value", opt.get("repr")))
            is not False
            for c in fact_conds
            if c.applies_if
        )
        if applicable:
            show_for.append(opt["id"])
    if not show_for or len(show_for) == len(options_by_fact[gateway]):
        return None  # jamais applicable, ou toujours : pas de branchement utile
    return {"questionId": gateway, "showForOptionIds": show_for}


def _depends_on_pertinence(
    fact: FactDef,
    built: dict[str, dict],
    options_by_fact: dict[str, list[dict]],
) -> dict | None:
    """Branchement d'une question sur la PORTE de son fait (`pertinent_si`).

    C'est l'AUTORITÉ du branchement, avant toute inférence : la clause est
    déclarée sur le FAIT, donc vraie de toutes les aides à la fois, là où
    `_depends_on` doit la remonter des conditions et renonce (fail-closed) dès
    qu'une seule ne la porte pas. Sur `type_hebergement_touristique`, cinq aides
    sur treize suffisaient à casser l'inférence : trois l'utilisent comme
    périmètre d'AIDE (le gate synthétique n'a pas d'`applies_if`), deux ont une
    clause PROPRE que `_scoped_conditions` garde à la place de la porte.

    Porte non posée : rien à quoi se brancher, la question reste (fail-closed).
    """
    clause = fact.pertinent_si
    if clause is None or not clause.fact or clause.fact not in built:
        return None
    show_for = [
        opt["id"]
        for opt in options_by_fact[clause.fact]
        # Option « je ne sais pas » : la porte reste inconnue, le fait est donc
        # peut-être pertinent — on garde la question (fail-closed).
        if opt.get("unknown")
        or evaluate_predicate(clause.predicate.root, opt.get("value", opt.get("repr"))) is not False
    ]
    if not show_for or len(show_for) == len(options_by_fact[clause.fact]):
        return None  # jamais pertinent, ou toujours : pas de branchement utile
    return {"questionId": clause.fact, "showForOptionIds": show_for}


def _depends_on_deduction(
    fact_key: str,
    built: dict[str, dict],
    options_by_fact: dict[str, list[dict]],
) -> dict | None:
    """Branchement d'une question DÉDUITE sur sa source (FAITS_DEDUITS_DES_FAITS).

    La question n'a de sens que pour les réponses à la source qui ne déduisent
    rien ; pour les autres, le serveur connaît déjà la valeur. L'option « je ne
    sais pas » garde la question (fail-closed). Source non posée : rien à quoi
    se brancher, la question reste.
    """
    deduction = FAITS_DEDUITS_DES_FAITS.get(fact_key)
    if deduction is None:
        return None
    source_key, table = deduction
    if source_key not in built:
        return None
    show_for = [
        opt["id"]
        for opt in options_by_fact[source_key]
        if opt.get("unknown")
        or not any(_meme_valeur(opt.get("value", opt.get("repr")), v) for v in table)
    ]
    if not show_for or len(show_for) == len(options_by_fact[source_key]):
        return None
    return {"questionId": source_key, "showForOptionIds": show_for}


def _pourquoi_servi(
    fact: FactDef, options: list[dict], eliminations: dict[str, list[str]]
) -> dict[str, str] | None:
    """Les textes `pourquoi` du fait que le front peut avoir à afficher.

    Rien quand aucune réponse n'écarte d'aide dans ce diagnostic : l'encart ne
    s'ouvrirait jamais. Sinon, les clés des réponses encore offertes, plus le
    repli `"*"` : une réponse retirée depuis /admin laisse sa clé orpheline
    dans le YAML, et le front n'a pas à la recevoir. La décision d'afficher
    reste au front, qui connaît les aides déjà écartées par les autres réponses.
    """
    if not fact.pourquoi or not eliminations:
        return None
    offertes = {o["id"] for o in options}
    servi = {cle: texte for cle, texte in fact.pourquoi.items() if cle == "*" or cle in offertes}
    return servi or None


def build_questions(
    verdicts: list[AideVerdict],
    facts: dict[str, FactDef],
) -> list[dict]:
    """Construit les QcmQuestion (contrat front) depuis les faits manquants.

    Deux sources : les gates en incertitude (`missing_facts`, qui pilotent les
    éliminations) et les faits PASSERELLES (`gateway_facts`, qui débloquent
    l'applicabilité d'une condition sans jamais éliminer personne).

    eliminationsParOption[option] = aides que cette option REFUSE vraiment, au
    sens du statut `non_eligible` — calculé en évaluant le prédicat à la valeur
    de l'option. Exact, pas de réparation de monotonie. Un gate en échec qui
    n'est pas dirimant (fait porteur d'un `levier`, condition à
    `derogation_possible`) n'y entre donc pas : l'aide reste vivante, et le
    front doit continuer de poser ses autres questions.

    Sur une question à choix multiple (`multiple: true`), chaque entrée vaut
    « si c'était la seule case cochée » : cocher une case de plus ne peut que
    LIBÉRER des aides (sémantique existentielle, cf. MultiValue), d'où
    l'intersection côté front. Seule exception, les exclusions strictes
    (`none_in`) : cocher une case de plus peut écarter une aide, et
    `eliminationsStrictesParOption` les porte à part pour que le front en
    fasse l'union. Le verdict qui compte reste celui du moteur, réévalué avec
    les réponses complètes.
    """
    # fact_key → {aide_slug → [conditions gate sur ce fait]}
    by_fact: dict[str, dict[str, list[Condition]]] = {}
    gateway_by_fact: dict[str, dict[str, list[Condition]]] = {}
    montant_by_slug: dict[str, float] = {}
    # (slug, fait) → rang de la PREMIÈRE condition de l'aide portant ce fait.
    rang_source: dict[tuple[str, str], int] = {}
    for v in verdicts:
        if v.status not in ("potentiel", "atteignable"):
            continue
        montant_by_slug[v.aide.slug] = v.aide.financement.montant_max or 0
        for fact_key, conds in v.missing_facts.items():
            by_fact.setdefault(fact_key, {})[v.aide.slug] = conds
        for fact_key, conds in v.gateway_facts.items():
            gateway_by_fact.setdefault(fact_key, {})[v.aide.slug] = conds
        for rang, cond in enumerate(v.aide.conditions):
            if cond.fact:
                rang_source.setdefault((v.aide.slug, cond.fact), rang)

    def aide_slugs(fact_key: str) -> list[str]:
        return sorted(set(by_fact.get(fact_key, {})) | set(gateway_by_fact.get(fact_key, {})))

    def ordre_source(fact_key: str) -> tuple[str, int]:
        """Départage à nombre d'aides égal : les questions d'une même aide se
        suivent, dans l'ordre où le règlement énonce ses conditions.

        Le YAML suit le texte officiel : « possède un orgue » y précède « âge de
        l'orgue », et l'objet d'une aide ses exclusions. Un départage
        alphabétique sur la clé du fait les mélangeait (`age_orgue_ans` avant
        `possede_orgue_a_tuyaux`) et dispersait une aide sur tout le
        questionnaire. Un fait sans condition dans l'aide (gate synthétique de
        périmètre) passe en dernier."""
        slugs = aide_slugs(fact_key)
        premier = slugs[0] if slugs else ""
        return (premier, rang_source.get((premier, fact_key), 10**6))

    candidats = set(by_fact) | set(gateway_by_fact)
    # Un fait dont une réponse en déduit un autre (FAITS_DEDUITS_DES_FAITS) se
    # pose avant lui, comme une passerelle : c'est ce qui permet au front de
    # sauter la question déduite.
    sources_deduction = {
        source for cible, (source, _) in FAITS_DEDUITS_DES_FAITS.items() if cible in candidats
    }
    # Même geste pour la PORTE d'un fait (`pertinent_si`) : elle se pose avant
    # lui, sinon `_depends_on_pertinence` n'a rien à quoi se brancher et la
    # question part à tout le monde. Une porte sert parfois MOINS d'aides que
    # sa dépendante (« avez-vous un projet d'hébergement ? » face aux treize
    # aides qui en demandent le type) : le classement par nombre d'aides,
    # seul, l'aurait mise après.
    portes: set[str] = set()
    for cible in candidats:
        porte = (facts.get(cible) or _SANS_FAIT).pertinent_si
        if porte is not None and porte.fact:
            portes.add(porte.fact)
    # Le fait PORTEUR entre au premier étage dès qu'une aide l'attend par
    # dérivation (`_porteur_condition`) : tant qu'on ignore qui dépose, les
    # questions d'entreprise de ces aides n'ont pas à être posées, et y répondre
    # ne servirait à rien si le porteur les écarte toutes ensuite. Les gates
    # dérivés sont reconnaissables à leur id suffixé — on ne se fie pas à la
    # seule présence du fait, qu'une aide peut gater explicitement.
    porteur_derive = any(
        cond.id.endswith("--porteur")
        for conds in by_fact.get(FAIT_PORTEUR, {}).values()
        for cond in conds
    )
    # Tri : les faits PASSERELLES d'abord (une question dont dépend une autre se
    # pose avant elle), puis ceux qui débloquent le plus d'aides, puis l'ordre de
    # la source. Le graphe d'applicabilité n'a qu'un niveau dans le corpus : pas
    # de tri topologique.
    ordered = sorted(
        candidats,
        key=lambda k: (
            not (porteur_derive and k == FAIT_PORTEUR),
            k not in gateway_by_fact and k not in sources_deduction and k not in portes,
            -len(aide_slugs(k)),
            *ordre_source(k),
            k,
        ),
    )

    questions: list[dict] = []
    built: dict[str, dict] = {}
    options_by_fact: dict[str, list[dict]] = {}
    for fact_key in ordered:
        fact = facts.get(fact_key)
        if fact is None:
            continue
        aides_conds = by_fact.get(fact_key, {})
        gateway_conds = gateway_by_fact.get(fact_key, {})
        all_conds = [c for conds in aides_conds.values() for c in conds] + [
            c for conds in gateway_conds.values() for c in conds
        ]
        options = _options_for_fact(fact, all_conds)
        if not options:
            continue

        elim: dict[str, list[str]] = {}
        elim_strictes: dict[str, list[str]] = {}
        # Un fait porteur d'un levier n'élimine JAMAIS : son gate en échec rend
        # l'aide « à débloquer » (cf. evaluate_aide), pas refusée.
        fait_dirimant = fact.levier is None
        for opt in options:
            if opt.get("unknown"):
                continue  # option « pas encore choisi » : n'élimine jamais
            test_value = opt.get("value", opt.get("repr"))
            eliminated = []
            strictes = []
            for slug, conds in aides_conds.items():
                # Exclusion stricte (`none_in`) : cette case écarte l'aide quelles
                # que soient les autres cases cochées. Elle entre AUSSI dans
                # `elim` ci-dessous, qui reste exact pour qui ne coche qu'elle
                # (et pour un onglet dont le front ignore encore la table
                # stricte : il sous-élimine, il n'élimine jamais à tort).
                if fait_dirimant and any(
                    next(iter(c.predicate.root)) in BLOCK_OPS
                    and evaluate_predicate(c.predicate.root, test_value) is False
                    and not c.derogation_possible
                    for c in conds
                ):
                    strictes.append(slug)
                # L'aide est éliminée si AU MOINS un de ses gates DIRIMANTS sur
                # ce fait devient faux à cette valeur. Les gates synthétiques des
                # faits passerelles sont exclus : ils libèrent, ils n'éliminent
                # pas. Un gate à `derogation_possible` ne l'est pas davantage :
                # son échec dégrade en incertitude, l'aide reste potentielle.
                #
                # Annoncer ici une élimination que le moteur n'applique pas
                # coûte cher : le front élague le questionnaire sur cette liste
                # (`isQuestionServingLiveAide`), et l'aide, toujours vivante,
                # revient avec des critères jamais posés.
                if fait_dirimant and any(
                    evaluate_predicate(c.predicate.root, test_value) is False
                    and not c.derogation_possible
                    for c in conds
                ):
                    eliminated.append(slug)
            if eliminated:
                elim[opt["id"]] = sorted(eliminated)
            if strictes:
                elim_strictes[opt["id"]] = sorted(strictes)

        slugs = aide_slugs(fact_key)
        multiple = fact.type == "multi_enum"
        # `unknown` est remonté au front : ces options portent un « ? » plutôt
        # qu'une pastille lettrée, ne comptent pour aucune élimination, et sont
        # exclusives des autres en choix multiple.
        # Quand le fait DÉCLARE ses options, `unknown` part explicitement — y
        # compris `false` : le front n'a alors plus à deviner au libellé quelle
        # réponse est une échappatoire (cf. unknownAnswer.ts), et une réponse de
        # plein droit nommée « Je ne sais pas trop » garde sa pastille lettrée.
        # Les options FABRIQUÉES par le moteur (tranches numériques, couple
        # booléen implicite) gardent l'ancien contrat : rien à déclarer.
        declare = bool(fact.options)
        shown_options = [
            {
                "id": o["id"],
                "label": o["label"],
                **(
                    {"unknown": bool(o.get("unknown"))}
                    if declare
                    else ({"unknown": True} if o.get("unknown") else {})
                ),
            }
            for o in options
        ]
        # Le pseudo-choix « passer » n'a pas de sens en choix multiple : ne rien
        # cocher passe déjà la question.
        if not multiple:
            shown_options.append({"id": "skip", "label": "Passer cette question"})
        question = {
            "id": fact_key,
            "question": fact.question,
            "help": fact.help,
            "multiple": multiple,
            "options": shown_options,
            "aideIds": slugs,
            # Enjeu de la question : le total des montants max en jeu derrière
            # elle. 0 quand aucune des aides n'est chiffrée — le front n'affiche
            # alors que leur nombre plutôt qu'un « jusqu'à 0 € » absurde.
            "enjeuMax": sum(montant_by_slug.get(s, 0) for s in slugs),
            "eliminatingOptionIds": [],
            "eliminationsParOption": elim,
            # Choix multiple seulement, et seulement s'il y a lieu : les aides
            # qu'une case écarte À ELLE SEULE (exclusion stricte, `none_in`).
            # Le front en fait l'UNION sur la sélection, là où il intersecte
            # `eliminationsParOption`.
            **({"eliminationsStrictesParOption": elim_strictes} if elim_strictes else {}),
            "categorie": fact_key,
            # Où la réponse vaut : le bien, le projet, ou le propriétaire. Sert
            # aux faits DURABLES — une réponse de scope `monument` ou
            # `proprietaire` se reprend d'un projet à l'autre du même bien
            # (cf. services/faits_durables.py).
            "scope": fact.scope,
        }
        pourquoi = _pourquoi_servi(fact, options, elim or elim_strictes)
        if pourquoi:
            question["pourquoiEcarte"] = pourquoi
        depends_on = (
            _depends_on_pertinence(fact, built, options_by_fact)
            or _depends_on(all_conds, built, options_by_fact)
            or _depends_on_deduction(fact_key, built, options_by_fact)
        )
        if depends_on:
            question["dependsOn"] = depends_on
        options_by_fact[fact_key] = options
        built[fact_key] = question
        questions.append(question)
    return questions


# ---------------------------------------------------------------------------
# Forme aide pour le frontend (snake_case → _to_camel côté routeur)
# ---------------------------------------------------------------------------


def aide_display_dict(aide: Aide) -> dict:
    """Projette une Aide YAML sur la forme d'une ligne aides_v3 (snake_case).

    `id` = slug : on ne lit pas la base, donc pas d'UUID. Le front traite les
    aideIds comme des chaînes opaques — cohérent avec eliminationsParOption.
    """
    bullets = "\n".join(f"- {c.text}" for c in aide.conditions)
    f = aide.financement
    return {
        "id": aide.slug,
        "nom": aide.nom,
        "nom_court": aide.nom_court,
        "description": aide.description,
        "description_longue": aide.description_longue,
        "organisme": aide.organisme,
        "categorie": aide.categorie,
        "type": aide.type,
        # Finalités de l'aide — sert au préfiltre « Votre projet » et au debug.
        "raison": aide.raison,
        # Familles thématiques — servent au préfiltre « Votre projet » et aux
        # facettes du mode découverte. Comme `raison`, la clé passe en
        # snake_case (hors _AIDE_KEY_MAP) et n'est pas caviardée par
        # `retirer_les_modalites` : une famille n'est pas une modalité.
        "familles": aide.familles,
        "montant_max": f.montant_max,
        "montant_min": f.montant_min,
        "taux_max": f.taux_max,
        "taux_min": f.taux_min,
        "plancher": f.plancher,
        "base_ttc": f.base_ttc,
        "commune_max_population": aide.hard_filters.commune_max_population,
        "cofinancement_requis": aide.flags.cofinancement_requis,
        "architecte_requis": aide.flags.architecte_requis,
        "conditions_eligibilite_detail": bullets or None,
        "demarche_description": aide.demarche,
        "documents_requis": [d.model_dump() for d in aide.documents_requis],
        "delai_instruction": aide.calendrier.delai_instruction,
        "date_ouverture": aide.calendrier.date_ouverture.isoformat()
        if aide.calendrier.date_ouverture
        else None,
        "date_limite": aide.calendrier.date_limite.isoformat()
        if aide.calendrier.date_limite
        else None,
        "permanent": aide.calendrier.permanent,
        "url_officielle": aide.source.url_officielle,
        "formulaire_url": aide.source.formulaire_url,
        "tags": aide.tags,
        "carte": _carte_editoriale(aide.fiche),
    }


def _carte_editoriale(fiche: Fiche | None) -> dict | None:
    """Ce que la carte d'une aide emprunte à sa fiche rédigée.

    Quatre champs courts, et rien de plus : ce dict part avec chaque aide du
    diagnostic, une centaine par projet. Le reste de la fiche ne sert qu'à sa
    page et passe par `GET /aides/{id}` (cf. `aide_fiche_dict`).
    """
    if fiche is None:
        return None
    carte = {
        "titre": fiche.titre,
        "financeur": fiche.financeur,
        "chapeau": fiche.chapeau,
        "montant": fiche.montant.model_dump() if fiche.montant else None,
    }
    return carte if any(carte.values()) else None


def aide_fiche_dict(aide: Aide) -> dict:
    """La forme d'affichage, plus ce que seule la page de l'aide consomme.

    `reglement` porte les conditions telles que le règlement les énonce (texte,
    citation, nature) pour la rubrique « Le règlement complet » : les
    évaluations du diagnostic n'en disent que le verdict, et pas pour les
    conditions écartées d'un profil par `applies_if`. `fiche` est la rédaction
    en langue claire, en camelCase comme le reste de la réponse.
    """
    d = aide_display_dict(aide)
    d["verifie_le"] = aide.source.verified_at.isoformat() if aide.source.verified_at else None
    d["reglement"] = [
        {
            "id": c.id,
            "text": c.text,
            "quote": c.quote,
            "kind": c.kind,
            "effect": c.effect,
            "derogationPossible": c.derogation_possible,
        }
        for c in aide.conditions
    ]
    f = aide.fiche
    if f is None:
        d["fiche"] = None
        return d
    d["fiche"] = {
        "redigeLe": f.redige_le.isoformat() if f.redige_le else None,
        "titre": f.titre,
        "financeur": f.financeur,
        "chapeau": f.chapeau,
        "montant": f.montant.model_dump() if f.montant else None,
        "essentiel": f.essentiel.model_dump(exclude_none=True),
        "enBref": f.en_bref.model_dump() if f.en_bref else None,
        "conseils": [c.model_dump() for c in f.conseils],
        "etapes": [e.model_dump() for e in f.etapes],
        "points": {k: p.model_dump() for k, p in f.points.items()},
        "pieces": dict(f.pieces),
    }
    return d


# Rôles de financement qui allègent réellement la facture de chantier. Le taux
# cumulé n'agrège que ceux-là : une déduction fiscale (Denormandie, Malraux…)
# porte sur l'impôt et non sur le coût des travaux, un prêt se rembourse, un
# label n'apporte pas d'argent. Rôle dérivé du `type` via ROLE_BY_TYPE.
ROLES_SUBVENTIONNANTS = frozenset({"subvention", "mecenat"})

# Plafond d'aides publiques cumulées : le maître d'ouvrage garde au moins 20 %
# du coût à sa charge, règle que reprennent les dispositifs les uns après les
# autres. Aucun cumul affiché ne peut donc dépasser 80 % des travaux.
PLAFOND_TAUX_TRAVAUX_PCT = 80.0


def taux_travaux_cumule(verdicts: list[AideVerdict]) -> float | None:
    """Part maximale du coût des travaux couverte par les aides retenues, en %.

    Somme des `taux_max` des aides qui subventionnent les travaux, écrêtée à
    PLAFOND_TAUX_TRAVAUX_PCT. Retourne None si aucune aide n'est chiffrée en
    taux — la case n'affiche alors que le montant.
    """
    taux = 0.0
    for v in verdicts:
        if ROLE_BY_TYPE.get(v.aide.type) not in ROLES_SUBVENTIONNANTS:
            continue
        if v.aide.financement.taux_max is None:
            continue
        taux += v.aide.financement.taux_max
    if taux <= 0:
        return None
    return round(min(taux, PLAFOND_TAUX_TRAVAUX_PCT), 1)


def _match_result(verdict: AideVerdict, today: date | None = None) -> dict:
    """Forme AideMatchResult attendue par le front."""
    incertitudes = [e for e in verdict.evaluations if e["verdict"] == INCERTITUDE]
    n_non = sum(1 for e in verdict.evaluations if e["verdict"] == NON)
    n_leviers = len(verdict.leviers)
    if verdict.status == "eligible":
        explication = "Tous les critères vérifiables sont satisfaits."
    elif verdict.status == "atteignable":
        explication = f"{n_leviers} démarche(s) à engager pour débloquer cette aide."
    elif verdict.status == "potentiel":
        explication = f"{len(incertitudes)} information(s) à confirmer."
    else:
        explication = verdict.raison_ineligibilite or f"{n_non} critère(s) non satisfait(s)."
    # Un gate `user_fact` n'échoue sur une RÉPONSE que si sa valeur en vient :
    # _resolve_fact_value se rabat sinon sur la fiche (`auto_source`), d'où le
    # marqueur `fiche`. Les autres refus (hard_filters, gates `auto`) se
    # déduisent eux aussi de la fiche, sans que personne n'ait rien répondu.
    # Les échecs porteurs d'un `levier` sont exclus : ils ne rendent pas l'aide
    # non éligible (statut « atteignable »), ils la mettent à débloquer.
    #
    # Le refus automatique l'emporte : une aide hors région ET refusée sur une
    # réponse n'est pas « écartée par vos réponses », elle n'a jamais été
    # candidate — c'est d'ailleurs le hard_filter que `raison_ineligibilite`
    # affiche. Tout ce qui n'est pas explicitement `user_fact` compte comme
    # automatique (fail-closed : dans le doute, on n'impute rien à l'utilisateur).
    refus_automatique = bool(verdict.hard_fails) or any(
        e["verdict"] == NON
        and (e.get("nature") != "user_fact" or e.get("fiche"))
        and not e.get("levier")
        for e in verdict.evaluations
    )
    elimine_par_reponse = (
        verdict.status == "non_eligible"
        and not refus_automatique
        and any(
            e["verdict"] == NON and e.get("nature") == "user_fact" and not e.get("levier")
            for e in verdict.evaluations
        )
    )
    return {
        "aide": aide_display_dict(verdict.aide),
        # Statut explicite : le front l'utilise tel quel plutôt que de le
        # re-dériver de `eligible` + incertitudes (dérivation conservée en
        # repli pour l'ancien chemin LLM, qui ne renseigne pas ce champ).
        "statut": verdict.status,
        # Fenêtre de candidature, orthogonale au statut : une aide peut être
        # pleinement éligible mais pas déposable aujourd'hui. Hors de
        # `aide_display_dict` à dessein — c'est une lecture du jour, pas un
        # attribut de l'aide.
        "disponibilite": disponibilite(verdict.aide, today),
        "eligible": verdict.status != "non_eligible",
        "criteresRemplis": verdict.criteres_remplis,
        "criteresNonRemplis": verdict.criteres_non_remplis,
        "raisonIneligibilite": verdict.raison_ineligibilite,
        # Le refus vient-il d'une réponse de l'utilisateur, ou des seuls filtres
        # automatiques ? Le front n'affiche que les premiers : se voir refuser
        # une aide sur un critère qu'on n'a jamais eu à trancher n'apprend rien.
        # Champ porté par TOUS les statuts (false hors non_eligible) pour que le
        # front n'ait pas à distinguer « absent » de « non ».
        "elimineParReponse": elimine_par_reponse,
        "leviers": verdict.leviers,
        "llmEvaluation": {
            "explication": explication,
            "evaluations": verdict.evaluations,
            "incertitudes": incertitudes,
        },
    }


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------


def engine_ready_aides(aides: dict[str, Aide]) -> dict[str, Aide]:
    """Aides sans aucune condition `untyped` — les seules que le moteur traite."""
    return {
        slug: a for slug, a in aides.items() if not any(c.kind == "untyped" for c in a.conditions)
    }


def _codes_reserves(brut: object) -> set[str]:
    """Liste de codes portée par une clé réservée (`_raisons`, `_familles`).

    Tolérante par construction : le dict vient de `projets.questionnaire`, donc
    d'un enregistrement qui peut précéder la clé. Absence, valeur d'un autre
    type et éléments non textuels rendent un ensemble vide — « rien de déclaré »,
    qui ne filtre rien.
    """
    if not isinstance(brut, (list, tuple, set)):
        return set()
    return {c for c in brut if isinstance(c, str)}


def familles_heritees(declarees: set[str]) -> set[str]:
    """Traduit les codes de famille RETIRÉS du référentiel (`FAMILLES_HERITEES`).

    Un projet garde dans `projets.questionnaire._familles` les codes cochés le
    jour où il a été cadré, et rien ne les réécrit. Sans cette traduction, un
    projet coché « Tourisme et hébergement » avant la scission du 2026-09-22
    déclarerait une famille qu'aucune aide ne porte plus : `hors_famille`
    (déclaré non vide, intersection vide) écarterait TOUTES les aides taguées,
    l'inverse exact de ce que l'utilisateur a demandé.

    Un héritage ÉLARGIT toujours — l'ancien code vaut ses successeurs — donc la
    traduction ne peut rien retirer. Un code inconnu est laissé tel quel :
    `hors_famille` est déjà fail-open par aide, et une famille orpheline ne
    ferme rien d'autre qu'elle-même.
    """
    return {code for d in declarees for code in FAMILLES_HERITEES.get(d, frozenset({d}))}


def hors_projet(aide: Aide, raisons: set[str]) -> bool:
    """Vrai si l'aide ne sert AUCUNE des finalités déclarées par l'utilisateur.

    Fail-open : une aide sans `raison` renseignée passe toujours (on ne masque
    jamais une aide faute de donnée). `raisons` vide ⇒ aucun filtrage.
    """
    if not raisons or not aide.raison:
        return False
    return not (set(aide.raison) & raisons)


# Familles qu'une finalité IMPLIQUE, pour les projets qui n'ont pas vu l'étape
# « Votre projet » dans sa version familles. L'intention étant exclusive depuis
# le passage au choix unique, l'étape ne s'affiche que pour « faire vivre le
# lieu » seul ; un projet ANCIEN à plusieurs intentions qui repasse le wizard la
# verra aussi, et il ne faut pas lui retirer ses aides de restauration parce
# qu'il aura coché « spectacles ». Projection de la skill de prospection.
FAMILLES_PAR_RAISON: dict[str, frozenset[str]] = {
    "restauration_travaux": frozenset(
        {
            "restauration_bati",
            "energie_climat",
            "eau_nature_domaine",
            "securite_risques",
            "parcs_jardins_paysages",
        }
    ),
    "etude_ingenierie": frozenset({"etudes_ingenierie"}),
}


def familles_effectives(declarees: set[str], raisons: set[str]) -> set[str]:
    """Familles déclarées, complétées de celles qu'impliquent les finalités."""
    return set(declarees).union(*(FAMILLES_PAR_RAISON.get(r, frozenset()) for r in raisons))


def hors_famille(aide: Aide, effectives: set[str], declarees: set[str]) -> bool:
    """Vrai si l'aide ne relève d'AUCUNE des familles retenues par le projet.

    Calqué sur `hors_projet`, avec le même fail-open et la même asymétrie : une
    aide sans `familles` passe toujours (on ne masque jamais une aide faute de
    tag), et rien n'est filtré tant que l'utilisateur n'a rien DÉCLARÉ — c'est
    le sens de « Je ne sais pas encore, montrez-moi tout », qui envoie une liste
    vide et doit tout garder.

    `declarees` gouverne l'activation du filtre, `effectives` son contenu : les
    familles implicites d'une finalité ne déclenchent jamais un filtrage à
    elles seules (sinon un projet de restauration, qui ne voit pas l'étape
    familles, perdrait toute aide taguée hors des cinq familles de travaux).
    """
    if not declarees or not aide.familles:
        return False
    return not (set(aide.familles) & effectives)


Disponibilite = Literal["maintenant", "bientot"]


def disponibilite(aide: Aide, today: date | None = None) -> Disponibilite:
    """Fenêtre de candidature à la date du jour — axe transverse au statut.

    « maintenant » = le dossier peut être déposé aujourd'hui. « bientot » =
    tous les autres cas de fenêtre fermée, qu'elle ne soit pas encore ouverte
    (`date_ouverture` future) ou déjà refermée (`date_limite` passée). Les
    dispositifs annuels reconduits tombent dans le second cas : leur date
    périmée ne dit pas que l'aide a disparu, seulement que la session est
    passée — d'où l'affichage en « disponibles bientôt » plutôt qu'une
    exclusion du diagnostic.

    Ne s'appuie que sur les dates structurées : `permanent: true` (dépôt au fil
    de l'eau) court-circuite tout, et une aide sans aucune date est réputée
    ouverte (fail-open : on ne masque jamais une aide faute de donnée).
    `date_limite == today` reste ouvert, comme partout ailleurs.
    """
    cal = aide.calendrier
    if cal.permanent:
        return "maintenant"
    t = today or date.today()
    if cal.date_ouverture and cal.date_ouverture > t:
        return "bientot"
    if cal.date_limite and cal.date_limite < t:
        return "bientot"
    return "maintenant"


def run_deterministic_diagnostic(
    aides: dict[str, Aide],
    facts: dict[str, FactDef],
    monument: dict,
    population: int | None,
    answers: dict[str, object] | None = None,
    today: date | None = None,
) -> dict:
    """Diagnostic 100 % déterministe sur les aides engine-ready.

    Retourne la forme AideDiagnosticResult (aide en snake_case, à caméliser par
    le routeur comme pour run_diagnostic). `today` est résolu une fois pour
    toute la passe : la disponibilité de chaque aide est datée du même jour, et
    les tests peuvent la figer.
    """
    today = today or date.today()
    fact_answers, reserved = split_reserved_answers(answers)
    raisons = _codes_reserves(reserved.get("_raisons"))
    # `_familles` : ce que l'utilisateur a coché à l'étape « Votre projet » d'un
    # projet « faire vivre le lieu ». Clé absente comme liste vide ⇒ rien de
    # déclaré, donc aucun filtrage (cf. hors_famille).
    # `familles_heritees` traduit d'abord les codes retirés du référentiel : un
    # projet cadré avant la scission du 2026-09-22 porte encore
    # `tourisme_hebergement`, que plus aucune aide ne tague.
    familles_declarees = familles_heritees(_codes_reserves(reserved.get("_familles")))
    familles = familles_effectives(familles_declarees, raisons)

    ready = engine_ready_aides(aides)
    # La fenêtre de candidature n'écarte plus aucune aide : elle est portée par
    # `disponibilite` sur chaque résultat (cf. _match_result). Une session
    # passée n'est pas une inéligibilité, c'est un dossier à préparer.
    # Exclure les aides hors du projet déclaré (étape « Votre projet ») : leurs
    # faits manquants pollueraient le questionnaire (« À quelle fréquence la
    # manifestation est-elle organisée ? » pour un ravalement de façade).
    ready_avant_raisons = len(ready)
    ready = {slug: a for slug, a in ready.items() if not hors_projet(a, raisons)}
    hors_sujet = ready_avant_raisons - len(ready)

    # Même geste, un cran plus fin : la FAMILLE thématique, que `raison` ne sait
    # pas dire (un festival, un gîte et un outil de médiation partagent
    # « valorisation_rayonnement »). Posé juste après `hors_projet` pour que les
    # deux filtres de cadrage comptent dans le même `hors_sujet`.
    ready_avant_familles = len(ready)
    ready = {
        slug: a for slug, a in ready.items() if not hors_famille(a, familles, familles_declarees)
    }
    hors_sujet += ready_avant_familles - len(ready)

    reponses = deduire_faits_des_faits(
        deduire_faits_des_familles(
            familles,
            familles_declarees,
            deduire_faits_des_raisons(raisons, fact_answers, facts),
            facts,
            ready,
        ),
        facts,
    )
    ctx = build_context(monument, population, reponses)
    # Exclure les aides dont l'utilisateur a déclaré qu'elles ne le concernent
    # pas (périmètre de l'aide : festivals, compagnies, écoles d'art…). Même
    # traitement que les aides hors projet : elles n'ont jamais été candidates.
    ready_avant_perimetre = len(ready)
    ready = {slug: a for slug, a in ready.items() if not hors_perimetre(a, ctx, facts)}
    hors_sujet += ready_avant_perimetre - len(ready)

    verdicts = [evaluate_aide(a, monument, population, ctx, facts) for a in ready.values()]

    eligibles = [v for v in verdicts if v.status == "eligible"]
    potentiels = [v for v in verdicts if v.status == "potentiel"]
    non_eligibles = [v for v in verdicts if v.status == "non_eligible"]
    # « À débloquer » : triées par enjeu décroissant, la plus grosse démarche
    # payante en tête. Les aides sans montant chiffré ferment la marche.
    atteignables = sorted(
        (v for v in verdicts if v.status == "atteignable"),
        key=lambda v: v.aide.financement.montant_max or 0,
        reverse=True,
    )

    questions = build_questions(verdicts, facts)

    # Le montant potentiel couvre tout ce qui est à portée sans démarche
    # préalable : les éligibles (« disponibles maintenant »), les potentiels
    # (« à confirmer ») et, pour ces deux statuts, ceux dont la fenêtre est
    # fermée ou pas encore ouverte (« disponibles bientôt »). Les atteignables
    # en sont exclus, quelle que soit leur fenêtre : ils supposent une démarche
    # et sont chiffrés à part dans `montantAtteignableTotal`.
    montant_total = sum(v.aide.financement.montant_max or 0 for v in eligibles + potentiels)
    montant_atteignable = sum(v.aide.financement.montant_max or 0 for v in atteignables)
    # Part des travaux : beaucoup d'aides ne plafonnent pas en euros et ne se
    # chiffrent que là. Périmètre plus large que le montant potentiel — les
    # trois seaux affichés (« disponibles maintenant », « à confirmer », « à
    # débloquer »), puisque la case annonce un maximum atteignable, pas un acquis.
    taux_travaux = taux_travaux_cumule(eligibles + potentiels + atteignables)

    logger.info(
        "DIAGNOSTIC DÉTERMINISTE %s | ready=%d (hors projet=%d) éligibles=%d "
        "atteignables=%d potentiels=%d non=%d questions=%d",
        monument.get("nom", "?"),
        len(ready),
        hors_sujet,
        len(eligibles),
        len(atteignables),
        len(potentiels),
        len(non_eligibles),
        len(questions),
    )

    return {
        "monumentId": monument.get("id"),
        "totalAidesAnalysees": len(ready),
        "aidesEligibles": [_match_result(v, today) for v in eligibles],
        "aidesPotentiellementEligibles": [_match_result(v, today) for v in potentiels],
        "aidesAtteignables": [_match_result(v, today) for v in atteignables],
        "aidesNonEligibles": [_match_result(v, today) for v in non_eligibles],
        "montantPotentielTotal": montant_total if montant_total > 0 else None,
        "montantAtteignableTotal": montant_atteignable if montant_atteignable > 0 else None,
        "tauxTravauxMaxPct": taux_travaux,
        "qcmQuestions": questions,
    }
