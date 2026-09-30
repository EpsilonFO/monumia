import logging
import traceback
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from supabase import Client

from aides_schema import load_all_aides, load_facts, load_pending_facts
from db import get_current_user_id, get_supabase
from eligibility_engine import aide_fiche_dict, run_deterministic_diagnostic
from eligibility_engine import disponibilite as aide_disponibilite
from routers.monuments import (
    enrich_monument_with_population,
    resolve_code_insee,
    valider_proprietaires,
    valider_type_edifice,
)
from services import catalogue_admin, quotas
from services import stripe_billing as billing
from services.offres import GRATUIT, Offre
from services.parallele import en_parallele
from services.project_access import require_project_access, require_projet_access_et_monument

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


class MonumentInvite(BaseModel):
    """Le monument tel que le décrit un VISITEUR, sans compte ni ligne en base.

    Sous-ensemble strict de `CreateMonumentRequest` : uniquement ce que
    `build_context` lit (cf. eligibility_engine). Les autres champs du
    formulaire — référence Mérimée, dates de protection, description — sont
    ignorés par Pydantic : le brouillon les garde côté client jusqu'au rejeu,
    ils n'ont rien à faire dans un calcul.

    Toutes les bornes sont explicites. La route est PUBLIQUE, et pyright
    n'analyse pas `routers/` : ce modèle est le seul rempart, les tests en sont
    le filet.
    """

    nom: str = Field(max_length=200)
    commune: str = Field(max_length=120)
    #: Code INSEE éventuellement HISTORIQUE (Mérimée), résolu par
    #: `resolve_code_insee` vers la commune actuelle.
    codeInsee: str | None = Field(default=None, max_length=10)
    protection: str = Field(max_length=40)
    #: Un ou plusieurs (choix multiple) ; une chaîne seule vaut un propriétaire.
    proprietaire: list[str]
    etatConservation: str | None = Field(default=None, max_length=20)
    siecleConstruction: str | None = Field(default=None, max_length=40)
    #: Natures du bien (choix multiple) et leurs précisions : elles répondent
    #: d'avance aux faits de typologie (cf. DEDUCTIONS_TYPE_EDIFICE). Un code
    #: inconnu est refusé ici, comme à la création du monument, et la liste est
    #: plafonnée au nombre de types.
    typeEdifice: list[str] | None = None
    affecteAuCulte: bool | None = None
    architectureRomane: bool | None = None

    _v_type = field_validator("typeEdifice", mode="before")(valider_type_edifice)
    _v_proprietaire = field_validator("proprietaire", mode="before")(valider_proprietaires)


#: Plafonds du diagnostic invité. Rien de métier : le corpus compte quelques
#: dizaines de types de travaux et l'ontologie une centaine de faits — au-delà,
#: c'est un client qui déraille ou un abus.
_MAX_TRAVAUX_INVITE = 30
_MAX_ANSWERS_INVITE = 100


class DiagnosticInviteRequest(BaseModel):
    """Un diagnostic complet en un seul corps : le bien, le cadrage, les réponses.

    Rien n'est persisté, donc rien n'est référencé par un id : le visiteur n'a
    ni monument ni projet en base. C'est l'équivalent de
    `merge_projet_into_monument` fait côté client.
    """

    monument: MonumentInvite
    travaux_envisages: list[str] = Field(default_factory=list, alias="travauxEnvisages")
    answers: dict[str, object] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}

    @field_validator("travaux_envisages")
    @classmethod
    def _borne_les_travaux(cls, v: list[str]) -> list[str]:
        if len(v) > _MAX_TRAVAUX_INVITE:
            raise ValueError(f"Au plus {_MAX_TRAVAUX_INVITE} types de travaux")
        return [t[:60] for t in v]

    @field_validator("answers")
    @classmethod
    def _borne_les_reponses(cls, v: dict[str, object]) -> dict[str, object]:
        if len(v) > _MAX_ANSWERS_INVITE:
            raise ValueError(f"Au plus {_MAX_ANSWERS_INVITE} réponses")
        return v


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
    "verifie_le": "verifieLe",
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


