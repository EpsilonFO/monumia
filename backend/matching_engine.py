"""
Matching engine v2 — uses normalised aides_v2 tables.

Three-phase approach:
  1. SQL pre-filter via prefiltrer_aides() → candidate aide UUIDs
  2. Python builds human-readable criteria match/mismatch lists
  3. LLM fine-matching on conditions_eligibilite_detail for nuanced rules
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional

from mistralai.client import Mistral
from supabase import Client

from prompts.matching import prompt_1, prompt_2, prompt_3

logger = logging.getLogger(__name__)

PROTECTION_LABELS = {
    "classe": "Classé Monument Historique",
    "inscrit": "Inscrit Monument Historique",
    "abords": "En périmètre d'un MH (abords)",
    "spr": "Site Patrimonial Remarquable (SPR)",
    "non_protege": "Non protégé",
}

OWNERSHIP_LABELS = {
    "public_commune": "Commune",
    "public_departement": "Département",
    "public_region": "Région",
    "public_etat": "État",
    "prive_personne_physique": "Propriétaire privé (personne physique)",
    "prive_sci": "SCI",
    "association": "Association",
    "mixte": "Propriété mixte",
}

SEGMENT_LABELS = {
    "commune": "Commune",
    "prive": "Propriétaire privé",
    "btp": "Entreprise BTP",
}

TRAVAUX_LABELS = {
    "toiture": "Toiture",
    "charpente": "Charpente",
    "couverture": "Couverture",
    "facade": "Façade",
    "maconnerie": "Maçonnerie",
    "vitraux": "Vitraux",
    "peintures_murales": "Peintures murales",
    "menuiserie": "Menuiserie",
    "electricite": "Électricité",
    "plomberie": "Plomberie",
    "chauffage": "Chauffage",
    "accessibilite": "Accessibilité",
    "mise_en_securite": "Mise en sécurité",
    "restauration_generale": "Restauration générale",
    "etude_prealable": "Étude préalable",
    "mobilier": "Mobilier",
    "orgues": "Orgues",
    "parcs_jardins": "Parcs et jardins",
    "protection_solaire": "Protection solaire",
    "ventilation": "Ventilation",
}

ETAT_LABELS = {
    "bon": "Bon état",
    "moyen": "État moyen",
    "mauvais": "Mauvais état",
    "peril": "En péril",
}


def _label(mapping: dict, value: str) -> str:
    return mapping.get(value, value)


def _labels(mapping: dict, values: list) -> str:
    return ", ".join(_label(mapping, v) for v in values)


# ---------------------------------------------------------------------------
# Phase 1: SQL pre-filter
# ---------------------------------------------------------------------------


def prefiltrer_aides(
    supabase: Client,
    monument: dict,
    user: dict,
    travaux_filtres: Optional[list[str]] = None,
) -> list[str]:
    """Call the prefiltrer_aides SQL function and return matching aide UUIDs."""
    travaux = travaux_filtres or monument.get("travaux_envisages") or []

    # Resolve code_insee: fallback from commune name if empty
    code_insee = monument.get("code_insee") or ""
    if not code_insee and monument.get("commune"):
        commune_lookup = (
            supabase.table("communes")
            .select("code_insee, population")
            .eq("nom_commune", monument["commune"])
            .limit(1)
            .execute()
        )
        if commune_lookup.data:
            code_insee = commune_lookup.data[0].get("code_insee", "")

    # Extract departement code from code_insee (e.g. "10025" → "10", "2A004" → "2A")
    departement_code = None
    if code_insee:
        if code_insee[:2] in ("2A", "2B"):
            departement_code = code_insee[:2]
        elif code_insee[:3] in ("971", "972", "973", "974", "975", "976"):
            departement_code = code_insee[:3]
        else:
            departement_code = code_insee[:2]

    # Fetch commune population
    population = None
    if code_insee and user.get("segment") == "commune":
        commune_result = supabase.table("communes").select("population").eq("code_insee", code_insee).single().execute()
        if commune_result.data:
            population = commune_result.data.get("population")

    params = {
        "p_protection": monument.get("protection"),
        "p_proprietaire": monument.get("proprietaire"),
        "p_travaux": travaux if travaux else None,
        "p_region": monument.get("region"),
        "p_departement": departement_code,
        "p_segment": user.get("segment"),
        "p_population": population,
        "p_etat_conservation": monument.get("etat_conservation"),
    }
    print(f"\n[RPC prefiltrer_aides] params: {json.dumps(params, ensure_ascii=False, default=str)}")

    result = supabase.rpc("prefiltrer_aides", params).execute()

    return [row["aide_id"] for row in (result.data or [])]


# ---------------------------------------------------------------------------
# Phase 2: Build human-readable criteria for each aide
# ---------------------------------------------------------------------------


def _fetch_aide_with_joins(supabase: Client, aide_id: str) -> dict:
    """Fetch an aide_v2 row with its join table data."""
    aide = (supabase.table("aides_v2").select("*").eq("id", aide_id).single().execute()).data

    if not aide:
        return {}

    # Fetch join tables
    aide["protections"] = [
        r["protection_code"]
        for r in (supabase.table("aides_protections").select("protection_code").eq("aide_id", aide_id).execute()).data
        or []
    ]
    aide["proprietaires"] = [
        r["proprietaire_code"]
        for r in (
            supabase.table("aides_proprietaires").select("proprietaire_code").eq("aide_id", aide_id).execute()
        ).data
        or []
    ]
    aide["travaux"] = [
        r["travaux_code"]
        for r in (supabase.table("aides_travaux").select("travaux_code").eq("aide_id", aide_id).execute()).data or []
    ]
    aide["regions"] = [
        r["region_code"]
        for r in (supabase.table("aides_regions").select("region_code").eq("aide_id", aide_id).execute()).data or []
    ]
    aide["departements"] = [
        r["departement_code"]
        for r in (supabase.table("aides_departements").select("departement_code").eq("aide_id", aide_id).execute()).data
        or []
    ]
    aide["segments"] = [
        r["segment_code"]
        for r in (supabase.table("aides_segments").select("segment_code").eq("aide_id", aide_id).execute()).data or []
    ]
    aide["etats_conservation"] = [
        r["etat_conservation_code"]
        for r in (
            supabase.table("aides_etats_conservation").select("etat_conservation_code").eq("aide_id", aide_id).execute()
        ).data
        or []
    ]

    return aide


def fetch_aides_with_joins(supabase: Client, aide_ids: list[str]) -> list[dict]:
    """Fetch multiple aides with their join data. Batch queries per join table."""
    if not aide_ids:
        return []

    # Fetch all aide rows at once
    aides_result = supabase.table("aides_v2").select("*").in_("id", aide_ids).execute()
    aides_by_id = {a["id"]: a for a in (aides_result.data or [])}

    # Initialize join lists
    for aide in aides_by_id.values():
        aide["protections"] = []
        aide["proprietaires"] = []
        aide["travaux"] = []
        aide["regions"] = []
        aide["departements"] = []
        aide["segments"] = []
        aide["etats_conservation"] = []

    # Batch fetch each join table
    join_queries = {
        "aides_protections": ("protection_code", "protections"),
        "aides_proprietaires": ("proprietaire_code", "proprietaires"),
        "aides_travaux": ("travaux_code", "travaux"),
        "aides_regions": ("region_code", "regions"),
        "aides_departements": ("departement_code", "departements"),
        "aides_segments": ("segment_code", "segments"),
        "aides_etats_conservation": ("etat_conservation_code", "etats_conservation"),
    }

    for table_name, (code_col, aide_key) in join_queries.items():
        rows = (supabase.table(table_name).select(f"aide_id, {code_col}").in_("aide_id", aide_ids).execute()).data or []
        for row in rows:
            aid = aides_by_id.get(row["aide_id"])
            if aid:
                aid[aide_key].append(row[code_col])

    return list(aides_by_id.values())


def _check_eligibility(
    aide: dict,
    monument: dict,
    user: dict,
    mode_projet: bool,
    travaux_filtres: list[str],
    population: Optional[int] = None,
) -> dict:
    """Build human-readable criteria match lists for a single aide.

    The aide dict must already contain join data (protections, proprietaires, etc.)
    as populated by fetch_aides_with_joins().
    """
    criteres_remplis: list[str] = []
    criteres_non_remplis: list[str] = []

    # Protection
    protections = aide.get("protections") or []
    if protections:
        if monument.get("protection") in protections:
            criteres_remplis.append(f"Protection : {_label(PROTECTION_LABELS, monument.get('protection'))}")
        else:
            criteres_non_remplis.append(f"Protection requise : {_labels(PROTECTION_LABELS, protections)}")
    else:
        criteres_remplis.append("Tous niveaux de protection")

    # Propriétaire
    proprietaires = aide.get("proprietaires") or []
    if proprietaires:
        if monument.get("proprietaire") in proprietaires:
            criteres_remplis.append(f"Type de propriétaire : {_label(OWNERSHIP_LABELS, monument.get('proprietaire'))}")
        else:
            criteres_non_remplis.append(f"Propriétaire éligible : {_labels(OWNERSHIP_LABELS, proprietaires)}")
    else:
        criteres_remplis.append("Tous types de propriétaires")

    # Travaux
    travaux_eligibles = aide.get("travaux") or []
    if travaux_eligibles:
        travaux_to_check = (
            travaux_filtres if (mode_projet and travaux_filtres) else (monument.get("travaux_envisages") or [])
        )
        if not travaux_to_check:
            criteres_remplis.append("Types de travaux : non spécifiés (compatible)")
        elif any(t in travaux_eligibles for t in travaux_to_check):
            criteres_remplis.append("Types de travaux compatibles")
        else:
            criteres_non_remplis.append(f"Travaux éligibles : {_labels(TRAVAUX_LABELS, travaux_eligibles)}")
    else:
        criteres_remplis.append("Tous types de travaux")

    # Région
    regions = aide.get("regions") or []
    if regions:
        if monument.get("region") in regions:
            criteres_remplis.append(f"Région : {monument.get('region')}")
        else:
            criteres_non_remplis.append(f"Région requise : {', '.join(regions)}")
    else:
        criteres_remplis.append("Toute la France")

    # Département
    departements = aide.get("departements") or []
    if departements:
        if monument.get("departement") in departements:
            criteres_remplis.append(f"Département : {monument.get('departement')}")
        else:
            criteres_non_remplis.append(f"Département requis : {', '.join(departements)}")

    # Segment
    segments = aide.get("segments") or []
    if segments:
        if user.get("segment") in segments:
            criteres_remplis.append(f"Segment : {_label(SEGMENT_LABELS, user.get('segment'))}")
        else:
            criteres_non_remplis.append(f"Réservé aux : {_labels(SEGMENT_LABELS, segments)}")
    else:
        criteres_remplis.append("Communes et privés")

    # Population
    max_pop = aide.get("commune_max_population")
    if max_pop is not None:
        if user.get("segment") == "commune" and population and population <= max_pop:
            criteres_remplis.append(f"Commune ≤ {max_pop:,} hab. ({population} hab.)")
        elif user.get("segment") == "commune" and population and population > max_pop:
            criteres_non_remplis.append(f"Réservé aux communes ≤ {max_pop:,} hab.")

    # État de conservation
    etats = aide.get("etats_conservation") or []
    if etats:
        etat = monument.get("etat_conservation")
        if etat in etats:
            criteres_remplis.append(f"État de conservation : {_label(ETAT_LABELS, etat)}")
        else:
            criteres_non_remplis.append(f"État requis : {_labels(ETAT_LABELS, etats)}")

    eligible = len(criteres_non_remplis) == 0

    return {
        "aide": aide,
        "eligible": eligible,
        "criteresRemplis": criteres_remplis,
        "criteresNonRemplis": criteres_non_remplis,
        "raisonIneligibilite": criteres_non_remplis[0] if not eligible else None,
    }


# ---------------------------------------------------------------------------
# Phase 3: LLM fine-matching on conditions_eligibilite_detail
# ---------------------------------------------------------------------------


def _build_monument_profile(monument: dict, user: dict, population: Optional[int]) -> str:
    """Build a human-readable text description of the monument for the LLM."""
    lines = []
    lines.append(f"Nom : {monument.get('nom', 'Non renseigné')}")
    lines.append(f"Protection : {_label(PROTECTION_LABELS, monument.get('protection', ''))}")
    lines.append(f"Propriétaire : {_label(OWNERSHIP_LABELS, monument.get('proprietaire', ''))}")
    lines.append(f"Commune : {monument.get('commune', 'Non renseigné')}")
    lines.append(f"Code INSEE : {monument.get('code_insee', 'Non renseigné')}")
    lines.append(f"Département : {monument.get('departement', 'Non renseigné')}")
    lines.append(f"Région : {monument.get('region', 'Non renseigné')}")
    if population is not None:
        lines.append(f"Population commune : {population} habitants")
    lines.append(f"État de conservation : {_label(ETAT_LABELS, monument.get('etat_conservation', ''))}")
    travaux = monument.get("travaux_envisages") or []
    if travaux:
        lines.append(f"Travaux envisagés : {_labels(TRAVAUX_LABELS, travaux)}")
    lines.append(f"Segment utilisateur : {_label(SEGMENT_LABELS, user.get('segment', ''))}")
    if monument.get("siecle_construction"):
        lines.append(f"Siècle de construction : {monument['siecle_construction']}")
    if monument.get("reference_merimee"):
        lines.append(f"Référence Mérimée : {monument['reference_merimee']}")
    return "\n".join(lines)


def _llm_evaluate_eligibility(
    monument_profile: str,
    aide_nom: str,
    conditions_detail: str,
    prompt_template: str,
) -> dict:
    """Call Mistral to evaluate fine eligibility with a specific prompt template.

    Returns {"eligible": bool, "explication": str, "incertitudes": list[str]}
    """
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        logger.warning("MISTRAL_API_KEY not set, skipping LLM evaluation")
        return {
            "eligible": True,
            "explication": "",
            "incertitudes": ["Évaluation LLM indisponible"],
        }

    client = Mistral(api_key=api_key)

    prompt = prompt_template.format(
        monument_profile=monument_profile,
        aide_nom=aide_nom,
        conditions_detail=conditions_detail,
    )

    try:
        response = client.chat.complete(
            model="mistral-small-latest",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        choice = response.choices[0]
        content = choice.message.content
        result = json.loads(content)
        return result
    except Exception as e:
        logger.error(f"LLM evaluation failed for aide '{aide_nom}': {e}")
        return {
            "eligible": True,
            "explication": "",
            "incertitudes": [f"Erreur LLM : {e}"],
        }


def _aggregate_llm_results(results: list[dict]) -> dict:
    """Aggregate results from 3 LLM calls using voting logic.

    Returns a consolidated result based on majority vote:
    - If 2+ prompts say eligible → eligible
    - If 2+ prompts say ineligible → ineligible
    - Merges all incertitudes and explications
    """
    eligible_votes = sum(1 for r in results if r.get("eligible", True))
    ineligible_votes = len(results) - eligible_votes

    all_incertitudes = []
    all_explications = []

    for r in results:
        all_incertitudes.extend(r.get("incertitudes", []))
        explication = r.get("explication", "")
        if explication:
            all_explications.append(explication)

    # Remove duplicates from incertitudes
    all_incertitudes = list(set(all_incertitudes))

    # Majority vote
    aggregated_eligible = eligible_votes >= 2
    aggregated_explication = " | ".join(all_explications)

    return {
        "eligible": aggregated_eligible,
        "explication": aggregated_explication,
        "incertitudes": all_incertitudes,
        "votes": {
            "eligible": eligible_votes,
            "ineligible": ineligible_votes,
        },
    }


def _run_llm_phase(
    eligible_results: list[dict],
    monument_profile: str,
) -> list[dict]:
    """Run LLM evaluation on eligible aides that have conditions_eligibilite_detail.

    Uses 3 prompts with different conditioning and aggregates results by majority vote.

    Returns three lists: (still_eligible, potentially_eligible, downgraded_to_ineligible)
    - still_eligible: LLM says eligible AND no incertitudes
    - potentially_eligible: LLM says eligible BUT has incertitudes
    - downgraded: LLM says not eligible
    """
    still_eligible = []
    potentially_eligible = []
    downgraded = []

    for result in eligible_results:
        aide = result["aide"]
        conditions = aide.get("conditions_eligibilite_detail")

        if not conditions:
            # No complex conditions — keep as eligible
            still_eligible.append(result)
            continue

        # Run 3 LLM evaluations with different prompts
        print(f"\n{'=' * 60}")
        print(f"[LLM TRIPLE EVALUATION] Aide: {aide.get('nom', '')}")
        print(f"{'=' * 60}")

        llm_results = []
        for i, prompt_template in enumerate([prompt_1, prompt_2, prompt_3], 1):
            print(f"\n  → Prompt {i}/3...")
            llm_result = _llm_evaluate_eligibility(
                monument_profile=monument_profile,
                aide_nom=aide.get("nom", ""),
                conditions_detail=conditions,
                prompt_template=prompt_template,
            )
            llm_results.append(llm_result)
            print(
                f"    Result: eligible={llm_result.get('eligible')}, incertitudes={len(llm_result.get('incertitudes', []))}"
            )

        # Aggregate results by majority vote
        aggregated = _aggregate_llm_results(llm_results)

        print(
            f"\n  → AGGREGATED: eligible={aggregated['eligible']} (votes: {aggregated['votes']['eligible']}/{len(llm_results)})"
        )

        result["llmEvaluation"] = {
            "explication": aggregated["explication"],
            "incertitudes": aggregated["incertitudes"],
            "votes": aggregated["votes"],
        }

        if aggregated["eligible"]:
            incertitudes = aggregated["incertitudes"]
            if incertitudes:
                potentially_eligible.append(result)
            else:
                still_eligible.append(result)
        else:
            result["eligible"] = False
            result["criteresNonRemplis"].append(f"Condition détaillée : {aggregated.get('explication', '')}")
            result["raisonIneligibilite"] = result["raisonIneligibilite"] or aggregated.get("explication", "")
            downgraded.append(result)

    return still_eligible, potentially_eligible, downgraded


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_diagnostic(
    supabase: Client,
    monument: dict,
    user: dict,
    mode_projet: bool = False,
    travaux_filtres: Optional[list[str]] = None,
) -> dict:
    """Run a full diagnostic: SQL pre-filter → criteria check → LLM fine-matching."""
    ctx_travaux = travaux_filtres or []

    # Phase 1: SQL pre-filter
    candidate_ids = prefiltrer_aides(supabase, monument, user, ctx_travaux or None)

    print(f"\n{'=' * 60}")
    print(f"[PRE-FILTER] Monument: {monument.get('nom')}")
    print(f"  protection={monument.get('protection')}, proprietaire={monument.get('proprietaire')}")
    print(f"  region={monument.get('region')}, departement={monument.get('departement')}")
    print(f"  segment={user.get('segment')}, travaux={ctx_travaux or monument.get('travaux_envisages')}")
    print(f"  → {len(candidate_ids)} aides candidates")
    print(f"{'=' * 60}")

    # Fetch all aides (candidates + non-candidates) for the full report
    all_aide_ids = [a["id"] for a in (supabase.table("aides_v2").select("id").execute()).data or []]
    non_candidate_ids = [aid for aid in all_aide_ids if aid not in candidate_ids]

    # Phase 2: Fetch aides with join data + build criteria
    candidate_aides = fetch_aides_with_joins(supabase, candidate_ids)
    non_candidate_aides = fetch_aides_with_joins(supabase, non_candidate_ids)

    print("\n[CANDIDATES] Aides pré-filtrées SQL:")
    for a in candidate_aides:
        print(f"  ✓ {a.get('nom_court') or a.get('nom')}")
    print("\n[NON-CANDIDATES] Aides exclues par SQL:")
    for a in non_candidate_aides:
        print(f"  ✗ {a.get('nom_court') or a.get('nom')}")

    # Resolve population for criteria display
    population = None
    code_insee = monument.get("code_insee")
    if code_insee and user.get("segment") == "commune":
        commune_result = supabase.table("communes").select("population").eq("code_insee", code_insee).single().execute()
        if commune_result.data:
            population = commune_result.data.get("population")

    eligible_results = [
        _check_eligibility(a, monument, user, mode_projet, ctx_travaux, population) for a in candidate_aides
    ]
    non_eligible_results = [
        _check_eligibility(a, monument, user, mode_projet, ctx_travaux, population) for a in non_candidate_aides
    ]

    # Phase 3: LLM fine-matching on eligible candidates
    monument_profile = _build_monument_profile(monument, user, population)
    still_eligible, potentially_eligible, downgraded = _run_llm_phase(eligible_results, monument_profile)
    non_eligible_results.extend(downgraded)

    montant_total = sum(r["aide"].get("montant_max") or 0 for r in still_eligible if r["aide"].get("montant_max"))

    return {
        "monumentId": monument["id"],
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "totalAidesAnalysees": len(all_aide_ids),
        "aidesEligibles": still_eligible,
        "aidesPotentiellementEligibles": potentially_eligible,
        "aidesNonEligibles": non_eligible_results,
        "montantPotentielTotal": montant_total if montant_total > 0 else None,
    }
