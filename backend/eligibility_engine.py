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
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from aides_schema import (
    ENUM_FACT_TYPES,
    Aide,
    AppliesIf,
    Condition,
    FactDef,
    MultiValue,
    evaluate_predicate,
)
from labels import (
    DEPARTEMENT_LABELS,
    ETAT_LABELS,
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
    par les prédicats : oui/non → bool, tranche numérique → représentant, enum →
    id (déjà la valeur), multi_enum → MultiValue des ids cochés, `skip`/option
    `unknown` → None (fait non renseigné).

    Sans cette normalisation, passer l'id brut « non » à un prédicat `eq: false`
    donnerait `"non" == False` → False, marquant l'aide non éligible à tort.
    """
    if raw is None or raw == "skip":
        return None
    if fact is None:
        return raw
    if fact.type == "boolean":
        if isinstance(raw, bool):
            return raw
        if raw == "oui":
            return True
        if raw == "non":
            return False
        return None
    if fact.type == "multi_enum":
        # Le front envoie une liste d'ids ; une réponse d'avant le passage en
        # choix multiple (chaîne unique, déjà persistée dans
        # `monuments.questionnaire`) reste lisible telle quelle.
        raws = raw if isinstance(raw, (list, tuple)) else [raw]
        unknown_ids = {o.id for o in fact.options or [] if o.unknown}
        kept = [v for v in raws if isinstance(v, str) and v != "skip" and v not in unknown_ids]
        return MultiValue(kept) if kept else None
    if fact.type == "enum":
        for opt in fact.options or []:
            if opt.id == raw and opt.unknown:
                return None
        return raw
    if fact.type in ("integer", "number"):
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            return raw
        return _tranche_repr(raw) if isinstance(raw, str) else None
    return raw


def _resolve_fact_value(ctx: dict, fact_key: str, facts: dict[str, FactDef]):
    """Valeur typée d'un fait depuis les réponses utilisateur (None si inconnu)."""
    return _normalize_answer(facts.get(fact_key), ctx.get("_answers", {}).get(fact_key))


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


def hors_perimetre(aide: Aide, ctx: dict, facts: dict[str, FactDef]) -> bool:
    """Vrai si l'utilisateur a répondu que cette aide ne concerne pas son projet.

    Fail-closed : tant que le fait de périmètre est inconnu, l'aide reste
    candidate (et la question est posée). Seule une réponse explicitement
    négative l'écarte.
    """
    return aide.applies_if is not None and _evaluate_clause(aide.applies_if, ctx, facts) is False


def _scoped_conditions(aide: Aide) -> list[Condition]:
    """Conditions de l'aide, chacune héritant du PÉRIMÈTRE de l'aide.

    Reporter la clause de l'aide sur ses conditions les fait entrer telles
    quelles dans la mécanique existante : le fait de périmètre est posé comme
    fait passerelle, et chaque question de l'aide en hérite d'un `dependsOn`.
    Une aide de 27 conditions se déclare donc en une ligne de YAML.

    Une condition qui porte DÉJÀ sa propre clause garde la sienne : elle est
    plus spécifique, et le branchement conditionnel se désactive alors de
    lui-même (fail-closed, la question est posée). Un gate qui porte sur le fait
    de périmètre lui-même n'hérite de rien : il serait sa propre condition
    d'applicabilité.
    """
    clause = aide.applies_if
    if clause is None:
        return aide.conditions
    return [
        c
        if c.applies_if is not None or c.fact == clause.fact
        else c.model_copy(update={"applies_if": clause})
        for c in aide.conditions
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
    """Plan d'action affichable pour un gate en échec sur un fait à levier."""
    levier = fact.levier
    assert levier is not None  # garanti par l'appelant
    plan = {
        "factId": cond.fact,
        "critere": cond.text,
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

    for cond in _scoped_conditions(aide):
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
                # Vraie condition, mais dont la vérification n'a de sens qu'au
                # montage du dossier (plan de financement, pièces justificatives).
                # La poser en amont ne renseignerait personne et éliminerait à
                # tort ; on l'affiche à confirmer avec l'organisme, sans gater.
                explication = (
                    "À confirmer avec l'organisme au moment du dossier "
                    "(sans incidence sur votre éligibilité)."
                )
            else:
                explication = "Information sur l'aide."
            verdict.evaluations.append(
                {
                    "critere": cond.text,
                    "verdict": INFO,
                    "explication": explication,
                    "nature": nature,
                }
            )
            continue

        fact: FactDef | None = None
        value = None
        if cond.kind == "auto":
            result = evaluate_predicate(cond.predicate.root, ctx.get(cond.field))
            cat = None
        elif cond.kind == "user_fact":
            fact = facts.get(cond.fact or "")
            value = _resolve_fact_value(ctx, cond.fact, facts)
            result = evaluate_predicate(cond.predicate.root, value)
            cat = cond.fact
        else:  # manual_check (ou untyped résiduel) : non évaluable → incertitude
            result = None
            cat = None

        # applies_if indéterminé : la condition s'applique peut-être (fail-closed)
        # → si on n'a pas pu trancher le gate, on reste en incertitude.
        if applies is None and result is True:
            result = None

        if result is True:
            verdict.evaluations.append(
                {
                    "critere": cond.text,
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
                    "verdict": NON,
                    "explication": "Critère non satisfait.",
                    "nature": nature,
                }
            )
        else:  # None → incertitude
            has_incertitude = True
            ev = {
                "critere": cond.text,
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
            if cat:
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


def _numeric_tranches(boundaries: list[float], unit: str | None) -> list[dict]:
    """Construit des options MECE à partir de bornes triées (cf.
    `_normalize_boundary`). Chaque option porte un `repr` (valeur représentative
    de la tranche), strictement intérieur à la bande, donc évaluer un prédicat de
    seuil au représentant est exact.
    """
    ts = sorted(set(boundaries))
    suffix = f" {unit}" if unit and unit not in ("€",) else (unit or "")

    def fmt(v: float) -> str:
        return str(int(v)) if float(v).is_integer() else str(v)

    options = []
    # Tranche basse : strictement sous la plus petite borne. Omise si elle ne
    # contient aucune valeur atteignable (borne basse <= 0 pour un compteur).
    if ts[0] - 1 >= 0:
        options.append(
            {"id": f"lt{fmt(ts[0])}", "label": f"Moins de {fmt(ts[0])}{suffix}", "repr": ts[0] - 1}
        )
    # Tranches intermédiaires.
    for lo, hi in zip(ts, ts[1:], strict=False):
        options.append(
            {"id": f"{fmt(lo)}_{fmt(hi)}", "label": f"De {fmt(lo)} à {fmt(hi)}{suffix}", "repr": lo}
        )
    # Tranche haute : au-dessus de la plus grande borne (incluse).
    options.append(
        {"id": f"ge{fmt(ts[-1])}", "label": f"{fmt(ts[-1])}{suffix} ou plus", "repr": ts[-1]}
    )
    return options


def _options_for_fact(fact: FactDef, gate_conds: list[Condition]) -> list[dict]:
    """Options d'une question, selon le type du fait. Chaque option a `value`
    (à injecter pour calculer l'élimination) ou `repr` (numérique)."""
    if fact.type == "boolean":
        return [
            {"id": "oui", "label": "Oui", "value": True},
            {"id": "non", "label": "Non", "value": False},
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


def build_questions(
    verdicts: list[AideVerdict],
    facts: dict[str, FactDef],
) -> list[dict]:
    """Construit les QcmQuestion (contrat front) depuis les faits manquants.

    Deux sources : les gates en incertitude (`missing_facts`, qui pilotent les
    éliminations) et les faits PASSERELLES (`gateway_facts`, qui débloquent
    l'applicabilité d'une condition sans jamais éliminer personne).

    eliminationsParOption[option] = aides dont un gate sur ce fait devient
    IMPOSSIBLE si l'utilisateur choisit cette option — calculé en évaluant le
    prédicat à la valeur de l'option. Exact, pas de réparation de monotonie.

    Sur une question à choix multiple (`multiple: true`), chaque entrée vaut
    « si c'était la seule case cochée » : cocher une case de plus ne peut que
    LIBÉRER des aides (sémantique existentielle, cf. MultiValue), d'où
    l'intersection côté front. Le verdict qui compte reste celui du moteur,
    réévalué avec les réponses complètes.
    """
    # fact_key → {aide_slug → [conditions gate sur ce fait]}
    by_fact: dict[str, dict[str, list[Condition]]] = {}
    gateway_by_fact: dict[str, dict[str, list[Condition]]] = {}
    montant_by_slug: dict[str, float] = {}
    for v in verdicts:
        if v.status not in ("potentiel", "atteignable"):
            continue
        montant_by_slug[v.aide.slug] = v.aide.financement.montant_max or 0
        for fact_key, conds in v.missing_facts.items():
            by_fact.setdefault(fact_key, {})[v.aide.slug] = conds
        for fact_key, conds in v.gateway_facts.items():
            gateway_by_fact.setdefault(fact_key, {})[v.aide.slug] = conds

    def aide_slugs(fact_key: str) -> list[str]:
        return sorted(set(by_fact.get(fact_key, {})) | set(gateway_by_fact.get(fact_key, {})))

    # Tri : les faits PASSERELLES d'abord (une question dont dépend une autre se
    # pose avant elle), puis ceux qui débloquent le plus d'aides. Le graphe
    # d'applicabilité n'a qu'un niveau dans le corpus : pas de tri topologique.
    ordered = sorted(
        set(by_fact) | set(gateway_by_fact),
        key=lambda k: (k not in gateway_by_fact, -len(aide_slugs(k)), k),
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
        for opt in options:
            if opt.get("unknown"):
                continue  # option « pas encore choisi » : n'élimine jamais
            test_value = opt.get("value", opt.get("repr"))
            eliminated = []
            for slug, conds in aides_conds.items():
                # L'aide est éliminée si AU MOINS un de ses gates sur ce fait
                # devient faux à cette valeur. Les gates synthétiques des faits
                # passerelles sont exclus : ils libèrent, ils n'éliminent pas.
                if any(evaluate_predicate(c.predicate.root, test_value) is False for c in conds):
                    eliminated.append(slug)
            if eliminated:
                elim[opt["id"]] = sorted(eliminated)

        slugs = aide_slugs(fact_key)
        multiple = fact.type == "multi_enum"
        # `unknown` est remonté au front : ces options portent un « ? » plutôt
        # qu'une pastille lettrée, ne comptent pour aucune élimination, et sont
        # exclusives des autres en choix multiple.
        shown_options = [
            {"id": o["id"], "label": o["label"], **({"unknown": True} if o.get("unknown") else {})}
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
            "categorie": fact_key,
        }
        depends_on = _depends_on(all_conds, built, options_by_fact)
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
    }


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


def hors_projet(aide: Aide, raisons: set[str]) -> bool:
    """Vrai si l'aide ne sert AUCUNE des finalités déclarées par l'utilisateur.

    Fail-open : une aide sans `raison` renseignée passe toujours (on ne masque
    jamais une aide faute de donnée). `raisons` vide ⇒ aucun filtrage.
    """
    if not raisons or not aide.raison:
        return False
    return not (set(aide.raison) & raisons)


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
    raw_raisons = reserved.get("_raisons")
    raisons = (
        {r for r in raw_raisons if isinstance(r, str)}
        if isinstance(raw_raisons, (list, tuple, set))
        else set()
    )

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

    ctx = build_context(monument, population, fact_answers)
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

    # Le montant potentiel est présenté comme mobilisable en l'état : on n'y
    # compte donc que les éligibles dont la fenêtre est ouverte aujourd'hui.
    montant_total = sum(
        v.aide.financement.montant_max or 0
        for v in eligibles
        if v.aide.financement.montant_max and disponibilite(v.aide, today) == "maintenant"
    )
    montant_atteignable = sum(v.aide.financement.montant_max or 0 for v in atteignables)

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
        "qcmQuestions": questions,
    }