# Ce qu'une aide non éligible garde quand elle n'a PAS été écartée par une
# réponse. Le front n'affiche que les `elimineParReponse` (ProjetDetailPage,
# diagnostic-bilan) ; les autres ne servent qu'à retrouver une aide par son id
# (fiche atteinte par lien direct, contexte des questions du wizard). Relevé
# champ par champ chez les lecteurs : c'était 9,9 Mo sur 10,1 d'un diagnostic
# complet, pour 8 entrées affichées sur près de 300.
_CHAMPS_MATCH_RESUME = (
    "statut",
    "disponibilite",
    "eligible",
    "elimineParReponse",
    "criteresRemplis",
    "criteresNonRemplis",
)
_CHAMPS_AIDE_RESUME = (
    "id",
    "nom",
    "nomCourt",
    "description",
    "organisme",
    "categorie",
    "familles",
    "montantMax",
    "tauxMax",
    "baseTTC",
    "permanent",
    "dateLimite",
    "dateOuverture",
    "urlOfficielle",
)


def resumer_non_eligibles(result: dict) -> dict:
    """Réduit à un résumé les non éligibles que le front n'affiche jamais.

    Une entrée écartée par une réponse garde tout son détail : c'est la section
    « Écartées par vos réponses », avec son analyse critère par critère. Les
    autres perdent `llmEvaluation` et les champs longs de l'aide, et portent
    `resume: true` — c'est ce drapeau qui dit au front d'aller chercher la fiche
    complète sur `GET /aides/{id}` plutôt que de se contenter du résumé.

    Rien d'autre ne dépend de ces entrées : `totalAidesAnalysees` compte les
    aides traitées, le QCM se bâtit sur les verdicts du moteur, et aucun montant
    n'agrège les non éligibles.
    """
    resumes = []
    for match in result.get("aidesNonEligibles", []):
        if match.get("elimineParReponse"):
            resumes.append(match)
            continue
        aide = match.get("aide") or {}
        resume = {k: match[k] for k in _CHAMPS_MATCH_RESUME if k in match}
        resume["aide"] = {k: aide[k] for k in _CHAMPS_AIDE_RESUME if k in aide}
        resume["resume"] = True
        resumes.append(resume)
    result["aidesNonEligibles"] = resumes
    return result


# Le libellé qui remplace le nom d'une aide là où elle n'est PAS floutée : le
# digest du dashboard, qui alimente l'échéancier et les vignettes de projet. Il
# doit donc rester présentable.
LOCKED_AIDE_LABEL = "Aide masquée"

# Ce qu'on retire d'une aide dont le guichet n'est pas encore ouvert, pour un
# compte qui n'a pas l'offre Veille.
#
# Le NOM n'en fait plus partie : la liste montre les vrais noms, simplement
# floutés (décision produit du 2026-09-03). Conséquence à assumer plutôt qu'à
# oublier — le flou est un habillage, pas une frontière : ces noms partent en
# clair dans la réponse HTTP et l'onglet Réseau des devtools suffit à les lire.
# C'est tenable ici parce que le catalogue est construit à partir de sources
# publiques, et parce que ce que vend l'offre n'est pas le nom : c'est l'email
# le jour de l'ouverture, et le MODE D'EMPLOI ci-dessous.
#
# Le montant, le taux, la catégorie et les dates restent également visibles :
# c'est l'argumentaire de vente, montrer ce qu'il y a à gagner. Ce qui part,
# c'est ce qui permettrait de déposer sans nous.
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


def retirer_les_modalites(aide: dict) -> dict:
    """Retire d'une aide de quoi la déposer : financeur, contacts, pièces.

    Son identité reste (nom, description) : la liste l'affiche floutée. La
    frontière qui tient, c'est celle-ci plus le contrôle sur GET /aides/{id},
    seul chemin vers la fiche complète.
    """
    for field in _REDACTED_AIDE_FIELDS:
        if field in aide:
            aide[field] = None
    # Le financeur de la carte rédigée est l'organisme en quelques mots : il
    # part avec lui. Titre, chapeau et montant restent, comme le nom et la
    # description. Copie : la carte sort du cache YAML du moteur.
    carte = aide.get("carte")
    if carte:
        aide["carte"] = {**carte, "financeur": None}
    aide["locked"] = True
    return aide


