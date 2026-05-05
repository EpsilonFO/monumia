"""
Matching engine v2 — uses normalised aides_v2 tables.

Three-phase approach:
  1. SQL pre-filter via prefiltrer_aides() → candidate aide UUIDs (source of truth for eligibility)
  2. Python builds human-readable criteria labels for display (does NOT re-check eligibility)
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

from prompts.matching import render_prompt_eligibility, render_prompt_qcm

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

REGION_LABELS = {
    "auvergne-rhone-alpes": "Auvergne-Rhône-Alpes",
    "bourgogne-franche-comte": "Bourgogne-Franche-Comté",
    "bretagne": "Bretagne",
    "centre-val-de-loire": "Centre-Val de Loire",
    "corse": "Corse",
    "grand-est": "Grand Est",
    "hauts-de-france": "Hauts-de-France",
    "ile-de-france": "Île-de-France",
    "normandie": "Normandie",
    "nouvelle-aquitaine": "Nouvelle-Aquitaine",
    "occitanie": "Occitanie",
    "pays-de-la-loire": "Pays de la Loire",
    "provence-alpes-cote-d-azur": "Provence-Alpes-Côte d'Azur",
    "guadeloupe": "Guadeloupe",
    "martinique": "Martinique",
    "guyane": "Guyane",
    "la-reunion": "La Réunion",
    "mayotte": "Mayotte",
}

# INSEE department codes → libellé. Used to humanise filter labels;
# `aides_departements.departement_code` and `communes.departement_num`
# both store the code form (e.g. "75", "2A", "971").
DEPARTEMENT_LABELS = {
    "01": "Ain",
    "02": "Aisne",
    "03": "Allier",
    "04": "Alpes-de-Haute-Provence",
    "05": "Hautes-Alpes",
    "06": "Alpes-Maritimes",
    "07": "Ardèche",
    "08": "Ardennes",
    "09": "Ariège",
    "10": "Aube",
    "11": "Aude",
    "12": "Aveyron",
    "13": "Bouches-du-Rhône",
    "14": "Calvados",
    "15": "Cantal",
    "16": "Charente",
    "17": "Charente-Maritime",
    "18": "Cher",
    "19": "Corrèze",
    "2A": "Corse-du-Sud",
    "2B": "Haute-Corse",
    "21": "Côte-d'Or",
    "22": "Côtes-d'Armor",
    "23": "Creuse",
    "24": "Dordogne",
    "25": "Doubs",
    "26": "Drôme",
    "27": "Eure",
    "28": "Eure-et-Loir",
    "29": "Finistère",
    "30": "Gard",
    "31": "Haute-Garonne",
    "32": "Gers",
    "33": "Gironde",
    "34": "Hérault",
    "35": "Ille-et-Vilaine",
    "36": "Indre",
    "37": "Indre-et-Loire",
    "38": "Isère",
    "39": "Jura",
    "40": "Landes",
    "41": "Loir-et-Cher",
    "42": "Loire",
    "43": "Haute-Loire",
    "44": "Loire-Atlantique",
    "45": "Loiret",
    "46": "Lot",
    "47": "Lot-et-Garonne",
    "48": "Lozère",
    "49": "Maine-et-Loire",
    "50": "Manche",
    "51": "Marne",
    "52": "Haute-Marne",
    "53": "Mayenne",
    "54": "Meurthe-et-Moselle",
    "55": "Meuse",
    "56": "Morbihan",
    "57": "Moselle",
    "58": "Nièvre",
    "59": "Nord",
    "60": "Oise",
    "61": "Orne",
    "62": "Pas-de-Calais",
    "63": "Puy-de-Dôme",
    "64": "Pyrénées-Atlantiques",
    "65": "Hautes-Pyrénées",
    "66": "Pyrénées-Orientales",
    "67": "Bas-Rhin",
    "68": "Haut-Rhin",
    "69": "Rhône",
    "70": "Haute-Saône",
    "71": "Saône-et-Loire",
    "72": "Sarthe",
    "73": "Savoie",
    "74": "Haute-Savoie",
    "75": "Paris",
    "76": "Seine-Maritime",
    "77": "Seine-et-Marne",
    "78": "Yvelines",
    "79": "Deux-Sèvres",
    "80": "Somme",
    "81": "Tarn",
    "82": "Tarn-et-Garonne",
    "83": "Var",
    "84": "Vaucluse",
    "85": "Vendée",
    "86": "Vienne",
    "87": "Haute-Vienne",
    "88": "Vosges",
    "89": "Yonne",
    "90": "Territoire de Belfort",
    "91": "Essonne",
    "92": "Hauts-de-Seine",
    "93": "Seine-Saint-Denis",
    "94": "Val-de-Marne",
    "95": "Val-d'Oise",
    "971": "Guadeloupe",
    "972": "Martinique",
    "973": "Guyane",
    "974": "La Réunion",
    "976": "Mayotte",
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

    # Department code: prefer the value enriched from communes (`departement_num`),
    # fall back to extracting it from code_insee (handles Corsica 2A/2B and DOM
    # codes 971–976) when the monument hasn't been enriched yet.
    departement_code = monument.get("departement_num")
    if not departement_code and code_insee:
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
    logger.debug(
        "[SQL] RPC prefiltrer_aides → params: %s",
        json.dumps(params, ensure_ascii=False, default=str),
    )

    result = supabase.rpc("prefiltrer_aides", params).execute()

    return [row["aide_id"] for row in (result.data or [])]


# ---------------------------------------------------------------------------
# Phase 2: Build human-readable criteria labels (display only, no re-filtering)
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


def _build_criteria_labels(
    aide: dict,
    monument: dict,
    user: dict,
    mode_projet: bool,
    travaux_filtres: list[str],
    population: int | None = None,
) -> dict:
    """Build human-readable criteria match/mismatch lists for a single aide.

    This does NOT determine eligibility — that is done by the SQL pre-filter.
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
            criteres_remplis.append(f"Région : {_label(REGION_LABELS, monument.get('region'))}")
        else:
            criteres_non_remplis.append(f"Région requise : {_labels(REGION_LABELS, regions)}")
    else:
        criteres_remplis.append("Toute la France")

    # Département : compare on the numeric INSEE code (matches aides_departements.departement_code).
    # `monument["departement"]` holds the human label (e.g. "Paris") for display only.
    departements = aide.get("departements") or []
    if departements:
        dep_code = monument.get("departement_num")
        if dep_code and dep_code in departements:
            criteres_remplis.append(
                f"Département : {monument.get('departement') or _label(DEPARTEMENT_LABELS, dep_code)} ({dep_code})"
            )
        else:
            criteres_non_remplis.append(
                f"Département requis : {_labels(DEPARTEMENT_LABELS, departements)}"
            )

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
    dep_label = monument.get("departement") or _label(
        DEPARTEMENT_LABELS, monument.get("departement_num")
    )
    dep_num = monument.get("departement_num")
    if dep_label and dep_num:
        lines.append(f"Département : {dep_label} ({dep_num})")
    else:
        lines.append(f"Département : {dep_label or dep_num or 'Non renseigné'}")
    region_display = monument.get("region_label") or _label(REGION_LABELS, monument.get("region"))
    lines.append(f"Région : {region_display or 'Non renseigné'}")
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
    prompt: str,
    aide_nom: str,
) -> dict:
    """Call Mistral to evaluate fine eligibility with a rendered prompt.

    Returns {"eligible": bool, "explication": str, "incertitudes": list[str]}
    """
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        logger.warning("[LLM] MISTRAL_API_KEY absent — évaluation ignorée")
        return {
            "eligible": True,
            "explication": "",
            "incertitudes": ["Évaluation LLM indisponible"],
        }

    client = Mistral(api_key=api_key)

    logger.info("[LLM] Appel Mistral pour « %s »...", aide_nom)
    last_error = None
    for attempt in range(3):
        try:
            response = await client.chat.complete_async(
                model="mistral-medium-latest",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            choice = response.choices[0]
            content = choice.message.content
            result = json.loads(content)
            return result
        except Exception as e:
            last_error = e
            if attempt < 2:
                wait = 2**attempt
                logger.warning(
                    "[LLM] Tentative %d/3 échouée pour « %s » (%s), retry dans %ds",
                    attempt + 1,
                    aide_nom,
                    e,
                    wait,
                )
                await asyncio.sleep(wait)
    logger.error(f"LLM evaluation failed for aide '{aide_nom}' after 3 attempts: {last_error}")
    return {
        "eligible": True,
        "explication": "",
        "incertitudes": [f"Erreur LLM : {last_error}"],
    }


_LLM_LOG_PATH = Path("/app/llm.txt")


def _llm_log(aide_nom: str, llm_result: dict) -> None:
    """Log LLM result and append full record to llm.txt."""
    eligible = llm_result.get("eligible")
    explication = llm_result.get("explication", "")
    incertitudes = llm_result.get("incertitudes", [])
    icon = "✓" if eligible else "✗"
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    # stdout (visible in docker logs)
    logger.info("%s eligible=%s | incertitudes=%d", icon, eligible, len(incertitudes))
    logger.info("   explication : %s", explication)
    for inc in incertitudes:
        logger.info("   - %s", inc)

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
                    prompt=render_prompt_eligibility(
                        monument_profile=monument_profile,
                        aide_nom=result["aide"].get("nom", ""),
                        conditions_detail=result["aide"]["conditions_eligibilite_detail"],
                    ),
                    aide_nom=result["aide"].get("nom", ""),
                )
                for result in needs_llm
            )
        )

        for result, llm_result in zip(needs_llm, llm_results, strict=True):
            aide = result["aide"]
            _llm_log(aide.get("nom", ""), llm_result)

            # Normalise on the way in: the frontend matches QCM answers to
            # incertitudes by exact category equality, so the categories stored
            # here MUST be drawn from the same closed set used during QCM
            # aggregation. Anything unknown is coerced to "autre".
            result["llmEvaluation"] = {
                "explication": llm_result.get("explication", ""),
                "incertitudes": [
                    _normalize_incertitude(inc) for inc in (llm_result.get("incertitudes") or [])
                ],
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
# Phase 4: Generate QCM questions from incertitudes
# ---------------------------------------------------------------------------

MAX_QCM_QUESTIONS = 50


# Closed set of allowed incertitude categories. MUST match the identifiers
# listed in prompts/eligibility.j2 — any drift causes the LLM-emitted category
# to be coerced to "autre", which in turn breaks the QCM ↔ incertitude matching
# (the frontend marks an incertitude as clarified by exact category equality).
ALLOWED_INCERTITUDE_CATEGORIES = {
    # Procédure et antériorité
    "non_commencement_travaux",
    "accord_abf_prealable",
    "convention_drac",
    "demande_autorisation_urbanisme",
    "delai_realisation_post_accord",
    # Intervenants et qualifications
    "architecte_mh_acmh",
    "artisan_rge",
    "qualification_specifique",
    # Diagnostics et études
    "diagnostic_prealable",
    "dpe_audit_energetique",
    "gain_energetique_minimum",
    "etude_impact_patrimonial",
    # Ouverture, usage et destination
    "ouverture_public",
    "usage_batiment",
    "residence_principale",
    "usage_non_lucratif",
    "anciennete_batiment",
    # Engagements et durée
    "engagement_conservation",
    "engagement_location",
    "engagement_ouverture_public",
    "maintien_activite",
    # Conditions financières
    "revenus_plafond",
    "montant_minimum_projet",
    "cumul_aides_plafond",
    "cofinancement_requis",
    "regime_fiscal",
    # Garanties et assurances
    "assurance_garantie",
    # Critères sociaux et territoriaux
    "emploi_insertion",
    "formation_apprentissage",
    "accessibilite_pmr_erp",
    "territoire_specifique",
    "impact_territorial",
    # Innovation et partenariats
    "innovation_saut_techno",
    "partenariat_consortium",
    # Autres
    "label_certification_prealable",
    "autre",
}


def _normalize_incertitude(inc: str | dict) -> dict:
    """Normalise an incertitude to {categorie, detail} format.

    - Legacy plain-string → wrapped under "autre".
    - Dict with unknown category → coerced to "autre" (logs a warning).
    """
    if isinstance(inc, dict) and "categorie" in inc:
        cat = str(inc.get("categorie") or "").strip().lower()
        if cat not in ALLOWED_INCERTITUDE_CATEGORIES:
            logger.warning("[LLM] Catégorie inconnue « %s » remappée vers « autre »", cat)
            return {"categorie": "autre", "detail": inc.get("detail", "")}
        return {"categorie": cat, "detail": inc.get("detail", "")}
    # Legacy plain-string fallback
    text = inc if isinstance(inc, str) else str(inc)
    return {"categorie": "autre", "detail": text}


def _aggregate_incertitudes(eligible_results: list[dict]) -> list[dict]:
    """Aggregate incertitudes by category across all aides.

    Returns a compact list grouped by category, each with the set of aide IDs
    and a representative detail string. This reduces hundreds of raw incertitudes
    down to ~10 category groups.
    """
    from collections import defaultdict

    # category → {aideIds: set, details: list[str]}
    groups: dict[str, dict] = defaultdict(
        lambda: {"aideIds": set(), "aideNoms": set(), "details": []}
    )

    for result in eligible_results:
        llm_eval = result.get("llmEvaluation")
        if not llm_eval:
            continue
        aide_id = result["aide"]["id"]
        aide_nom = result["aide"].get("nom_court") or result["aide"].get("nom", "")
        for inc in llm_eval.get("incertitudes", []):
            normalized = _normalize_incertitude(inc)
            cat = normalized["categorie"]
            detail = normalized["detail"]
            groups[cat]["aideIds"].add(aide_id)
            groups[cat]["aideNoms"].add(aide_nom)
            # Keep unique details only (avoid near-duplicates flooding context)
            if detail not in groups[cat]["details"]:
                groups[cat]["details"].append(detail)

    # Convert to serialisable list, sorted by number of aides impacted (most first).
    # Keep payload compact to avoid LLM timeouts on large diagnostics:
    # - drop aideNoms (not needed by LLM — aideIds are enough for tracking)
    # - cap details to 3 representative ones
    # - truncate very long detail strings
    aggregated = []
    for cat, data in sorted(groups.items(), key=lambda x: len(x[1]["aideIds"]), reverse=True):
        details_truncated = [d[:200] for d in data["details"][:3]]
        aggregated.append(
            {
                "categorie": cat,
                "aideIds": sorted(data["aideIds"]),
                "nbAides": len(data["aideIds"]),
                "details": details_truncated,
            }
        )

    return aggregated


def _compact_for_llm(aggregated: list[dict]) -> list[dict]:
    """Strip aideIds before sending to LLM — we remap them back post-response via categorie."""
    return [
        {"categorie": g["categorie"], "nbAides": g["nbAides"], "details": g["details"]}
        for g in aggregated
    ]


async def generate_qcm_questions(
    eligible_results: list[dict],
    monument_profile: str = "",
) -> list[dict]:
    """Collect incertitudes from eligible aides, aggregate by category, and generate QCM."""
    aggregated = _aggregate_incertitudes(eligible_results)

    if not aggregated:
        return []

    total_raw = sum(
        len(inc)
        for r in eligible_results
        if (e := r.get("llmEvaluation"))
        for inc in [e.get("incertitudes", [])]
    )

    logger.info("─" * 60)
    logger.info(
        "PHASE 4 — Génération QCM (%d incertitude(s) brutes → %d catégorie(s) agrégée(s))",
        total_raw,
        len(aggregated),
    )
    for g in aggregated:
        logger.info("  • %s — %d aide(s) : %s", g["categorie"], g["nbAides"], g["details"][0][:80])
    logger.info("─" * 60)

    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        logger.warning("MISTRAL_API_KEY not set, skipping QCM generation")
        return []

    client = Mistral(api_key=api_key)

    # Build a compact payload (no aideIds) for the LLM — we remap them from categorie after.
    compact_payload = _compact_for_llm(aggregated)
    aide_ids_by_category = {g["categorie"]: g["aideIds"] for g in aggregated}

    prompt = render_prompt_qcm(
        max_questions=MAX_QCM_QUESTIONS,
        monument_profile=monument_profile,
        incertitudes_json=json.dumps(compact_payload, ensure_ascii=False, indent=2),
    )
    logger.info("[QCM] Prompt construit (%d caractères), appel Mistral...", len(prompt))

    QCM_TIMEOUT_S = 90
    last_error = None
    for attempt in range(3):
        try:
            logger.info("[QCM] Tentative %d/3 (timeout %ds)...", attempt + 1, QCM_TIMEOUT_S)
            response = await asyncio.wait_for(
                client.chat.complete_async(
                    model="mistral-large-latest",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                ),
                timeout=QCM_TIMEOUT_S,
            )
            content = response.choices[0].message.content
            logger.info("[QCM] Réponse reçue (%d caractères)", len(content or ""))
            parsed = json.loads(content)
            raw_questions = parsed.get("questions", [])

            # Remap aideIds from categorie (we stripped them from the prompt to save tokens).
            questions = []
            for q in raw_questions:
                if not isinstance(q, dict):
                    continue
                cat = q.get("categorie")
                mapped_ids = aide_ids_by_category.get(cat, [])
                if not mapped_ids:
                    logger.warning(
                        "[QCM] Question ignorée: catégorie « %s » inconnue ou sans aides", cat
                    )
                    continue
                q["aideIds"] = mapped_ids
                q.setdefault("eliminatingOptionIds", [])
                questions.append(q)

            # Sanitize questions: ensure required fields and valid structure
            questions = []
            for q in raw_questions:
                if not isinstance(q, dict):
                    continue
                qid = q.get("id")
                qtext = q.get("question")
                options = q.get("options")
                aide_ids = q.get("aideIds")
                if not (qid and qtext and isinstance(options, list) and isinstance(aide_ids, list)):
                    logger.warning("[QCM] Question malformée ignorée: %s", q)
                    continue
                # Ensure eliminatingOptionIds exists
                q.setdefault("eliminatingOptionIds", [])
                # Ensure eliminationsParOption is a dict if present
                if "eliminationsParOption" in q and not isinstance(
                    q["eliminationsParOption"], dict
                ):
                    q["eliminationsParOption"] = {}
                questions.append(q)

            logger.info(
                "→ %d question(s) QCM générée(s) (brut: %d, filtrées: %d)",
                len(questions),
                len(raw_questions),
                len(raw_questions) - len(questions),
            )
            for q in questions:
                logger.info(
                    "  ? [%s] %s (%d aide(s))",
                    q.get("categorie", "?"),
                    (q.get("question") or "")[:80],
                    len(q.get("aideIds", [])),
                )

            return questions
        except TimeoutError as e:
            last_error = e
            logger.warning("[QCM] Tentative %d/3 timeout après %ds", attempt + 1, QCM_TIMEOUT_S)
            if attempt < 2:
                await asyncio.sleep(2**attempt)
        except Exception as e:
            last_error = e
            if attempt < 2:
                wait = 2**attempt
                logger.warning(
                    "[QCM] Tentative %d/3 échouée (%s), retry dans %ds", attempt + 1, e, wait
                )
                await asyncio.sleep(wait)
    logger.error(f"QCM generation failed after 3 attempts: {last_error}")
    return []


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

    logger.info("#" * 60)
    logger.info("# DIAGNOSTIC — %s", monument.get("nom", "Monument inconnu"))
    logger.info("#" * 60)
    logger.info("  segment      : %s", _label(SEGMENT_LABELS, user.get("segment")))
    logger.info("  protection   : %s", _label(PROTECTION_LABELS, monument.get("protection")))
    logger.info("  propriétaire : %s", _label(OWNERSHIP_LABELS, monument.get("proprietaire")))
    logger.info(
        "  région       : %s (%s)",
        _label(REGION_LABELS, monument.get("region")),
        monument.get("region"),
    )
    logger.info(
        "  département  : %s (%s)",
        monument.get("departement"),
        monument.get("departement_num"),
    )
    logger.info(
        "  travaux      : %s",
        _labels(TRAVAUX_LABELS, ctx_travaux or monument.get("travaux_envisages") or []) or "—",
    )
    logger.info("  mode_projet  : %s", mode_projet)

    # Phase 1: SQL pre-filter
    logger.info("─" * 60)
    logger.info("PHASE 1 — Pré-filtre SQL")
    logger.info("─" * 60)
    candidate_ids = prefiltrer_aides(supabase, monument, user, ctx_travaux or None)
    logger.info("→ %d aide(s) candidate(s) retenue(s) par le SQL", len(candidate_ids))

    # Fetch all aides (candidates + non-candidates) for the full report
    all_aide_ids = [a["id"] for a in (supabase.table("aides_v2").select("id").execute()).data or []]
    non_candidate_ids = [aid for aid in all_aide_ids if aid not in candidate_ids]
    logger.info(
        "→ %d aide(s) exclue(s) d'emblée sur %d total", len(non_candidate_ids), len(all_aide_ids)
    )

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

    # Candidates from SQL are eligible — just build labels for display
    eligible_results = [
        _build_criteria_labels(a, monument, user, mode_projet, ctx_travaux, population)
        for a in candidate_aides
    ]
    for r in eligible_results:
        r["eligible"] = True

    # Non-candidates are ineligible — build labels to show why
    non_eligible_results = [
        _build_criteria_labels(a, monument, user, mode_projet, ctx_travaux, population)
        for a in non_candidate_aides
    ]
    for r in non_eligible_results:
        r["eligible"] = False

    # Phase 3: LLM fine-matching on eligible candidates
    logger.info("─" * 60)
    logger.info(
        "PHASE 2 — Évaluation LLM (%d aide(s) avec conditions_eligibilite_detail)",
        len(eligible_results),
    )
    logger.info("─" * 60)
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

    logger.info("Résultats LLM :")
    for r in still_eligible:
        logger.info("  ✓  éligible      — %s", r["aide"].get("nom_court") or r["aide"].get("nom"))
    for r in potentially_eligible:
        logger.info("  ?  potentiel     — %s", r["aide"].get("nom_court") or r["aide"].get("nom"))
    for r in downgraded:
        logger.info("  ✗  disqualifié   — %s", r["aide"].get("nom_court") or r["aide"].get("nom"))

    montant_total = sum(
        r["aide"].get("montant_max") or 0 for r in still_eligible if r["aide"].get("montant_max")
    )

    logger.info("#" * 60)
    logger.info("# RÉSULTAT FINAL")
    logger.info("#   Éligibles        : %d", len(still_eligible))
    logger.info("#   Potentiellement  : %d", len(potentially_eligible))
    logger.info("#   Non éligibles    : %d", len(non_eligible_results))
    if montant_total:
        logger.info("#   Montant potentiel: %s €", f"{montant_total:,}")
    logger.info("#" * 60)

    # Phase 4: Generate QCM questions from incertitudes
    qcm_questions = []
    all_with_incertitudes = still_eligible + potentially_eligible
    if all_with_incertitudes:
        qcm_questions = await generate_qcm_questions(all_with_incertitudes, monument_profile)

    return {
        "monumentId": monument["id"],
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "totalAidesAnalysees": len(all_aide_ids),
        "aidesEligibles": still_eligible,
        "aidesPotentiellementEligibles": potentially_eligible,
        "aidesNonEligibles": non_eligible_results,
        "montantPotentielTotal": montant_total if montant_total > 0 else None,
        "qcmQuestions": qcm_questions,
    }
