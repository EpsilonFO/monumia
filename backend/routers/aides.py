import logging
import traceback
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import Client

from aides_schema import load_all_aides, load_facts, load_pending_facts
from db import get_current_user_id, get_supabase
from eligibility_engine import aide_display_dict, run_deterministic_diagnostic
from routers.monuments import enrich_monument_with_population
from services import stripe_billing as billing
from services.project_access import require_project_access

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/aides", tags=["aides"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class DeterministicDiagnosticRequest(BaseModel):
    monument_id: str
    # Réponses déjà connues (fact_key → valeur). Optionnel : le front résout
    # aussi les éliminations côté client via eliminationsParOption.
    answers: dict[str, object] | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Map DB snake_case columns → frontend camelCase keys
_AIDE_KEY_MAP = {
    "nom_court": "nomCourt",
    "description_longue": "descriptionLongue",
    "montant_max": "montantMax",
    "taux_max": "tauxMax",
    "montant_min": "montantMin",
    "commune_max_population": "communeMaxPopulation",
    "cofinancement_requis": "cofinancementRequis",
    "architecte_requis": "architecteRequis",
    "conditions_eligibilite_detail": "conditionsEligibiliteDetail",
    "demarche_description": "demarcheDescription",
    "documents_requis": "documentsRequis",
    "delai_instruction": "delaiInstruction",
    "date_ouverture": "dateOuverture",
    "date_limite": "dateLimite",
    "url_officielle": "urlOfficielle",
    "formulaire_url": "formulaireUrl",
    "base_ttc": "baseTTC",
    "created_at": "createdAt",
    "updated_at": "updatedAt",
}


def _to_camel(aide: dict) -> dict:
    """Convert a DB aide row (snake_case) to frontend shape (camelCase)."""
    out = {}
    for k, v in aide.items():
        out[_AIDE_KEY_MAP.get(k, k)] = v
    return out


_DIAGNOSTIC_BUCKETS = (
    "aidesEligibles",
    "aidesPotentiellementEligibles",
    "aidesAtteignables",
    "aidesNonEligibles",
)


def _camelise_diagnostic(result: dict) -> dict:
    """Convert aide objects inside diagnostic results to camelCase."""
    for bucket in _DIAGNOSTIC_BUCKETS:
        for match in result.get(bucket, []):
            match["aide"] = _to_camel(match["aide"])
    return result


# Ce que voit un projet non débloqué. Le libellé remplace le nom de l'aide dans
# l'échéancier, où il n'est pas flouté : il doit rester présentable.
LOCKED_AIDE_LABEL = "Aide masquée"

# Champs retirés d'une aide non débloquée. Le montant, le taux, la catégorie et
# la date limite RESTENT visibles : c'est tout l'argumentaire de vente, montrer
# ce qu'il y a à gagner sans dire où le demander. Ce qui part, c'est ce qu'on
# vend — l'identité du financeur et le moyen de le contacter.
_REDACTED_AIDE_FIELDS = (
    "organisme",
    "urlOfficielle",
    "formulaireUrl",
    "contact",
    "contactEmail",
    "contactTelephone",
    "documentsRequis",
    "procedure",
    "conditions",
)


def redact_locked_aide(aide: dict) -> dict:
    """Anonymise une aide dont le projet n'est pas débloqué.

    Le floutage CSS côté navigateur ne cache rien : le nom part quand même dans
    la réponse HTTP, et l'onglet Réseau des devtools suffit à le lire. La seule
    frontière qui tienne est ici, côté serveur.

    L'`id` est conservé : il sert de clé de rendu, et ne révèle rien à lui seul —
    la fiche complète d'une aide, elle, reste derrière son propre contrôle.
    """
    aide["nom"] = LOCKED_AIDE_LABEL
    aide["nomCourt"] = LOCKED_AIDE_LABEL
    aide["description"] = "Débloquez ce projet pour voir de quelle aide il s'agit."
    for field in _REDACTED_AIDE_FIELDS:
        if field in aide:
            aide[field] = None
    aide["locked"] = True
    return aide


def redact_diagnostic_if_locked(
    result: dict, supabase: Client, user_id: str, monument_id: str
) -> dict:
    """Applique la redaction à tout un diagnostic si le projet n'est pas payé."""
    if billing.has_monument_access(supabase, user_id, monument_id):
        return result
    for bucket in _DIAGNOSTIC_BUCKETS:
        for match in result.get(bucket, []):
            match["aide"] = redact_locked_aide(match["aide"])
    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


@router.get("/{aide_id}")
def get_aide(
    aide_id: str,
    supabase: Client = Depends(get_supabase),
):
    """Récupère une aide par id.

    Le moteur déterministe identifie les aides par leur slug (il lit les YAML,
    pas la base). Donc `aide_id` peut être un UUID (aide en base) ou un slug
    (aide servie depuis les YAML). On résout dans cet ordre : UUID en base,
    puis YAML par slug — la même source que le diagnostic, donc l'affichage
    reste cohérent même si le loader n'a pas (encore) poussé l'aide en base.
    """
    if _is_uuid(aide_id):
        result = supabase.table("aides_v3").select("*").eq("id", aide_id).maybe_single().execute()
        if result and result.data:
            return _to_camel(result.data)

    aide = load_all_aides().get(aide_id)
    if aide:
        return _to_camel(aide_display_dict(aide))

    raise HTTPException(status_code=404, detail="Aide introuvable")


def deterministic_diagnostic_for(
    monument: dict,
    population: int | None,
    answers: dict[str, object] | None,
) -> dict:
    """Lance le moteur déterministe et rend le résultat prêt pour le frontend.

    Purement CPU (les YAML sont en cache, ~2 ms par monument) : aucun appel
    réseau, d'où la possibilité de l'exécuter pour tous les projets d'un coup
    dans /dashboard.
    """
    aides = load_all_aides()
    facts = {**load_facts(), **load_pending_facts()}

    try:
        result = run_deterministic_diagnostic(
            aides=aides,
            facts=facts,
            monument=monument,
            population=population,
            answers=answers,
        )
    except Exception as exc:
        logger.error("run_deterministic_diagnostic crashed:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Erreur moteur déterministe : {exc}") from exc

    result["qcmAnswers"] = answers or {}
    return _camelise_diagnostic(result)


@router.post("/diagnostic-deterministe")
def diagnostic_deterministe(
    body: DeterministicDiagnosticRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """Diagnostic 100 % déterministe (aucun LLM), sur les aides « engine-ready »
    (zéro condition untyped), conditions lues depuis les YAML typés.

    Non persisté (les aideIds sont des slugs, pas des UUID) : le résultat est
    rendu directement, le QCM se résout côté client via eliminationsParOption.
    """
    # Accès projet partagé : un collaborateur (membre) doit pouvoir lancer le
    # diagnostic, pas seulement le propriétaire — d'où require_project_access
    # plutôt qu'un filtre user_id (qui renverrait 404 aux collaborateurs).
    require_project_access(supabase, body.monument_id, user_id, "member")
    monument_result = (
        supabase.table("monuments").select("*").eq("id", body.monument_id).single().execute()
    )
    if not monument_result.data:
        raise HTTPException(status_code=404, detail="Monument introuvable")
    monument, population = enrich_monument_with_population(supabase, monument_result.data)

    return redact_diagnostic_if_locked(
        deterministic_diagnostic_for(monument, population, body.answers),
        supabase,
        user_id,
        body.monument_id,
    )