# Les trois seaux « à portée ». Ce sont eux, et eux seuls, que le front répartit
# entre « disponibles maintenant » et « disponibles bientôt » : une aide non
# éligible reste dans sa propre section quelle que soit sa fenêtre de dépôt, et
# la caviarder n'aurait aucun sens (il n'y a rien à y vendre).
_BUCKETS_A_PORTEE = ("aidesEligibles", "aidesPotentiellementEligibles", "aidesAtteignables")


def redact_bientot_hors_offre(result: dict, offre: Offre) -> dict:
    """Retire leurs modalités aux aides « Disponibles bientôt » hors offre.

    C'est le seul paywall qui reste sur les aides : leur détail est gratuit dès
    lors que le guichet est ouvert. Ce que l'offre Veille vend sur celles qui
    n'ont pas encore ouvert, c'est l'email le jour de l'ouverture et l'accès à
    leur fiche — plus leur nom, que la liste montre désormais.
    """
    if offre.aides_bientot:
        return result
    for bucket in _BUCKETS_A_PORTEE:
        for match in result.get(bucket, []):
            if match.get("disponibilite") == "bientot":
                match["aide"] = retirer_les_modalites(match["aide"])
    return result


def pseudonymiser_aides(questions: list[dict]) -> list[dict]:
    """Remplace les slugs d'aides des questions par des alias « a1, a2… ».

    Le front ne fait que des tests d'APPARTENANCE entre `aideIds` et les
    valeurs d'`eliminationsParOption` et d'`eliminationsStrictesParOption` (cf. `computeEliminatedAideIds` et
    `isQuestionServingLiveAide` dans frontend/src/lib/qcm.ts) : un alias stable
    à l'intérieur d'une même réponse lui suffit, et le visiteur n'apprend
    aucun nom d'aide au passage.

    Rien d'autre n'a besoin d'être masqué dans une question : `dependsOn`
    référence des questionId et des ids d'option, `categorie` est une clé de
    fait, et les textes viennent de `facts.yaml` (l'ontologie, pas le
    catalogue). Copie, jamais de mutation en place : les questions sortent du
    moteur, dont les YAML sont en cache mémoire.
    """
    alias: dict[str, str] = {}

    def alias_de(slug: str) -> str:
        if slug not in alias:
            alias[slug] = f"a{len(alias) + 1}"
        return alias[slug]

    sorties: list[dict] = []
    for question in questions:
        q = dict(question)
        q["aideIds"] = [alias_de(s) for s in question.get("aideIds") or []]
        for champ in ("eliminationsParOption", "eliminationsStrictesParOption"):
            elim = question.get(champ)
            if elim:
                q[champ] = {option: [alias_de(s) for s in slugs] for option, slugs in elim.items()}
        sorties.append(q)
    return sorties


def synthese_invite(result: dict) -> dict:
    """L'accroche chiffrée : des compteurs et des montants, aucun nom d'aide.

    C'est TOUT ce qu'un visiteur sans compte apprend du catalogue. La liste des
    aides ne sort pas d'ici — elle l'attend derrière l'inscription, où le
    diagnostic est rejoué sous l'offre réelle du compte.
    """
    return {
        "eligibles": len(result.get("aidesEligibles") or []),
        "potentielles": len(result.get("aidesPotentiellementEligibles") or []),
        "atteignables": len(result.get("aidesAtteignables") or []),
        "totalAnalysees": result.get("totalAidesAnalysees") or 0,
        "montantPotentielTotal": result.get("montantPotentielTotal"),
        "montantAtteignableTotal": result.get("montantAtteignableTotal"),
        "tauxTravauxMaxPct": result.get("tauxTravauxMaxPct"),
    }


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


