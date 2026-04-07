"""
Matching engine v2 — uses normalised aides_v2 tables.

Three-phase approach:
  1. SQL pre-filter via prefiltrer_aides() → candidate aide UUIDs
  2. Python builds human-readable criteria match/mismatch lists
  3. LLM fine-matching on conditions_eligibilite_detail for nuanced rules
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from mistralai.client import Mistral
from supabase import Client

from prompts.matching import prompt_1

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


def _label(mapping: dict, value: str | None) -> str:
    if value is None:
        return ""
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
    travaux_filtres: list[str] | None = None,
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
        commune_result = (
            supabase.table("communes")
            .select("population")
            .eq("code_insee", code_insee)
            .single()
            .execute()
        )
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
    print(
        f"  [SQL] RPC prefiltrer_aides → params: {json.dumps(params, ensure_ascii=False, default=str)}"
    )

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
        for r in (
            supabase.table("aides_protections")
            .select("protection_code")
            .eq("aide_id", aide_id)
            .execute()
        ).data
        or []
    ]
    aide["proprietaires"] = [
        r["proprietaire_code"]
        for r in (
            supabase.table("aides_proprietaires")
            .select("proprietaire_code")
            .eq("aide_id", aide_id)
            .execute()
        ).data
        or []
    ]
    aide["travaux"] = [
        r["travaux_code"]
        for r in (
            supabase.table("aides_travaux").select("travaux_code").eq("aide_id", aide_id).execute()
        ).data
        or []
    ]
    aide["regions"] = [
        r["region_code"]
        for r in (
            supabase.table("aides_regions").select("region_code").eq("aide_id", aide_id).execute()
        ).data
        or []
    ]
    aide["departements"] = [
        r["departement_code"]
        for r in (
            supabase.table("aides_departements")
            .select("departement_code")
            .eq("aide_id", aide_id)
            .execute()
        ).data
        or []
    ]
    aide["segments"] = [
        r["segment_code"]
        for r in (
            supabase.table("aides_segments").select("segment_code").eq("aide_id", aide_id).execute()
        ).data
        or []
    ]
    aide["etats_conservation"] = [
        r["etat_conservation_code"]
        for r in (
            supabase.table("aides_etats_conservation")
            .select("etat_conservation_code")
            .eq("aide_id", aide_id)
            .execute()
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
        rows = (
            supabase.table(table_name)
            .select(f"aide_id, {code_col}")
            .in_("aide_id", aide_ids)
            .execute()
        ).data or []
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
    population: int | None = None,
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
            criteres_remplis.append(
                f"Protection : {_label(PROTECTION_LABELS, monument.get('protection'))}"
            )
        else:
            criteres_non_remplis.append(
                f"Protection requise : {_labels(PROTECTION_LABELS, protections)}"
            )
    else:
        criteres_remplis.append("Tous niveaux de protection")

    # Propriétaire
    proprietaires = aide.get("proprietaires") or []
    if proprietaires:
        if monument.get("proprietaire") in proprietaires:
            criteres_remplis.append(
                f"Type de propriétaire : {_label(OWNERSHIP_LABELS, monument.get('proprietaire'))}"
            )
        else:
            criteres_non_remplis.append(
                f"Propriétaire éligible : {_labels(OWNERSHIP_LABELS, proprietaires)}"
            )
    else:
        criteres_remplis.append("Tous types de propriétaires")

    # Travaux
    travaux_eligibles = aide.get("travaux") or []
    if travaux_eligibles:
        travaux_to_check = (
            travaux_filtres
            if (mode_projet and travaux_filtres)
            else (monument.get("travaux_envisages") or [])
        )
        if not travaux_to_check:
            criteres_remplis.append("Types de travaux : non spécifiés (compatible)")
        elif any(t in travaux_eligibles for t in travaux_to_check):
            criteres_remplis.append("Types de travaux compatibles")
        else:
            criteres_non_remplis.append(
                f"Travaux éligibles : {_labels(TRAVAUX_LABELS, travaux_eligibles)}"
            )
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


def _build_monument_profile(monument: dict, user: dict, population: int | None) -> str:
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
    lines.append(
        f"État de conservation : {_label(ETAT_LABELS, monument.get('etat_conservation', ''))}"
    )
    travaux = monument.get("travaux_envisages") or []
    if travaux:
        lines.append(f"Travaux envisagés : {_labels(TRAVAUX_LABELS, travaux)}")
    lines.append(f"Segment utilisateur : {_label(SEGMENT_LABELS, user.get('segment', ''))}")
    if monument.get("siecle_construction"):
        lines.append(f"Siècle de construction : {monument['siecle_construction']}")
    if monument.get("reference_merimee"):
        lines.append(f"Référence Mérimée : {monument['reference_merimee']}")
    return "\n".join(lines)


async def _llm_evaluate_eligibility(
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
        print("  [LLM] ⚠ MISTRAL_API_KEY absent — évaluation ignorée")
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

    print(f"  [LLM] Appel Mistral pour « {aide_nom} »...")
    try:
        response = await client.chat.complete_async(
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


_LLM_LOG_PATH = Path("/app/llm.txt")


def _llm_log(aide_nom: str, llm_result: dict) -> None:
    """Print LLM result to stdout and append full record to llm.txt."""
    eligible = llm_result.get("eligible")
    explication = llm_result.get("explication", "")
    incertitudes = llm_result.get("incertitudes", [])
    icon = "✓" if eligible else "✗"
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    # stdout (visible in docker logs)
    print(f"  {icon} eligible={eligible} | incertitudes={len(incertitudes)}")
    print(f"     explication : {explication}")
    for inc in incertitudes:
        print(f"     - {inc}")

    # llm.txt (full record, in order)
    try:
        lines = [
            f"\n{'=' * 70}",
            f"[{ts}] {icon} {aide_nom}",
            f"{'=' * 70}",
            f"eligible    : {eligible}",
            f"explication : {explication}",
            "incertitudes :" if incertitudes else "incertitudes : aucune",
        ]
        for inc in incertitudes:
            lines.append(f"  - {inc}")

        with open(_LLM_LOG_PATH, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception as e:
        logger.warning(f"Failed to write llm.txt: {e}")


async def _run_llm_phase(
    eligible_results: list[dict],
    monument_profile: str,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Run LLM evaluation on eligible aides that have conditions_eligibilite_detail.

    Returns (still_eligible, potentially_eligible, downgraded):
    - still_eligible: LLM says eligible AND no incertitudes
    - potentially_eligible: LLM says eligible BUT has incertitudes
    - downgraded: LLM says not eligible
    """
    still_eligible = []
    potentially_eligible = []
    downgraded = []

    # Separate aides with/without conditions for LLM evaluation
    needs_llm = []
    for result in eligible_results:
        conditions = result["aide"].get("conditions_eligibilite_detail")
        if not conditions:
            still_eligible.append(result)
        else:
            needs_llm.append(result)

    # Run all LLM calls in parallel
    if needs_llm:
        llm_results = await asyncio.gather(
            *(
                _llm_evaluate_eligibility(
                    monument_profile=monument_profile,
                    aide_nom=result["aide"].get("nom", ""),
                    conditions_detail=result["aide"]["conditions_eligibilite_detail"],
                    prompt_template=prompt_1,
                )
                for result in needs_llm
            )
        )

        for result, llm_result in zip(needs_llm, llm_results, strict=True):
            aide = result["aide"]
            _llm_log(aide.get("nom", ""), llm_result)

            result["llmEvaluation"] = {
                "explication": llm_result.get("explication", ""),
                "incertitudes": llm_result.get("incertitudes", []),
            }

            llm_eligible = llm_result.get("eligible", True)
            incertitudes = llm_result.get("incertitudes", [])

            # If LLM says ineligible but has incertitudes, it means it's uncertain
            # rather than formally contradicted — treat as potentially eligible
            if not llm_eligible and incertitudes:
                llm_eligible = True

            if llm_eligible:
                if incertitudes:
                    potentially_eligible.append(result)
                else:
                    still_eligible.append(result)
            else:
                result["eligible"] = False
                result["criteresNonRemplis"].append(
                    f"Condition détaillée : {llm_result.get('explication', '')}"
                )
                result["raisonIneligibilite"] = result["raisonIneligibilite"] or llm_result.get(
                    "explication", ""
                )
                downgraded.append(result)

    return still_eligible, potentially_eligible, downgraded


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def run_diagnostic(
    supabase: Client,
    monument: dict,
    user: dict,
    mode_projet: bool = False,
    travaux_filtres: list[str] | None = None,
) -> dict:
    """Run a full diagnostic: SQL pre-filter → criteria check → LLM fine-matching."""
    ctx_travaux = travaux_filtres or []

    print(f"\n{'#' * 60}")
    print(f"# DIAGNOSTIC — {monument.get('nom', 'Monument inconnu')}")
    print(f"{'#' * 60}")
    print(f"  segment      : {_label(SEGMENT_LABELS, user.get('segment'))}")
    print(f"  protection   : {_label(PROTECTION_LABELS, monument.get('protection'))}")
    print(f"  propriétaire : {_label(OWNERSHIP_LABELS, monument.get('proprietaire'))}")
    print(f"  région       : {monument.get('region')}")
    print(f"  département  : {monument.get('departement')}")
    print(
        f"  travaux      : {_labels(TRAVAUX_LABELS, ctx_travaux or monument.get('travaux_envisages') or []) or '—'}"
    )
    print(f"  mode_projet  : {mode_projet}")

    # Phase 1: SQL pre-filter
    print(f"\n{'─' * 60}")
    print("PHASE 1 — Pré-filtre SQL")
    print(f"{'─' * 60}")
    candidate_ids = prefiltrer_aides(supabase, monument, user, ctx_travaux or None)
    print(f"  → {len(candidate_ids)} aide(s) candidate(s) retenue(s) par le SQL")

    # Fetch all aides (candidates + non-candidates) for the full report
    all_aide_ids = [a["id"] for a in (supabase.table("aides_v2").select("id").execute()).data or []]
    non_candidate_ids = [aid for aid in all_aide_ids if aid not in candidate_ids]
    print(f"  → {len(non_candidate_ids)} aide(s) exclue(s) d'emblée sur {len(all_aide_ids)} total")

    # Phase 2: Fetch aides with join data + build criteria
    print(f"\n{'─' * 60}")
    print("PHASE 2 — Vérification des critères Python")
    print(f"{'─' * 60}")
    candidate_aides = fetch_aides_with_joins(supabase, candidate_ids)
    non_candidate_aides = fetch_aides_with_joins(supabase, non_candidate_ids)

    print(f"\n  Candidates SQL ({len(candidate_aides)}) :")
    for a in candidate_aides:
        print(f"    ✓ {a.get('nom_court') or a.get('nom')}")
    print(f"\n  Exclues SQL ({len(non_candidate_aides)}) :")
    for a in non_candidate_aides:
        print(f"    ✗ {a.get('nom_court') or a.get('nom')}")

    # Resolve population for criteria display
    population = None
    code_insee = monument.get("code_insee")
    if code_insee and user.get("segment") == "commune":
        commune_result = (
            supabase.table("communes")
            .select("population")
            .eq("code_insee", code_insee)
            .single()
            .execute()
        )
        if commune_result.data:
            population = commune_result.data.get("population")
            print(f"\n  Population commune : {population} hab.")

    eligible_results = [
        _check_eligibility(a, monument, user, mode_projet, ctx_travaux, population)
        for a in candidate_aides
    ]
    non_eligible_results = [
        _check_eligibility(a, monument, user, mode_projet, ctx_travaux, population)
        for a in non_candidate_aides
    ]

    eligible_after_p2 = [r for r in eligible_results if r["eligible"]]
    ineligible_after_p2 = [r for r in eligible_results if not r["eligible"]]

    print("\n  Résultats critères Python sur les candidates SQL :")
    for r in eligible_after_p2:
        print(f"    ✓ {r['aide'].get('nom_court') or r['aide'].get('nom')}")
    for r in ineligible_after_p2:
        raison = r.get("raisonIneligibilite", "")
        print(f"    ✗ {r['aide'].get('nom_court') or r['aide'].get('nom')} — {raison}")

    non_eligible_results.extend(ineligible_after_p2)
    eligible_results = eligible_after_p2

    print(
        f"\n  → {len(eligible_results)} éligible(s) après phase 2, {len(non_eligible_results)} non éligible(s)"
    )

    # Phase 3: LLM fine-matching on eligible candidates
    print(f"\n{'─' * 60}")
    print(
        f"PHASE 3 — Évaluation LLM ({len(eligible_results)} aide(s) avec conditions_eligibilite_detail)"
    )
    print(f"{'─' * 60}")
    monument_profile = _build_monument_profile(monument, user, population)

    # Write diagnostic header to llm.txt
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    try:
        with open(_LLM_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n\n{'#' * 70}\n")
            f.write(f"# DIAGNOSTIC [{ts}]\n")
            f.write(f"# Monument : {monument.get('nom', '?')}\n")
            f.write(f"# Segment  : {_label(SEGMENT_LABELS, user.get('segment'))}\n")
            f.write(f"{'#' * 70}\n")
    except Exception as e:
        logger.warning(f"Failed to write llm.txt header: {e}")

    still_eligible, potentially_eligible, downgraded = await _run_llm_phase(
        eligible_results, monument_profile
    )
    non_eligible_results.extend(downgraded)

    print("\n  Résultats LLM :")
    for r in still_eligible:
        print(f"    ✓  éligible      — {r['aide'].get('nom_court') or r['aide'].get('nom')}")
    for r in potentially_eligible:
        print(f"    ?  potentiel     — {r['aide'].get('nom_court') or r['aide'].get('nom')}")
    for r in downgraded:
        print(f"    ✗  disqualifié   — {r['aide'].get('nom_court') or r['aide'].get('nom')}")

    montant_total = sum(
        r["aide"].get("montant_max") or 0 for r in still_eligible if r["aide"].get("montant_max")
    )

    print(f"\n{'#' * 60}")
    print("# RÉSULTAT FINAL")
    print(f"#   Éligibles        : {len(still_eligible)}")
    print(f"#   Potentiellement  : {len(potentially_eligible)}")
    print(f"#   Non éligibles    : {len(non_eligible_results)}")
    if montant_total:
        print(f"#   Montant potentiel: {montant_total:,} €")
    print(f"{'#' * 60}\n")

    return {
        "monumentId": monument["id"],
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "totalAidesAnalysees": len(all_aide_ids),
        "aidesEligibles": still_eligible,
        "aidesPotentiellementEligibles": potentially_eligible,
        "aidesNonEligibles": non_eligible_results,
        "montantPotentielTotal": montant_total if montant_total > 0 else None,
    }
