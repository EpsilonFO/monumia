import logging
import traceback
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator
from supabase import Client

from aides_schema import load_all_aides, load_facts, load_pending_facts
from db import get_current_user_id, get_supabase
from eligibility_engine import aide_display_dict, run_deterministic_diagnostic
from eligibility_engine import disponibilite as aide_disponibilite
from routers.monuments import enrich_monument_with_population
from services import quotas
from services import stripe_billing as billing
from services.offres import Offre
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


# Ce que voit une aide caviardée. Le libellé remplace le nom de l'aide dans
# l'échéancier, où il n'est pas flouté : il doit rester présentable.
LOCKED_AIDE_LABEL = "Aide masquée"

# Champs retirés d'une aide caviardée. Le montant, le taux, la catégorie et la
# date limite RESTENT visibles : c'est tout l'argumentaire de vente, montrer ce
# qu'il y a à gagner sans dire où le demander. Ce qui part, c'est ce qu'on
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
    """Anonymise une aide que l'offre du compte ne montre pas encore.

    Le floutage CSS côté navigateur ne cache rien : le nom part quand même dans
    la réponse HTTP, et l'onglet Réseau des devtools suffit à le lire. La seule
    frontière qui tienne est ici, côté serveur.

    L'`id` est conservé : c'est le slug, il sert de clé de rendu et de clé de
    corrélation avec les dossiers et les suivis déjà ouverts sur cette aide. Il
    reste donc devinable — d'où le contrôle posé aussi sur GET /aides/{id}, qui
    est le seul chemin menant à la fiche complète.
    """
    aide["nom"] = LOCKED_AIDE_LABEL
    aide["nomCourt"] = LOCKED_AIDE_LABEL
    aide["description"] = "Passez à l'offre Veille pour voir de quelle aide il s'agit."
    for field in _REDACTED_AIDE_FIELDS:
        if field in aide:
            aide[field] = None
    aide["locked"] = True
    return aide


# Les trois seaux « à portée ». Ce sont eux, et eux seuls, que le front répartit
# entre « disponibles maintenant » et « disponibles bientôt » : une aide non
# éligible reste dans sa propre section quelle que soit sa fenêtre de dépôt, et
# la caviarder n'aurait aucun sens (il n'y a rien à y vendre).
_BUCKETS_A_PORTEE = ("aidesEligibles", "aidesPotentiellementEligibles", "aidesAtteignables")


def redact_bientot_hors_offre(result: dict, offre: Offre) -> dict:
    """Caviarde les aides « Disponibles bientôt » que l'offre ne couvre pas.

    C'est le seul paywall qui reste sur les aides : leur détail est gratuit dès
    lors que le guichet est ouvert. Ce que l'offre Veille vend, c'est de savoir
    à l'AVANCE quelle aide va ouvrir — et de recevoir l'email le jour où elle
    ouvre.
    """
    if offre.aides_bientot:
        return result
    for bucket in _BUCKETS_A_PORTEE:
        for match in result.get(bucket, []):
            if match.get("disponibilite") == "bientot":
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


def _slug_aide_a_venir(slug: str | None) -> bool:
    """Cette aide attend-elle l'ouverture (ou la réouverture) de son guichet ?

    Lu dans les YAML, la même source que le diagnostic : les deux doivent
    classer une aide dans le même seau, sinon la fiche s'ouvre sur une aide que
    la liste annonçait masquée (ou l'inverse).
    """
    if not slug:
        return False
    aide = load_all_aides().get(slug)
    return aide is not None and aide_disponibilite(aide) == "bientot"


def _deja_engage(supabase: Client, user_id: str, slug: str) -> bool:
    """L'utilisateur travaille-t-il déjà sur cette aide ?

    Indispensable, et pas seulement par courtoisie : `disponibilite` range en
    « bientôt » AUSSI une aide dont la date limite est passée — la session
    annuelle est close, l'aide reviendra. Sans cette exemption, un dossier
    ouvert en juin perdrait le nom de son aide au lendemain de la date limite,
    au moment précis où son porteur en a le plus besoin.

    Un dossier ou un suivi vaut engagement : dans les deux cas l'utilisateur
    connaît déjà l'aide, il n'y a plus rien à lui masquer.
    """
    for table in ("dossiers", "aide_suivis"):
        res = (
            supabase.table(table)
            .select("id")
            .eq("user_id", user_id)
            .eq("aide_id", slug)
            .limit(1)
            .execute()
        )
        rows = (res.data if res else None) or []
        if rows:
            return True
    return False


@router.get("/{aide_id}")
def get_aide(
    aide_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """Récupère une aide par id.

    Le moteur déterministe identifie les aides par leur slug (il lit les YAML,
    pas la base). Donc `aide_id` peut être un UUID (aide en base) ou un slug
    (aide servie depuis les YAML). On résout dans cet ordre : UUID en base,
    puis YAML par slug — la même source que le diagnostic, donc l'affichage
    reste cohérent même si le loader n'a pas (encore) poussé l'aide en base.

    Authentifiée, et pas seulement par principe : c'est l'unique chemin vers la
    fiche complète d'une aide, donc la seule porte par laquelle le nom d'une
    aide « Disponibles bientôt » — masqué dans le diagnostic — pourrait sortir.
    Le contrôle porte sur le compte et non sur un monument : la route n'en
    connaît aucun, et une aide à venir est masquée pour toutes les fiches d'un
    compte au gratuit.
    """
    if not billing.offre_du_compte(supabase, user_id).aides_bientot:
        slug = aide_id
        if _is_uuid(aide_id):
            row = (
                supabase.table("aides_v3").select("slug").eq("id", aide_id).maybe_single().execute()
            )
            slug = ((row.data if row else None) or {}).get("slug")
        if slug and _slug_aide_a_venir(slug) and not _deja_engage(supabase, user_id, slug):
            raise HTTPException(
                status_code=402,
                detail="Passez à l'offre Veille pour consulter les aides qui ouvrent bientôt.",
            )

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

    # L'offre qui gouverne le BIEN, pas seulement le compte qui regarde :
    # l'architecte invité sur le chantier d'un client abonné voit le même
    # calendrier que son client.
    offre = quotas.offre_du_monument(supabase, monument_id, user_id)
    return redact_bientot_hors_offre(result, offre)
