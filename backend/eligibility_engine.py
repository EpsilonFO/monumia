"""
Moteur de diagnostic déterministe — remplace les deux phases LLM de
matching_engine.py par l'évaluation des conditions typées (aide_conditions).

Aucun appel réseau, aucun LLM. Source de vérité : les YAML typés
(backend/data/aides/*.yaml) chargés via aides_schema. Ne traite QUE les aides
« engine-ready » : zéro condition `untyped`. Les autres sont ignorées (le
produit n'affichera que les aides dont la donnée est compilée).

Pipeline :
  1. hard_filters (déterministe, sémantique identique à prefiltrer_aides)
  2. évaluation des conditions `gate` contre le contexte (monument + commune +
     réponses aux faits) → éligible / potentiel / non éligible
  3. génération des questions depuis les faits manquants (dédup par fait, tri
     par nombre d'aides débloquées), avec eliminationsParOption CALCULÉ.

La sortie a la forme AideDiagnosticResult attendue par le frontend (le champ
historique `llmEvaluation` est conservé pour compat d'affichage — il ne
contient plus rien de LLM, juste les verdicts déterministes par condition).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from aides_schema import Aide, Condition, FactDef, evaluate_predicate
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


def build_context(
    monument: dict,
    population: int | None,
    answers: dict[str, object] | None = None,
) -> dict[str, object]:
    """Construit le contexte : chemins FIELD_REGISTRY → valeur connue, sinon absent.

    Un chemin absent du dict (commune.programmes, commune.eligible_detr tant que
    l'enrichissement n'existe pas) ⇒ valeur None à l'évaluation ⇒ incertitude
    (fail-closed). `answers` mappe fact_key → réponse de l'utilisateur.
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
    for path in ("commune.programmes", "commune.eligible_detr"):
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
    status: str  # "eligible" | "potentiel" | "non_eligible"
    criteres_remplis: list[str] = field(default_factory=list)
    criteres_non_remplis: list[str] = field(default_factory=list)
    raison_ineligibilite: str | None = None
    evaluations: list[dict] = field(default_factory=list)
    # fact_key → liste de (condition, predicate) des gates user_fact en incertitude
    missing_facts: dict[str, list[Condition]] = field(default_factory=dict)


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
    id (déjà la valeur), `skip`/option `unknown` → None (fait non renseigné).

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


def _applies(cond: Condition, ctx: dict, facts: dict[str, FactDef]) -> bool | None:
    """La condition s'applique-t-elle à ce profil ? None = indéterminé (fail-closed)."""
    if cond.applies_if is None:
        return True
    pred = cond.applies_if.predicate.root
    if cond.applies_if.field:
        return evaluate_predicate(pred, ctx.get(cond.applies_if.field))
    return evaluate_predicate(pred, _resolve_fact_value(ctx, cond.applies_if.fact, facts))