def _slug_de(supabase: Client, aide_id: str) -> str | None:
    """Le slug derrière un identifiant d'aide, qu'il soit un UUID ou déjà un slug.

    Deux espaces d'identifiants cohabitent (cf. CLAUDE.md) : le YAML et le
    moteur parlent slug, `aides_v3` parle UUID. Tout ce qui se décide sur
    l'aide elle-même — paywall des guichets à venir, retrait du catalogue — se
    décide sur le slug, donc la résolution est faite une fois pour toutes.
    """
    if not _is_uuid(aide_id):
        return aide_id
    row = supabase.table("aides_v3").select("slug").eq("id", aide_id).maybe_single().execute()
    return ((row.data if row else None) or {}).get("slug")


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
    # Le slug est résolu une seule fois : le paywall des aides à venir et le
    # retrait du catalogue se prononcent tous les deux dessus. Une ligne
    # `aides_v3` héritée sans slug laisse `None`, et l'aide est servie
    # (fail-open : pas de faux 404 sur une donnée incomplète).
    slug = _slug_de(supabase, aide_id)

    if slug and slug in catalogue_admin.catalogue_effectif(supabase).retirees:
        raise HTTPException(status_code=404, detail="Aide retirée du catalogue")

    if (
        slug
        and _slug_aide_a_venir(slug)
        and not billing.offre_du_compte(supabase, user_id).aides_bientot
        and not _deja_engage(supabase, user_id, slug)
    ):
        raise HTTPException(
            status_code=402,
            detail="Passez à l'offre Veille pour consulter les aides qui ouvrent bientôt.",
        )

    if _is_uuid(aide_id):
        result = supabase.table("aides_v3").select("*").eq("id", aide_id).maybe_single().execute()
        if result and result.data:
            return _to_camel(result.data)

    # La fiche complète (rédaction, règlement cité) ne part que d'ici : le
    # diagnostic n'en emporte que la `carte`, pour ne pas alourdir cent aides.
    aide = load_all_aides().get(aide_id)
    if aide:
        return _to_camel(aide_fiche_dict(aide))

    raise HTTPException(status_code=404, detail="Aide introuvable")


def deterministic_diagnostic_for(
    monument: dict,
    population: int | None,
    answers: dict[str, object] | None,
    *,
    supabase: Client | None = None,
) -> dict:
    """Lance le moteur déterministe et rend le résultat prêt pour le frontend.

    Purement CPU (les YAML sont en cache, ~2 ms par monument) : aucun appel
    réseau, d'où la possibilité de l'exécuter pour tous les projets d'un coup
    dans /dashboard.

    Un seul funnel sert TOUS les diagnostics du produit (route projet, route
    invité, dashboard) : c'est donc ici, et nulle part ailleurs, que s'applique
    la surcouche d'administration — aides retirées du catalogue et questions
    reformulées (cf. services/catalogue_admin). Elle couvre du même coup les
    quatre seaux, `totalAidesAnalysees`, l'échéancier, les vignettes et le QCM.

    `supabase=None` rend le moteur NU, sur les seuls YAML : c'est ce que veulent
    les tests du moteur et les scripts hors ligne. Les trois appelants du
    produit passent leur client.
    """
    if supabase is not None:
        catalogue = catalogue_admin.catalogue_effectif(supabase)
        aides, facts = catalogue.aides, catalogue.facts
    else:
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
    return resumer_non_eligibles(_camelise_diagnostic(result))


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
    # Trois vagues d'allers-retours Supabase au lieu de sept en série : le
    # projet, puis ses appartenances avec la ligne du monument, puis la commune
    # avec l'offre. Le contrôle d'accès passe toujours en premier dans chaque
    # vague, pour que ce soit SON refus qui sorte (cf. services/parallele).
    if body.projet_id:
        # Accès projet partagé : un collaborateur (membre) doit pouvoir lancer le
        # diagnostic, pas seulement le propriétaire — d'où require_projet_access
        # plutôt qu'un filtre user_id (qui renverrait 404 aux collaborateurs).
        projet, _, monument_row = require_projet_access_et_monument(
            supabase, body.projet_id, user_id, "member"
        )
        monument_id = projet["monument_id"]
    else:
        monument_id = body.monument_id or ""
        _, projet, monument_result = en_parallele(
            lambda: require_project_access(supabase, monument_id, user_id, "member"),
            lambda: _latest_open_projet(supabase, monument_id),
            lambda: (
                supabase.table("monuments")
                .select("*")
                .eq("id", monument_id)
                .maybe_single()
                .execute()
            ),
        )
        monument_row = monument_result.data if monument_result else None
        if not monument_row:
            raise HTTPException(status_code=404, detail="Monument introuvable")

    # L'offre qui gouverne le BIEN, pas seulement le compte qui regarde :
    # l'architecte invité sur le chantier d'un client abonné voit le même
    # calendrier que son client. Le propriétaire est déjà sur la ligne lue.
    proprietaire = monument_row.get("user_id")
    (monument, population), offre = en_parallele(
        lambda: enrich_monument_with_population(supabase, monument_row),
        lambda: quotas.offre_du_monument(supabase, monument_id, user_id, proprietaire=proprietaire),
    )

    # Remplacement entier, jamais de fusion profonde : le front envoie le
    # questionnaire complet (réponses + clés réservées). `answers` absent =
    # on reprend celui enregistré sur le projet.
    answers = (
        body.answers if body.answers is not None else (projet or {}).get("questionnaire") or {}
    )

    result = deterministic_diagnostic_for(
        merge_projet_into_monument(monument, projet), population, answers, supabase=supabase
    )
    # Le moteur ne connaît que le monument : on stampe le projet à la frontière,
    # c'est lui qui clé le store de diagnostics et les liens d'échéance du front.
    result["projetId"] = projet["id"] if projet else None
    return redact_bientot_hors_offre(result, offre)


