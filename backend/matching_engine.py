"""
Matching engine v2 — uses normalised aides_v2 tables.

Two-phase approach:
  1. SQL pre-filter via prefiltrer_aides() → candidate aide UUIDs
  2. Python builds human-readable criteria match/mismatch lists for the response
"""

from datetime import datetime
from typing import Optional

from supabase import Client

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
    "toiture": "Toiture", "charpente": "Charpente", "couverture": "Couverture",
    "facade": "Façade", "maconnerie": "Maçonnerie", "vitraux": "Vitraux",
    "peintures_murales": "Peintures murales", "menuiserie": "Menuiserie",
    "electricite": "Électricité", "plomberie": "Plomberie", "chauffage": "Chauffage",
    "accessibilite": "Accessibilité", "mise_en_securite": "Mise en sécurité",
    "restauration_generale": "Restauration générale", "etude_prealable": "Étude préalable",
    "mobilier": "Mobilier", "orgues": "Orgues", "parcs_jardins": "Parcs et jardins",
    "protection_solaire": "Protection solaire", "ventilation": "Ventilation",
}

ETAT_LABELS = {
    "bon": "Bon état", "moyen": "État moyen", "mauvais": "Mauvais état", "peril": "En péril",
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

    # Fetch commune population from the communes table
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

    result = supabase.rpc("prefiltrer_aides", {
        "p_protection": monument.get("protection"),
        "p_proprietaire": monument.get("proprietaire"),
        "p_travaux": travaux if travaux else None,
        "p_region": monument.get("region"),
        "p_departement": monument.get("departement"),
        "p_segment": user.get("segment"),
        "p_population": population,
        "p_etat_conservation": monument.get("etat_conservation"),
    }).execute()

    return [row["aide_id"] for row in (result.data or [])]


# ---------------------------------------------------------------------------
# Phase 2: Build human-readable criteria for each aide
# ---------------------------------------------------------------------------

def _fetch_aide_with_joins(supabase: Client, aide_id: str) -> dict:
    """Fetch an aide_v2 row with its join table data."""
    aide = (
        supabase.table("aides_v2")
        .select("*")
        .eq("id", aide_id)
        .single()
        .execute()
    ).data

    if not aide:
        return {}

    # Fetch join tables
    aide["protections"] = [
        r["protection_code"]
        for r in (supabase.table("aides_protections").select("protection_code").eq("aide_id", aide_id).execute()).data or []
    ]
    aide["proprietaires"] = [
        r["proprietaire_code"]
        for r in (supabase.table("aides_proprietaires").select("proprietaire_code").eq("aide_id", aide_id).execute()).data or []
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
        for r in (supabase.table("aides_departements").select("departement_code").eq("aide_id", aide_id).execute()).data or []
    ]
    aide["segments"] = [
        r["segment_code"]
        for r in (supabase.table("aides_segments").select("segment_code").eq("aide_id", aide_id).execute()).data or []
    ]
    aide["etats_conservation"] = [
        r["etat_conservation_code"]
        for r in (supabase.table("aides_etats_conservation").select("etat_conservation_code").eq("aide_id", aide_id).execute()).data or []
    ]

    return aide


def fetch_aides_with_joins(supabase: Client, aide_ids: list[str]) -> list[dict]:
    """Fetch multiple aides with their join data. Batch queries per join table."""
    if not aide_ids:
        return []

    # Fetch all aide rows at once
    aides_result = (
        supabase.table("aides_v2")
        .select("*")
        .in_("id", aide_ids)
        .execute()
    )
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
        travaux_to_check = travaux_filtres if (mode_projet and travaux_filtres) else (monument.get("travaux_envisages") or [])
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
# Main entry point
# ---------------------------------------------------------------------------

def run_diagnostic(
    supabase: Client,
    monument: dict,
    user: dict,
    mode_projet: bool = False,
    travaux_filtres: Optional[list[str]] = None,
) -> dict:
    """Run a full diagnostic: SQL pre-filter → fetch aides with joins → build criteria."""
    ctx_travaux = travaux_filtres or []

    # Phase 1: SQL pre-filter
    candidate_ids = prefiltrer_aides(supabase, monument, user, ctx_travaux or None)

    # Fetch all aides (candidates + non-candidates) for the full report
    all_aide_ids = [
        a["id"]
        for a in (supabase.table("aides_v2").select("id").execute()).data or []
    ]
    non_candidate_ids = [aid for aid in all_aide_ids if aid not in candidate_ids]

    # Phase 2: Fetch aides with join data
    candidate_aides = fetch_aides_with_joins(supabase, candidate_ids)
    non_candidate_aides = fetch_aides_with_joins(supabase, non_candidate_ids)

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

    # Build criteria for all aides
    eligible_results = [
        _check_eligibility(a, monument, user, mode_projet, ctx_travaux, population)
        for a in candidate_aides
    ]
    non_eligible_results = [
        _check_eligibility(a, monument, user, mode_projet, ctx_travaux, population)
        for a in non_candidate_aides
    ]

    montant_total = sum(
        r["aide"].get("montant_max") or 0
        for r in eligible_results
        if r["aide"].get("montant_max")
    )

    return {
        "monumentId": monument["id"],
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "totalAidesAnalysees": len(all_aide_ids),
        "aidesEligibles": eligible_results,
        "aidesNonEligibles": non_eligible_results,
        "montantPotentielTotal": montant_total if montant_total > 0 else None,
    }