def _evaluate_hard_filters(
    aide: Aide, monument: dict, population: int | None
) -> tuple[list[str], list[str]]:
    """Évalue les hard_filters (sémantique prefiltrer_aides), SANS court-circuit.

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

    for cond in aide.conditions:
        applies = _applies(cond, ctx, facts)
        if applies is False:
            continue  # condition non applicable à ce profil → ni gate, ni affichée

        nature = _condition_nature(cond)

        # Conditions non dirimantes : affichées pour information, sans gater.
        if cond.effect != "gate":
            if nature == "discretionary":
                explication = "Apprécié par le financeur — point de vigilance pour le dossier."
            elif nature == "modulateur":
                explication = "Peut moduler le taux ou le montant (n'affecte pas l'éligibilité)."
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

        if cond.kind == "auto":
            result = evaluate_predicate(cond.predicate.root, ctx.get(cond.field))
            cat = None
        elif cond.kind == "user_fact":
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

    if has_non:
        verdict.status = "non_eligible"
    elif has_incertitude:
        verdict.status = "potentiel"
    else:
        verdict.status = "eligible"
    return verdict


# ---------------------------------------------------------------------------
# Génération des questions (déterministe)
# ---------------------------------------------------------------------------


def _numeric_tranches(thresholds: list[float], unit: str | None) -> list[dict]:
    """Construit des options MECE à partir de seuils triés.

    Chaque option porte un `repr` (valeur représentative de la tranche) : comme
    les bornes sont les seuils eux-mêmes, tout prédicat de seuil a une valeur de
    vérité CONSTANTE dans la tranche, donc évaluer au représentant est exact.
    """
    ts = sorted(set(thresholds))
    suffix = f" {unit}" if unit and unit not in ("€",) else (unit or "")

    def fmt(v: float) -> str:
        return str(int(v)) if float(v).is_integer() else str(v)

    options = []
    # Tranche basse : strictement sous le plus petit seuil.
    options.append(
        {"id": f"lt{fmt(ts[0])}", "label": f"Moins de {fmt(ts[0])}{suffix}", "repr": ts[0] - 1}
    )
    # Tranches intermédiaires.
    for lo, hi in zip(ts, ts[1:], strict=False):
        options.append(
            {"id": f"{fmt(lo)}_{fmt(hi)}", "label": f"De {fmt(lo)} à {fmt(hi)}{suffix}", "repr": lo}
        )
    # Tranche haute : au-dessus du plus grand seuil.
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
    if fact.type == "enum":
        return [
            {"id": o.id, "label": o.label, "value": o.id, "unknown": o.unknown}
            for o in fact.options or []
        ]
    # integer / number : tranches à partir des seuils des prédicats des gates.
    thresholds = []
    for c in gate_conds:
        for _op, val in c.predicate.root.items():
            if isinstance(val, (int, float)):
                thresholds.append(val)
    if not thresholds:
        return []
    return _numeric_tranches(thresholds, fact.unit)


def build_questions(
    verdicts: list[AideVerdict],
    facts: dict[str, FactDef],
) -> list[dict]:
    """Construit les QcmQuestion (contrat front) depuis les faits manquants.

    eliminationsParOption[option] = aides dont un gate sur ce fait devient
    IMPOSSIBLE si l'utilisateur choisit cette option — calculé en évaluant le
    prédicat à la valeur de l'option. Exact, pas de réparation de monotonie.
    """
    # fact_key → {aide_slug → [conditions gate sur ce fait]}
    by_fact: dict[str, dict[str, list[Condition]]] = {}
    for v in verdicts:
        if v.status != "potentiel":
            continue
        for fact_key, conds in v.missing_facts.items():
            by_fact.setdefault(fact_key, {})[v.aide.slug] = conds

    # Tri : faits débloquant le plus d'aides en premier.
    ordered = sorted(by_fact.items(), key=lambda kv: len(kv[1]), reverse=True)

    questions = []
    for fact_key, aides_conds in ordered:
        fact = facts.get(fact_key)
        if fact is None:
            continue
        all_gate_conds = [c for conds in aides_conds.values() for c in conds]
        options = _options_for_fact(fact, all_gate_conds)
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
                # devient faux à cette valeur.
                if any(evaluate_predicate(c.predicate.root, test_value) is False for c in conds):
                    eliminated.append(slug)
            if eliminated:
                elim[opt["id"]] = sorted(eliminated)

        questions.append(
            {
                "id": fact_key,
                "question": fact.question,
                "options": [{"id": o["id"], "label": o["label"]} for o in options]
                + [{"id": "skip", "label": "Je ne sais pas"}],
                "aideIds": sorted(aides_conds.keys()),
                "eliminatingOptionIds": [],
                "eliminationsParOption": elim,
                "categorie": fact_key,
            }
        )
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


def _match_result(verdict: AideVerdict) -> dict:
    """Forme AideMatchResult attendue par le front."""
    incertitudes = [e for e in verdict.evaluations if e["verdict"] == INCERTITUDE]
    n_non = sum(1 for e in verdict.evaluations if e["verdict"] == NON)
    if verdict.status == "eligible":
        explication = "Tous les critères vérifiables sont satisfaits."
    elif verdict.status == "potentiel":
        explication = f"{len(incertitudes)} information(s) à confirmer."
    else:
        explication = verdict.raison_ineligibilite or f"{n_non} critère(s) non satisfait(s)."
    return {
        "aide": aide_display_dict(verdict.aide),
        "eligible": verdict.status != "non_eligible",
        "criteresRemplis": verdict.criteres_remplis,
        "criteresNonRemplis": verdict.criteres_non_remplis,
        "raisonIneligibilite": verdict.raison_ineligibilite,
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


def candidature_close(aide: Aide, today: date | None = None) -> bool:
    """Vrai si la fenêtre de dépôt des candidatures est passée.

    Reproduit la logique SQL de `prefiltrer_aides` (migration
    20260528203714) pour que le moteur déterministe et le diagnostic LLM
    masquent les mêmes aides : une aide est close si elle n'est PAS permanente
    et que sa date limite est strictement dépassée. Une aide permanente
    (dépôt au fil de l'eau) ou sans date limite n'est jamais close.
    """
    cal = aide.calendrier
    if cal.permanent or cal.date_limite is None:
        return False
    return cal.date_limite < (today or date.today())


def run_deterministic_diagnostic(
    aides: dict[str, Aide],
    facts: dict[str, FactDef],
    monument: dict,
    population: int | None,
    answers: dict[str, object] | None = None,
) -> dict:
    """Diagnostic 100 % déterministe sur les aides engine-ready.

    Retourne la forme AideDiagnosticResult (aide en snake_case, à caméliser par
    le routeur comme pour run_diagnostic).
    """
    ready = engine_ready_aides(aides)
    # Exclure les aides dont la fenêtre de candidature est close (cf.
    # prefiltrer_aides côté SQL) : une aide à date limite dépassée et non
    # permanente n'est plus mobilisable, on ne l'analyse donc pas.
    ready_avant_dates = len(ready)
    ready = {slug: a for slug, a in ready.items() if not candidature_close(a)}
    closes = ready_avant_dates - len(ready)
    ctx = build_context(monument, population, answers)

    verdicts = [evaluate_aide(a, monument, population, ctx, facts) for a in ready.values()]

    eligibles = [v for v in verdicts if v.status == "eligible"]
    potentiels = [v for v in verdicts if v.status == "potentiel"]
    non_eligibles = [v for v in verdicts if v.status == "non_eligible"]

    questions = build_questions(verdicts, facts)

    montant_total = sum(
        v.aide.financement.montant_max or 0 for v in eligibles if v.aide.financement.montant_max
    )

    logger.info(
        "DIAGNOSTIC DÉTERMINISTE %s | ready=%d (closes exclues=%d) éligibles=%d "
        "potentiels=%d non=%d questions=%d",
        monument.get("nom", "?"),
        len(ready),
        closes,
        len(eligibles),
        len(potentiels),
        len(non_eligibles),
        len(questions),
    )

    return {
        "monumentId": monument.get("id"),
        "totalAidesAnalysees": len(ready),
        "aidesEligibles": [_match_result(v) for v in eligibles],
        "aidesPotentiellementEligibles": [_match_result(v) for v in potentiels],
        "aidesNonEligibles": [_match_result(v) for v in non_eligibles],
        "montantPotentielTotal": montant_total if montant_total > 0 else None,
        "qcmQuestions": questions,
    }
