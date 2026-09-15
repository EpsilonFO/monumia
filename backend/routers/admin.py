"""Administration du catalogue : retirer une aide, reformuler une question.

Les réponses d'une question sont éditables sur un `enum`, un `multi_enum` et un
`boolean` — sur ce dernier, chaque réponse déclare en plus la valeur qu'elle
envoie aux prédicats des aides, ce qui permet d'offrir plus de deux réponses à
une question binaire sans retyper un seul prédicat. Seules les tranches d'un
fait numérique restent calculées par le moteur.

Douze routes, toutes réservées aux comptes de `ADMIN_USER_IDS` (cf.
`config.est_admin`). Le `Depends(require_admin)` est posé sur le ROUTER et non
sur chaque route : aucune route nouvelle ne peut l'oublier.

La mécanique vit dans `services/catalogue_admin` — pyright n'analyse pas
`routers/`. Ici : les corps de requête (bornés, `extra="forbid"`), les 404 et
la traduction d'un refus de validation en 422.

Toutes les routes répondent 200 avec un corps JSON, suppressions comprises : le
`handleResponse` du frontend appelle `res.json()` sur chaque réponse, et un 204
le ferait échouer.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from supabase import Client

from aides_schema import load_all_aides, load_facts, load_pending_facts
from db import get_supabase, require_admin
from eligibility_engine import engine_ready_aides
from services import catalogue_admin, catalogue_stats
from services.catalogue_admin import (
    HELP_MAX,
    LABEL_MAX,
    MOTIF_MAX,
    OPTIONS_MAX,
    QUESTION_MAX,
    OptionSurchargee,
    SurchargeFait,
)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


# ---------------------------------------------------------------------------
# Corps de requête
# ---------------------------------------------------------------------------


class RetraitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Pourquoi l'aide est retirée — pour l'autre fondateur, qui verra la ligne.
    motif: str | None = Field(default=None, max_length=500)


class OptionRequest(BaseModel):
    """Une réponse possible. `id` figé pour les réponses existantes : les
    prédicats des aides le citent (cf. l'impact affiché avant enregistrement)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9_]+$", max_length=80)
    label: str = Field(min_length=1, max_length=LABEL_MAX)
    unknown: bool = False
    #: Questions Oui/Non seulement : la valeur envoyée aux prédicats des aides.
    #: `None` = « ne tranche pas ». Refusé sur un fait à choix par
    #: `valider_surcharge`, qui rend un 422.
    valeur: bool | None = None


class SimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    options: list[OptionRequest] = Field(max_length=OPTIONS_MAX)


class SurchargeRequest(BaseModel):
    """Reformulation d'une question. Un champ absent = « garder le YAML » ;
    `options`, quand elle est là, REMPLACE la liste entière."""

    model_config = ConfigDict(extra="forbid")

    question: str | None = Field(default=None, max_length=QUESTION_MAX)
    help: str | None = Field(default=None, max_length=HELP_MAX)
    options: list[OptionRequest] | None = Field(default=None, max_length=OPTIONS_MAX)


def _options(options: list[OptionRequest] | None) -> list[OptionSurchargee] | None:
    """Traduction champ à champ. Un champ oublié ici passerait le type-check —
    pyright n'analyse pas `routers/` — et partirait silencieusement à `None` :
    c'est `test_admin_routes` qui tient ce contrat, pas le typeur."""
    if options is None:
        return None
    return [
        OptionSurchargee(id=o.id, label=o.label, unknown=o.unknown, valeur=o.valeur)
        for o in options
    ]


class PredicatRequest(BaseModel):
    """Le point de conception du chantier : on ne transporte JAMAIS un prédicat
    JSON brut sur le fil.

    Un opérateur pris dans quatre littéraux et une liste de chaînes rendent
    INEXPRIMABLES la moitié des états invalides — pas de combinateur, pas de
    valeur non-chaîne, pas de liste vide — et `check_fact_predicate` s'occupe du
    reste. La contrainte « impossible de produire un prédicat invalide » est
    tenue par le type, pas par la bonne volonté du composant.
    """

    model_config = ConfigDict(extra="forbid")

    operateur: Literal["eq", "neq", "in", "not_in"]
    valeurs: list[str] = Field(min_length=1, max_length=OPTIONS_MAX)
    #: Pourquoi, pour l'autre fondateur qui verra la ligne.
    motif: str | None = Field(default=None, max_length=MOTIF_MAX)


def _fait_ou_404(key: str):
    """Le fait tel qu'il est dans les YAML. 404 sur une clé inconnue : la
    surcharge est une couche PAR-DESSUS l'ontologie, elle n'en crée pas."""
    fact = {**load_facts(), **load_pending_facts()}.get(key)
    if fact is None:
        raise HTTPException(status_code=404, detail=f"Fait inconnu « {key} »")
    return fact


# ---------------------------------------------------------------------------
# Aides
# ---------------------------------------------------------------------------


@router.get("/aides")
def lister_aides(supabase: Client = Depends(get_supabase)):
    return catalogue_admin.lister_aides_admin(supabase)


@router.put("/aides/{slug}/retrait")
def retirer_aide(
    slug: str,
    body: RetraitRequest,
    user_id: str = Depends(require_admin),
    supabase: Client = Depends(get_supabase),
):
    """Retire l'aide du catalogue : elle disparaît des diagnostics, sa fiche
    répond 404 et on ne peut plus ouvrir de dossier dessus."""
    if slug not in load_all_aides():
        raise HTTPException(status_code=404, detail=f"Aide inconnue « {slug} »")
    return catalogue_admin.retirer_aide(supabase, slug, body.motif, user_id)


@router.delete("/aides/{slug}/retrait")
def republier_aide(slug: str, supabase: Client = Depends(get_supabase)):
    """Republie l'aide. Pas de 404 sur un slug absent du corpus, contrairement
    au retrait : une aide archivée entre-temps garderait sinon sa ligne de
    retrait pour toujours, sans moyen de la retirer depuis l'application."""
    return catalogue_admin.republier_aide(supabase, slug)


# ---------------------------------------------------------------------------
# Statistiques du catalogue
# ---------------------------------------------------------------------------


@router.get("/statistiques")
def statistiques(supabase: Client = Depends(get_supabase)):
    """Le catalogue en chiffres : par région, par département, au national.

    Recalculé à chaque appel sur le catalogue en cache — la page se rafraîchit
    d'elle-même, et un retrait enregistré se voit au plus tard au TTL suivant.
    Un nouveau lot d'aides, lui, entre par les YAML : il apparaît au
    redémarrage du backend, c'est-à-dire au déploiement qui l'amène.
    """
    return catalogue_stats.statistiques_catalogue(supabase)


# ---------------------------------------------------------------------------
# Questions du QCM
# ---------------------------------------------------------------------------


@router.get("/faits")
def lister_faits(supabase: Client = Depends(get_supabase)):
    return catalogue_admin.lister_faits_admin(supabase)


@router.post("/faits/{key}/simuler")
def simuler_options(
    key: str,
    body: SimulationRequest,
    supabase: Client = Depends(get_supabase),
):
    """L'impact du brouillon, SANS rien écrire : ce que chaque réponse écarte,
    et quelles aides citent une réponse qu'on s'apprête à supprimer."""
    original = _fait_ou_404(key)
    catalogue = catalogue_admin.catalogue_effectif(supabase)
    return catalogue_admin.impact_options(
        key, _options(body.options) or [], catalogue.aides, original
    )


@router.put("/faits/{key}")
def surcharger_fait(
    key: str,
    body: SurchargeRequest,
    user_id: str = Depends(require_admin),
    supabase: Client = Depends(get_supabase),
):
    original = _fait_ou_404(key)
    brouillon = SurchargeFait(
        fact_key=key, question=body.question, help=body.help, options=_options(body.options)
    )
    try:
        catalogue_admin.valider_surcharge(original, brouillon)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return catalogue_admin.enregistrer_surcharge(supabase, key, brouillon, user_id)


@router.delete("/faits/{key}")
def retablir_fait(key: str, supabase: Client = Depends(get_supabase)):
    """Rend au fait sa formulation d'origine (celle de `facts.yaml`)."""
    _fait_ou_404(key)
    return catalogue_admin.retablir_fait(supabase, key)


# ---------------------------------------------------------------------------
# Prédicats de conditions
# ---------------------------------------------------------------------------


def _condition_ou_404(supabase: Client, slug: str, condition_id: str):
    """Trois causes de refus, trois messages — l'aide, la condition, le mandat.
    `condition_servie` les distingue, la route se contente de les traduire."""
    try:
        return catalogue_admin.condition_servie(supabase, slug, condition_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=exc.args[0]) from exc


@router.get("/conditions")
def lister_conditions(supabase: Client = Depends(get_supabase)):
    """L'inventaire des conditions modifiables, plus les surcharges orphelines
    (aide ou condition disparue) — qui doivent rester supprimables."""
    return catalogue_admin.lister_conditions_admin(supabase)


@router.post("/conditions/{slug}/{condition_id}/simuler")
def simuler_predicat(
    slug: str,
    condition_id: str,
    body: PredicatRequest,
    supabase: Client = Depends(get_supabase),
):
    """Ce que le nouveau prédicat change, SANS rien écrire : réponse par
    réponse, le verdict avant et après, plus les avertissements qui rendent
    l'impact honnête (dérogation, levier, applies_if, autres gates)."""
    aide, condition, catalogue = _condition_ou_404(supabase, slug, condition_id)
    predicate = catalogue_admin.predicat_depuis(body.operateur, body.valeurs)
    try:
        catalogue_admin.valider_predicat(condition, predicate, catalogue.facts)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return catalogue_admin.impact_predicat(
        aide,
        condition,
        predicate,
        catalogue.facts,
        engine_ready=slug in engine_ready_aides(catalogue.aides),
        retiree=slug in catalogue.retirees,
    )


@router.put("/conditions/{slug}/{condition_id}")
def surcharger_predicat(
    slug: str,
    condition_id: str,
    body: PredicatRequest,
    user_id: str = Depends(require_admin),
    supabase: Client = Depends(get_supabase),
):
    """Remplace le prédicat servi pour cette condition. Un prédicat revenu à
    celui du YAML supprime la ligne au lieu de l'écrire."""
    _aide, condition, catalogue = _condition_ou_404(supabase, slug, condition_id)
    predicate = catalogue_admin.predicat_depuis(body.operateur, body.valeurs)
    try:
        catalogue_admin.valider_predicat(condition, predicate, catalogue.facts)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return catalogue_admin.enregistrer_predicat(
        supabase, slug, condition_id, predicate, body.motif, user_id
    )


@router.delete("/conditions/{slug}/{condition_id}")
def retablir_predicat(slug: str, condition_id: str, supabase: Client = Depends(get_supabase)):
    """Rend à la condition le prédicat de son YAML.

    Pas de 404, contrairement aux deux routes précédentes : une ligne orpheline
    (aide archivée, condition disparue) doit pouvoir partir, et c'est justement
    par cette route qu'on la nettoie.
    """
    return catalogue_admin.retablir_predicat(supabase, slug, condition_id)
