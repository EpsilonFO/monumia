"""
Matching engine — port of frontend/src/lib/matching-engine.ts
Determines which aides a monument/user combination is eligible for.
"""

from datetime import datetime
from typing import Optional


def _check_eligibility(aide: dict, monument: dict, user: dict, mode_projet: bool, travaux_filtres: list[str]) -> dict:
    criteres_remplis: list[str] = []
    criteres_non_remplis: list[str] = []
    c: dict = aide.get("criteres") or {}

    # Protection level
    protection_requise: list = c.get("protectionRequise") or []
    if protection_requise:
        if monument.get("protection") in protection_requise:
            criteres_remplis.append(f"Protection : {monument.get('protection')}")
        else:
            criteres_non_remplis.append(f"Protection requise : {', '.join(protection_requise)}")
    else:
        criteres_remplis.append("Tous niveaux de protection")

    # Owner type
    proprietaire_eligible: list = c.get("proprietaireEligible") or []
    if proprietaire_eligible:
        if monument.get("proprietaire") in proprietaire_eligible:
            criteres_remplis.append(f"Type de propriétaire : {monument.get('proprietaire')}")
        else:
            criteres_non_remplis.append(f"Propriétaire éligible : {', '.join(proprietaire_eligible)}")
    else:
        criteres_remplis.append("Tous types de propriétaires")

    # Work types
    travaux_eligibles: list = c.get("travauxEligibles") or []
    if travaux_eligibles:
        travaux_to_check = travaux_filtres if (mode_projet and travaux_filtres) else (monument.get("travaux_envisages") or [])
        if not travaux_to_check:
            criteres_remplis.append("Types de travaux : non spécifiés (compatible)")
        elif any(t in travaux_eligibles for t in travaux_to_check):
            criteres_remplis.append("Types de travaux compatibles")
        else:
            criteres_non_remplis.append(f"Travaux éligibles : {', '.join(travaux_eligibles)}")
    else:
        criteres_remplis.append("Tous types de travaux")

    # Region
    region_eligible: list = c.get("regionEligible") or []
    if region_eligible:
        if monument.get("region") in region_eligible:
            criteres_remplis.append(f"Région : {monument.get('region')}")
        else:
            criteres_non_remplis.append(f"Région requise : {', '.join(region_eligible)}")
    else:
        criteres_remplis.append("Toute la France")

    # Department
    departement_eligible: list = c.get("departementEligible") or []
    if departement_eligible:
        if monument.get("departement") in departement_eligible:
            criteres_remplis.append(f"Département : {monument.get('departement')}")
        else:
            criteres_non_remplis.append(f"Département requis : {', '.join(departement_eligible)}")

    # User segment
    segment_eligible: list = c.get("segmentEligible") or []
    if segment_eligible:
        if user.get("segment") in segment_eligible:
            criteres_remplis.append(f"Segment : {user.get('segment')}")
        else:
            criteres_non_remplis.append(f"Réservé aux : {', '.join(segment_eligible)}")
    else:
        criteres_remplis.append("Communes et privés")

    # Commune population (flexible threshold)
    max_pop = c.get("communeMaxPopulation") or (10000 if c.get("communeDeMoins10000Hab") else None)
    if max_pop is not None:
        commune_profile = user.get("commune") or {}
        population = commune_profile.get("population", 0)
        if user.get("segment") == "commune" and population and population < max_pop:
            criteres_remplis.append(f"Commune < {max_pop:,} hab. ({population} hab.)")
        elif user.get("segment") == "commune" and population and population >= max_pop:
            criteres_non_remplis.append(f"Réservé aux communes < {max_pop:,} hab.")
        elif user.get("segment") != "commune" and c.get("communeDeMoins10000Hab"):
            criteres_non_remplis.append("Réservé aux communes")

    # Conservation state
    etat_requis: list = c.get("etatConservationRequis") or []
    if etat_requis:
        etat = monument.get("etat_conservation")
        if etat in etat_requis:
            criteres_remplis.append(f"État de conservation : {etat}")
        else:
            criteres_non_remplis.append(f"État requis : {', '.join(etat_requis)}")

    eligible = len(criteres_non_remplis) == 0

    return {
        "aide": aide,
        "eligible": eligible,
        "criteresRemplis": criteres_remplis,
        "criteresNonRemplis": criteres_non_remplis,
        "raisonIneligibilite": criteres_non_remplis[0] if not eligible else None,
    }


def run_diagnostic(
    monument: dict,
    user: dict,
    aides: list[dict],
    mode_projet: bool = False,
    travaux_filtres: Optional[list[str]] = None,
) -> dict:
    ctx_travaux = travaux_filtres or []
    results = [_check_eligibility(a, monument, user, mode_projet, ctx_travaux) for a in aides]

    aides_eligibles = [r for r in results if r["eligible"]]
    aides_non_eligibles = [r for r in results if not r["eligible"]]

    montant_total = sum(
        r["aide"]["montantMax"]
        for r in aides_eligibles
        if r["aide"].get("montantMax")
    )

    return {
        "monumentId": monument["id"],
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "totalAidesAnalysees": len(aides),
        "aidesEligibles": aides_eligibles,
        "aidesNonEligibles": aides_non_eligibles,
        "montantPotentielTotal": montant_total if montant_total > 0 else None,
    }