@router.post("/diagnostic-invite")
def diagnostic_invite(
    body: DiagnosticInviteRequest,
    supabase: Client = Depends(get_supabase),
):
    """Diagnostic d'un monument DÉCRIT SUR PLACE, sans compte ni persistance.

    C'est le moteur du parcours découverte : le visiteur décrit son bien depuis
    la landing, cadre un chantier, répond au questionnaire, et ne crée son
    compte qu'à la fin. Rien n'est écrit — ni monument, ni projet, ni
    diagnostic : le brouillon vit dans le `localStorage` du navigateur, et
    l'inscription rejoue `POST /monuments` puis `POST /monuments/{id}/projets`.

    PUBLIQUE, donc, et la réponse est volontairement PAUVRE : les questions du
    QCM (avec des identifiants d'aides pseudonymisés) et une synthèse chiffrée.
    Aucun objet aide n'en sort, aucun nom, aucun slug. Le visiteur voit
    strictement moins qu'un compte gratuit, et c'est ce qui rend l'ouverture
    tenable — le seul chemin vers la fiche d'une aide reste
    `GET /aides/{aide_id}`, authentifié.

    Coût par appel : une requête `communes` et ~2 ms de CPU, comparable à
    `GET /communes/search` (public lui aussi). Le backend n'a aucun limiteur de
    débit : c'est un `limit_req` nginx qui borne l'abus, au déploiement.
    """
    m = body.monument
    # Résolution STRICTE (400 si la commune est introuvable) : le front la
    # provoque dès l'étape monument, en dry-run. Un 400 découvert au rejeu
    # tomberait APRÈS l'inscription, sur un brouillon impossible à corriger.
    code_insee = resolve_code_insee(supabase, m.commune, historical_code=m.codeInsee or None)

    # Le monument que le moteur attend : snake_case, `travaux_envisages` posé
    # directement dessus — c'est ce que fait `merge_projet_into_monument` pour
    # un projet en base, sauf qu'ici il n'y a ni l'un ni l'autre.
    monument = {
        "nom": m.nom,
        "code_insee": code_insee,
        "protection": m.protection,
        "proprietaire": m.proprietaire,
        "etat_conservation": m.etatConservation,
        "siecle_construction": m.siecleConstruction,
        "type_edifice": m.typeEdifice,
        "affecte_au_culte": m.affecteAuCulte,
        "architecture_romane": m.architectureRomane,
        "travaux_envisages": body.travaux_envisages,
    }
    monument, population = enrich_monument_with_population(supabase, monument)

    result = deterministic_diagnostic_for(monument, population, body.answers, supabase=supabase)
    # Symétrie avec la route authentifiée : un visiteur est au gratuit. Sans
    # effet sur ce qui sort (aucune aide ne sort), mais le jour où la synthèse
    # s'enrichira, elle partira d'un résultat déjà caviardé.
    result = redact_bientot_hors_offre(result, GRATUIT)

    return {
        "qcmQuestions": pseudonymiser_aides(result.get("qcmQuestions") or []),
        "synthese": synthese_invite(result),
    }
