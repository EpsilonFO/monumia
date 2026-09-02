import logging
import traceback
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator
from supabase import Client

from aides_schema import load_all_aides, load_facts, load_pending_facts
from db import get_current_user_id, get_supabase
from eligibility_engine import aide_display_dict, run_deterministic_diagnostic
from routers.monuments import enrich_monument_with_population
from services import stripe_billing as billing
from services.project_access import require_project_access, require_projet_access

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/aides", tags=["aides"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class DeterministicDiagnosticRequest(BaseModel):
    """Cible du diagnostic : un PROJET de travaux, ou (déprécié) un monument.

    Le cadrage (travaux, questionnaire) vit sur le projet depuis l'inversion de
    hiérarchie ; `monument_id` reste accepté pour qu'un onglet SPA non rechargé
    continue d'obtenir un diagnostic (il est alors résolu vers le projet ouvert
    le plus récent du monument).
    """

    projet_id: str | None = None
    monument_id: str | None = None
    # Réponses déjà connues (fact_key → valeur). Optionnel : le front résout
    # aussi les éliminations côté client via eliminationsParOption. Absent
    # (None) = on reprend le questionnaire enregistré du projet.
    answers: dict[str, object] | None = None

    @model_validator(mode="after")
    def _exige_une_cible(self) -> "DeterministicDiagnosticRequest":
        if not self.projet_id and not self.monument_id:
            raise ValueError("projet_id ou monument_id est requis")
        return self


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
    today: date | None = None,
) -> dict:
    """Lance le moteur déterministe et rend le résultat prêt pour le frontend.

    Purement CPU (les YAML sont en cache, ~2 ms par monument) : aucun appel
    réseau, d'où la possibilité de l'exécuter pour tous les projets d'un coup
    dans /dashboard.

    `today` n'est jamais renseigné par les routes — c'est la date du jour qui
    fait foi pour un utilisateur. Il n'existe que pour les outils hors ligne
    (`scripts/rappels_aides.py --today`), où figer la date est le seul moyen de
    vérifier un rappel sans attendre l'échéance : sans lui, la fenêtre de
    candidature de chaque aide resterait calée sur le vrai jour, et le décalage
    ne porterait que sur l'arithmétique des paliers.
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
            today=today,
        )
    except Exception as exc:
        logger.error("run_deterministic_diagnostic crashed:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Erreur moteur déterministe : {exc}") from exc

    result["qcmAnswers"] = answers or {}
    return _camelise_diagnostic(result)


def merge_projet_into_monument(monument: dict, projet: dict | None) -> dict:
    """Contexte du moteur : la fiche du monument + le cadrage de SON projet.

    Le moteur ne connaît pas les projets — `FIELD_REGISTRY` et `build_context`
    lisent `travaux_envisages` sur le monument, comme avant l'inversion de
    hiérarchie. La fusion se fait donc ici, à la frontière : le monument reste
    la source des champs du bien, le projet celle du chantier. Copie, jamais de
    mutation en place : le même monument sert plusieurs projets du dashboard.
    """
    if projet is None:
        return monument
    return {**monument, "travaux_envisages": projet.get("travaux_envisages") or []}


def _latest_open_projet(supabase: Client, monument_id: str) -> dict | None:
    """Projet ouvert le plus récent d'un monument, pour le chemin de compat
    `monument_id` (onglet SPA non rechargé). None si le monument n'en a aucun."""
    result = (
        supabase.table("projets")
        .select("*")
        .eq("monument_id", monument_id)
        .is_("cloture_at", "null")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None


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

    Deux entrées : `projet_id` (le chemin normal, le cadrage vient du projet) et
    `monument_id` seul (compat SPA non rechargée, on retombe sur le projet
    ouvert le plus récent). Le paywall reste clé MONUMENT dans les deux cas.
    """
    if body.projet_id:
        # Accès projet partagé : un collaborateur (membre) doit pouvoir lancer le
        # diagnostic, pas seulement le propriétaire — d'où require_projet_access
        # plutôt qu'un filtre user_id (qui renverrait 404 aux collaborateurs).
        projet, _ = require_projet_access(supabase, body.projet_id, user_id, "member")
        monument_id = projet["monument_id"]
    else:
        monument_id = body.monument_id or ""
        require_project_access(supabase, monument_id, user_id, "member")
        projet = _latest_open_projet(supabase, monument_id)

    monument_result = (
        supabase.table("monuments").select("*").eq("id", monument_id).single().execute()
    )
    if not monument_result.data:
        raise HTTPException(status_code=404, detail="Monument introuvable")
    monument, population = enrich_monument_with_population(supabase, monument_result.data)

    # Remplacement entier, jamais de fusion profonde : le front envoie le
    # questionnaire complet (réponses + clés réservées). `answers` absent =
    # on reprend celui enregistré sur le projet.
    answers = (
        body.answers if body.answers is not None else (projet or {}).get("questionnaire") or {}
    )

    result = deterministic_diagnostic_for(
        merge_projet_into_monument(monument, projet), population, answers
    )
    # Le moteur ne connaît que le monument : on stampe le projet à la frontière,
    # c'est lui qui clé le store de diagnostics et les liens d'échéance du front.
    result["projetId"] = projet["id"] if projet else None

    return redact_diagnostic_if_locked(result, supabase, user_id, monument_id)
