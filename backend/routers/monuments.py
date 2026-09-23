import contextlib
import re
import unicodedata
import uuid
from datetime import date
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from db import get_current_user_id, get_supabase
from services import quotas
from services.offres import as_dict
from services.parallele import en_parallele
from services.project_access import (
    monument_ids_via_projets,
    projet_roles_propres,
    require_monument_read,
    require_project_access,
)

router = APIRouter(prefix="/monuments", tags=["monuments"])

COLUMNS = "*"

# Les photos vivent dans le même bucket privé que les documents : jamais
# d'URL publique, un lien signé à la lecture (cf. sign_photos).
STORAGE_BUCKET = "documents"
SIGNED_URL_EXPIRY = 7 * 24 * 60 * 60  # 7 jours, en secondes

# La « photo de profil » du monument est une photo comme les autres, marquée par
# son type : c'est elle qui illustre la fiche, les cartes et le tableau de bord.
PHOTO_PROFIL_TYPE = "profil"


def _to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _snake_row(data: dict) -> dict:
    """Recursively convert all dict keys from camelCase to snake_case."""
    return {_to_snake(k): v for k, v in data.items()}


# Colonnes `date` de `monuments`. Le formulaire envoie `""` pour dire « pas de
# date » — notamment quand on choisit « non protégé », qui vide date et détail
# de protection. PostgreSQL, lui, refuse la chaîne vide sur une colonne `date`
# (« invalid input syntax for type date »), et l'erreur PostgREST remontait en
# 500 à la dernière étape du wizard : c'est le cas typique d'un monument absent
# de Mérimée, saisi à la main et non protégé.
DATE_COLUMNS = ("date_protection",)


def _normalize_dates(row: dict) -> dict:
    """Chaîne vide → NULL SQL, date mal formée → 400 plutôt que 500.

    La clé est CONSERVÉE à None au lieu d'être retirée : sur un PATCH, la
    retirer laisserait l'ancienne date en base, et effacer une date deviendrait
    impossible.
    """
    for column in DATE_COLUMNS:
        value = row.get(column)
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if not cleaned:
            row[column] = None
            continue
        try:
            date.fromisoformat(cleaned)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Date invalide : '{value}' (format attendu AAAA-MM-JJ)",
            ) from None
        row[column] = cleaned
    return row


def _normalize_commune(name: str) -> str:
    """Lowercase and strip accents from a commune name."""
    nfkd = unicodedata.normalize("NFKD", name)
    without_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return without_accents.lower()


def _validate_photo_storage_path(path: str, user_id: str) -> str:
    """Photo URLs are storage paths scoped to the caller's folder.

    The frontend uploads photos to the same private "documents" bucket under
    "<user_id>/...". Reject anything else so a tampered client can't reference
    another user's storage objects.
    """
    if not path or not isinstance(path, str):
        raise HTTPException(status_code=400, detail="URL de photo invalide")
    if "://" in path or path.startswith("/") or ".." in path.split("/"):
        raise HTTPException(status_code=400, detail="URL de photo invalide")
    if not path.startswith(f"{user_id}/"):
        raise HTTPException(status_code=403, detail="URL de photo non autorisée")
    return path


def sign_photos(supabase: Client, monuments: list[dict]) -> None:
    """Attache à chaque photo une `signed_url` affichable, en place.

    Le bucket est privé : le chemin de stockage brut ne s'affiche pas dans un
    `<img>`. La signature passe par le service role (comme pour les documents)
    afin que TOUT membre du monument voie la photo, pas seulement le déposant.
    Une seule signature par lot pour toute la liste. En cas d'échec storage on
    n'attache rien — une vignette manquante vaut mieux qu'une liste en erreur.
    """
    paths = {
        photo["url"]
        for monument in monuments
        for photo in (monument.get("photos") or [])
        if isinstance(photo.get("url"), str) and photo["url"] and "://" not in photo["url"]
    }
    if not paths:
        return

    signed_by_path: dict[str, str] = {}
    try:
        results = supabase.storage.from_(STORAGE_BUCKET).create_signed_urls(
            sorted(paths), SIGNED_URL_EXPIRY
        )
    except Exception:
        return
    for entry in results or []:
        path = (entry.get("path") or "").lstrip("/")
        signed = entry.get("signedURL") or entry.get("signedUrl")
        if path and signed:
            signed_by_path[path] = signed

    for monument in monuments:
        for photo in monument.get("photos") or []:
            signed = signed_by_path.get(photo.get("url"))
            if signed:
                photo["signed_url"] = signed


def _remove_from_storage(supabase: Client, path: str | None) -> None:
    """Efface au mieux l'objet storage d'une photo remplacée ou retirée."""
    if not path or "://" in path or ".." in path.split("/"):
        return
    with contextlib.suppress(Exception):
        supabase.storage.from_(STORAGE_BUCKET).remove([path])


def _try_resolve_code_insee(
    supabase: Client,
    commune_name: str | None,
    historical_code: str | None = None,
) -> str | None:
    """Resolve a commune to a currently-active code_insee, or None if unresolvable.

    Cascade:
      1. If historical_code is an active commune, use it.
      2. If historical_code maps to a current commune via communes_historique, use that.
      3. Match commune_name against communes.nom_commune_matching.
    """
    if historical_code:
        direct = (
            supabase.table("communes")
            .select("code_insee")
            .eq("code_insee", historical_code)
            .limit(1)
            .execute()
        )
        if direct.data:
            return direct.data[0]["code_insee"]

        mapped = (
            supabase.table("communes_historique")
            .select("nouveau_code_insee")
            .eq("ancien_code_insee", historical_code)
            .limit(1)
            .execute()
        )
        if mapped.data:
            return mapped.data[0]["nouveau_code_insee"]

    if commune_name:
        normalized = _normalize_commune(commune_name)
        by_name = (
            supabase.table("communes")
            .select("code_insee")
            .eq("nom_commune_matching", normalized)
            .limit(1)
            .execute()
        )
        if by_name.data:
            return by_name.data[0]["code_insee"]

    return None


def resolve_code_insee(
    supabase: Client,
    commune_name: str,
    historical_code: str | None = None,
) -> str:
    """Resolve a commune name to a current code_insee, or raise 400.

    Publique (et pas seulement pour ce routeur) : le diagnostic invité
    (`routers/aides.py`) la réutilise telle quelle, parce qu'elle est la seule
    à gérer le code INSEE historique de Mérimée via `communes_historique`.
    `enrich_monument_with_population` fait un `eq("code_insee")` direct et
    raterait une commune fusionnée.
    """
    code = _try_resolve_code_insee(supabase, commune_name, historical_code)
    if code is None:
        raise HTTPException(
            status_code=400,
            detail=f"Commune introuvable : '{commune_name}'",
        )
    return code


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class MonumentPhoto(BaseModel):
    id: str
    url: str
    legende: str
    type: str  # 'facade' | 'interieur' | 'detail' | 'aerien' | 'degradation' | 'autre'
    datePhoto: str | None = None


class CreateMonumentRequest(BaseModel):
    # NOTE: only fields backed by a real `monuments` column belong here. Ten
    # per-attribute columns (affectataire, periode_construction, superficie,
    # materiaux, type_couverture, nombre_niveaux, urgence_travaux,
    # diagnostic_realise, derniers_travaux, description_etat) were dropped by
    # migration 20260516174303. `questionnaire`, `travaux_envisages` et
    # `cloture_at` l'ont été à leur tour par la dépréciation qui suit la
    # création de `projets` : le cadrage d'un chantier vit sur le projet.
    # Pydantic ignores any such extra keys the client still sends, so they never
    # reach the insert (which PostgREST would otherwise reject with PGRST204).
    nom: str
    commune: str  # Used to resolve code_insee, not stored in DB
    codeInsee: str | None = None
    referenceMerimee: str | None = None

    protection: str
    dateProtection: str | None = None
    typeProtection: str | None = None
    proprietaire: str

    siecleConstruction: str | None = None
    descriptionGenerale: str | None = None

    # Nullable (migration 20260827094119) : les fiches créées avant que la
    # question n'existe n'ont pas d'état, et le wizard projet les rattrape. La
    # colonne RESTE sur le monument : elle décrit le bien, pas un chantier, et
    # tous ses projets la partagent.
    etatConservation: str | None = None


class UpdateMonumentRequest(BaseModel):
    # See CreateMonumentRequest: fields must map to a real `monuments` column.
    # The dropped per-attribute columns (and `adresse`, which never existed) are
    # intentionally absent; extra keys from the client are ignored.
    nom: str | None = None
    commune: str | None = None  # Used to resolve code_insee, not stored in DB
    codeInsee: str | None = None
    referenceMerimee: str | None = None

    protection: str | None = None
    dateProtection: str | None = None
    typeProtection: str | None = None
    proprietaire: str | None = None

    siecleConstruction: str | None = None
    descriptionGenerale: str | None = None

    etatConservation: str | None = None
    completionPercentage: int | None = None


class AddPhotoRequest(BaseModel):
    url: str
    legende: str
    type: str
    datePhoto: str | None = None


class PhotoProfilRequest(BaseModel):
    """Chemin de stockage de la photo fraîchement déposée par le front."""

    url: str
    legende: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _attach_epci(monument: dict, commune_row: dict) -> None:
    """Pose le rattachement intercommunal sur le monument.

    `commune.epci` est un chemin du FIELD_REGISTRY : les aides intercommunales
    (ex. CC Moret Seine et Loing = SIREN 247700032) le comparent au SIREN de
    leur EPCI porteur. La clé est écrite en notation pointée parce que
    `eligibility_engine.build_context` lit les champs d'enrichissement commune
    directement sous leur chemin de registre.

    Clé absente si la commune n'a pas d'EPCI (îles mono-communales) ou si la
    colonne n'est pas encore seedée : le moteur y voit une incertitude
    fail-closed, jamais une non-éligibilité. `communes.epci_nom` reste hors du
    monument — aucun affichage ne le consomme, les libellés d'EPCI sont déjà
    dans le texte des conditions.
    """
    siren = commune_row.get("epci_siren")
    if siren:
        monument["commune.epci"] = siren


def enrich_monument_with_population(supabase: Client, monument: dict) -> tuple[dict, int | None]:
    """Join commune data (commune, departement, region) + population via code_insee.

    `region` is stored as the kebab-case code (e.g. "ile-de-france") so it
    matches both `aides_v3.regions` (used by the SQL pre-filter) and the
    frontend `Region` type. The INSEE display label (e.g. "Île-de-France")
    is exposed separately as `region_label`.

    La population sort de la même ligne : les appelants qui en ont besoin (le
    diagnostic déterministe) interrogeaient `communes` une seconde fois sur le
    même code_insee.
    """
    code_insee = monument.get("code_insee")
    if not code_insee:
        return monument, None

    result = (
        supabase.table("communes")
        .select(
            "nom_commune, departement, departement_num, region, region_code, population, epci_siren"
        )
        .eq("code_insee", code_insee)
        .limit(1)
        .execute()
    )
    if not result.data:
        return monument, None

    row = result.data[0]
    monument["commune"] = row["nom_commune"]
    monument["departement"] = row["departement"]
    monument["departement_num"] = row["departement_num"]
    monument["region"] = row.get("region_code")
    monument["region_label"] = row.get("region")
    _attach_epci(monument, row)
    return monument, row.get("population")


def _enrich_monument(supabase: Client, monument: dict, user_id: str) -> dict:
    """Voir enrich_monument_with_population — variante sans la population.

    Pose aussi `offre` : l'offre qui gouverne ce bien (celle de son propriétaire
    unie à celle de l'appelant, cf. services/quotas.py). Le frontend en tire les
    boutons qu'il affiche sur la fiche et sur les projets du monument — d'où sa
    présence sur TOUTE réponse portant un monument, et pas seulement sur la
    liste : une fiche fraîchement créée doit déjà savoir ce qu'elle permet.
    """
    proprietaire = monument.get("user_id")
    (monument, _), offre = en_parallele(
        lambda: enrich_monument_with_population(supabase, monument),
        lambda: quotas.offre_du_monument(
            supabase, monument["id"], user_id, proprietaire=proprietaire
        ),
    )
    monument["offre"] = as_dict(offre)
    return monument


def _get_monument_or_404(supabase: Client, monument_id: str, user_id: str) -> dict:
    result = (
        supabase.table("monuments")
        .select(COLUMNS)
        .eq("id", monument_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Monument introuvable")
    return _enrich_monument(supabase, result.data, user_id)


def _compute_completion(monument: dict) -> int:
    """Recompute completionPercentage based on filled fields."""
    steps = [
        # Step 1 — Identification
        all(
            [
                monument.get("nom"),
                monument.get("code_insee"),
            ]
        ),
        # Step 2 — Legal
        all([monument.get("protection"), monument.get("proprietaire")]),
        # Step 3 — Physical
        any(
            [
                monument.get("siecle_construction"),
                monument.get("description_generale"),
            ]
        ),
        # Step 4 — State
        bool(monument.get("etat_conservation")),
        # Step 5 — Photos
        bool(monument.get("photos")),
    ]
    return int(sum(steps) / len(steps) * 100)


def build_members_index(
    member_rows: list[dict], profiles: dict[str, dict]
) -> dict[str, list[dict]]:
    """Regroupe les membres par monument pour l'aperçu de la liste des projets.

    member_rows : lignes project_members {monument_id, user_id, role}.
    profiles    : {user_id: {prenom, nom}}.
    Renvoie {monument_id: [{user_id, prenom, nom, role}]} en préservant l'ordre.
    """
    index: dict[str, list[dict]] = {}
    for row in member_rows:
        profile = profiles.get(row["user_id"], {})
        index.setdefault(row["monument_id"], []).append(
            {
                "user_id": row["user_id"],
                "prenom": profile.get("prenom", ""),
                "nom": profile.get("nom", ""),
                "role": row["role"],
            }
        )
    return index


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def fetch_user_monuments(
    supabase: Client, user_id: str
) -> tuple[list[dict], dict[str, int | None], dict[str, str]]:
    """Tous les monuments accessibles à l'utilisateur, enrichis et prêts à servir.

    Renvoie aussi la population par code_insee, récupérée dans la même requête
    `communes` : le dashboard en a besoin pour le moteur déterministe, et la
    rechercher séparément coûtait un aller-retour par monument. Et les projets où
    l'utilisateur a une appartenance PROPRE, avec son rôle (`projet_roles_propres`),
    lus ici de toute façon : le dashboard les relisait juste après, et en tire le
    rôle effectif de chaque projet.

    Quatre vagues d'allers-retours, quel que soit le nombre de monuments (cf.
    services/parallele) :
      A. les appartenances de l'utilisateur (équipes de monument, monuments
         possédés, équipes de projet) ;
      B. les monuments atteints par un projet, et la composition des équipes ;
      C. les lignes des monuments, et les profils des membres ;
      D. les communes, et l'offre qui gouverne chaque bien.
    """
    # ── Vague A ──────────────────────────────────────────────────────────────
    memberships, owned, roles_propres = en_parallele(
        lambda: (
            supabase.table("project_members")
            .select("monument_id, role")
            .eq("user_id", user_id)
            .execute()
            .data
        ),
        lambda: supabase.table("monuments").select("id").eq("user_id", user_id).execute().data,
        lambda: projet_roles_propres(supabase, user_id),
    )
    mes_projets = list(roles_propres)
    role_by_id = {m["monument_id"]: m["role"] for m in memberships or []}

    # Défense en profondeur : un propriétaire voit toujours SES monuments, même si
    # la ligne d'appartenance 'owner' manque (cf. get_project_role). user_id =
    # propriétaire authoritatif et immuable du monument.
    for o in owned or []:
        role_by_id.setdefault(o["id"], "owner")

    # ── Vague B ──────────────────────────────────────────────────────────────
    # Aperçu des membres par monument (avatars + compteur côté liste, sans une
    # requête par carte). Restreint aux monuments dont l'utilisateur est membre :
    # un accès par projet ne donne pas droit à la composition de l'équipe du bien.
    equipe_visible = list(role_by_id.keys())
    via_projets, all_members = en_parallele(
        lambda: monument_ids_via_projets(supabase, mes_projets),
        lambda: (
            (
                supabase.table("project_members")
                .select("monument_id, user_id, role")
                .in_("monument_id", equipe_visible)
                .execute()
                .data
            )
            or []
            if equipe_visible
            else []
        ),
    )

    # Monuments atteints par un PROJET seulement : l'utilisateur y a besoin d'une
    # porte d'entrée pour rejoindre son chantier, mais n'a aucun rôle sur le bien.
    # `my_role` restera None — le front y lit « fiche sanitaire en lecture, et
    # rien d'autre » (cf. require_monument_read).
    acces_restreint = {mid for mid in via_projets.values() if mid not in role_by_id}

    monument_ids = [*role_by_id.keys(), *acces_restreint]
    if not monument_ids:
        return [], {}, roles_propres

    # ── Vague C ──────────────────────────────────────────────────────────────
    member_user_ids = list({m["user_id"] for m in all_members})
    monuments, prows = en_parallele(
        lambda: (
            supabase.table("monuments")
            .select(COLUMNS)
            .in_("id", monument_ids)
            .order("created_at", desc=True)
            .execute()
            .data
        ),
        lambda: (
            supabase.table("users")
            .select("id, prenom, nom")
            .in_("id", member_user_ids)
            .execute()
            .data
            if member_user_ids
            else []
        ),
    )
    monuments = monuments or []
    profiles = cast("dict[str, dict]", {r["id"]: r for r in prows or []})
    members_by_monument = build_members_index(all_members, profiles)

    # ── Vague D ──────────────────────────────────────────────────────────────
    # L'offre qui gouverne chaque bien, en une requête pour toute la liste : le
    # propriétaire est déjà sur les lignes lues. Le frontend s'en sert pour
    # décider quels boutons afficher sur chaque monument, et /dashboard pour
    # masquer les aides encore à venir.
    code_insees = list({m["code_insee"] for m in monuments if m.get("code_insee")})
    proprietaires = {m["id"]: m["user_id"] for m in monuments if m.get("user_id")}
    communes_rows, offres = en_parallele(
        lambda: (
            supabase.table("communes")
            .select(
                "code_insee, nom_commune, departement, departement_num, region, region_code, "
                "population, epci_siren"
            )
            .in_("code_insee", code_insees)
            .execute()
            .data
            if code_insees
            else []
        ),
        lambda: quotas.offres_des_monuments(
            supabase, [m["id"] for m in monuments], user_id, proprietaires=proprietaires
        ),
    )

    # Batch-enrich with commune data (préservé de la version d'origine)
    population_by_code: dict[str, int | None] = {}
    communes_by_code = {c["code_insee"]: c for c in communes_rows or []}
    # Les lignes PostgREST ne sont pas typées : on resserre explicitement en
    # {str: int | None} plutôt que de propager du JSON quelconque.
    for code, row in communes_by_code.items():
        pop = row.get("population")
        population_by_code[str(code)] = pop if isinstance(pop, int) else None
    for m in monuments:
        commune_data = communes_by_code.get(m.get("code_insee"))
        if commune_data:
            m["commune"] = commune_data["nom_commune"]
            m["departement"] = commune_data["departement"]
            m["departement_num"] = commune_data["departement_num"]
            m["region"] = commune_data.get("region_code")
            m["region_label"] = commune_data.get("region")
            _attach_epci(m, commune_data)

    for m in monuments:
        m["my_role"] = role_by_id.get(m["id"])
        preview = members_by_monument.get(m["id"], [])
        m["members"] = preview
        m["member_count"] = len(preview)
        m["offre"] = as_dict(offres[m["id"]])
    return monuments, population_by_code, roles_propres


@router.get("")
def list_monuments(
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    monuments, _, _ = fetch_user_monuments(supabase, user_id)
    sign_photos(supabase, monuments)
    return monuments


@router.post("", status_code=status.HTTP_201_CREATED)
def create_monument(
    body: CreateMonumentRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    # Plafond de l'offre AVANT toute écriture : le monument gratuit est unique,
    # et la ligne créée puis refusée laisserait un bien orphelin.
    quotas.verifier_creation_monument(supabase, user_id)

    data = _normalize_dates(_snake_row(body.model_dump(exclude_none=True)))

    # Resolve code_insee from commune name, falling back to the historical INSEE
    # code (e.g. Mérimée's cog_insee_lors_de_la_protection) via communes_historique.
    data["code_insee"] = resolve_code_insee(supabase, body.commune, historical_code=body.codeInsee)

    # Remove fields not stored in monuments table
    for key in ("commune", "departement", "region", "coordonnees"):
        data.pop(key, None)

    row = {
        **data,
        "user_id": user_id,
        "photos": [],
        "completion_percentage": 0,
    }

    result = supabase.table("monuments").insert(row).execute()
    monument = result.data[0]

    # Le créateur est d'office chef de projet (owner) du projet partagé.
    supabase.table("project_members").insert(
        {"monument_id": monument["id"], "user_id": user_id, "role": "owner"}
    ).execute()

    # Compute and persist completion
    pct = _compute_completion(monument)
    supabase.table("monuments").update({"completion_percentage": pct}).eq(
        "id", monument["id"]
    ).execute()
    monument["completion_percentage"] = pct

    # Le créateur est chef de projet : renvoyer le rôle et le nombre de membres
    # dès la création, pour que l'UI propose immédiatement l'invitation d'équipe
    # (sinon `my_role` n'est peuplé qu'au prochain GET).
    enriched = _enrich_monument(supabase, monument, user_id)
    enriched["my_role"] = "owner"
    enriched["member_count"] = 1
    return enriched


@router.get("/{monument_id}")
def get_monument(
    monument_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    # Lecture élargie : l'équipe du monument, et les membres d'un de ses projets
    # (fiche sanitaire seule). `my_role` vaut None pour ces derniers — le front
    # en déduit qu'aucun onglet du monument ne leur est ouvert.
    role = require_monument_read(supabase, monument_id, user_id)
    result = supabase.table("monuments").select(COLUMNS).eq("id", monument_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Monument introuvable")
    monument = _enrich_monument(supabase, result.data, user_id)
    monument["my_role"] = role
    sign_photos(supabase, [monument])
    return monument


@router.patch("/{monument_id}")
def update_monument(
    monument_id: str,
    body: UpdateMonumentRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    require_project_access(supabase, monument_id, user_id, "co_owner")

    updates = _normalize_dates(_snake_row(body.model_dump(exclude_none=True)))

    # Re-resolve code_insee when commune changes
    if body.commune is not None:
        updates["code_insee"] = resolve_code_insee(
            supabase, body.commune, historical_code=body.codeInsee
        )

    # Remove fields not stored in monuments table
    for key in ("commune", "departement", "region", "coordonnees"):
        updates.pop(key, None)

    if not updates:
        result = (
            supabase.table("monuments").select(COLUMNS).eq("id", monument_id).single().execute()
        )
        return _enrich_monument(supabase, result.data, user_id)

    result = supabase.table("monuments").update(updates).eq("id", monument_id).execute()
    monument = result.data[0]

    # Recompute completion
    pct = _compute_completion(monument)
    supabase.table("monuments").update({"completion_percentage": pct}).eq(
        "id", monument_id
    ).execute()
    monument["completion_percentage"] = pct

    return _enrich_monument(supabase, monument, user_id)


@router.delete("/{monument_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_monument(
    monument_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    require_project_access(supabase, monument_id, user_id, "owner")
    quotas.verifier_suppression_monument(supabase, monument_id, user_id)
    supabase.table("monuments").delete().eq("id", monument_id).execute()


@router.post("/{monument_id}/photos", status_code=status.HTTP_201_CREATED)
def add_photo(
    monument_id: str,
    body: AddPhotoRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    require_project_access(supabase, monument_id, user_id, "co_owner")
    _m = supabase.table("monuments").select(COLUMNS).eq("id", monument_id).single().execute()
    if not _m.data:
        raise HTTPException(status_code=404, detail="Monument introuvable")
    monument = _m.data

    safe_url = _validate_photo_storage_path(body.url, user_id)

    new_photo = {
        "id": str(uuid.uuid4()),
        "url": safe_url,
        "legende": body.legende,
        "type": body.type,
        **({"datePhoto": body.datePhoto} if body.datePhoto else {}),
    }

    photos = cast(list, monument.get("photos") or [])
    photos.append(new_photo)

    supabase.table("monuments").update({"photos": photos}).eq("id", monument_id).execute()
    sign_photos(supabase, [{"photos": [new_photo]}])
    return new_photo


@router.put("/{monument_id}/photo-profil")
def set_photo_profil(
    monument_id: str,
    body: PhotoProfilRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """Pose (ou remplace) la photo de profil du monument.

    Une seule par monument : l'ancienne sort du tableau `photos` et son objet
    storage est effacé dans la foulée, pour ne pas laisser d'orphelin.
    """
    require_project_access(supabase, monument_id, user_id, "co_owner")
    _m = supabase.table("monuments").select(COLUMNS).eq("id", monument_id).single().execute()
    if not _m.data:
        raise HTTPException(status_code=404, detail="Monument introuvable")

    safe_url = _validate_photo_storage_path(body.url, user_id)

    photos = cast(list, _m.data.get("photos") or [])
    anciennes = [p for p in photos if p.get("type") == PHOTO_PROFIL_TYPE]
    new_photo = {
        "id": str(uuid.uuid4()),
        "url": safe_url,
        "legende": body.legende,
        "type": PHOTO_PROFIL_TYPE,
    }
    # En tête du tableau : la photo de profil est la première du monument.
    photos = [new_photo] + [p for p in photos if p.get("type") != PHOTO_PROFIL_TYPE]

    supabase.table("monuments").update({"photos": photos}).eq("id", monument_id).execute()
    for ancienne in anciennes:
        _remove_from_storage(supabase, ancienne.get("url"))

    sign_photos(supabase, [{"photos": [new_photo]}])
    return new_photo


@router.delete("/{monument_id}/photo-profil", status_code=status.HTTP_204_NO_CONTENT)
def remove_photo_profil(
    monument_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    require_project_access(supabase, monument_id, user_id, "co_owner")
    _m = supabase.table("monuments").select(COLUMNS).eq("id", monument_id).single().execute()
    if not _m.data:
        raise HTTPException(status_code=404, detail="Monument introuvable")

    photos = cast(list, _m.data.get("photos") or [])
    retirees = [p for p in photos if p.get("type") == PHOTO_PROFIL_TYPE]
    if not retirees:
        raise HTTPException(status_code=404, detail="Aucune photo de profil")

    supabase.table("monuments").update(
        {"photos": [p for p in photos if p.get("type") != PHOTO_PROFIL_TYPE]}
    ).eq("id", monument_id).execute()
    for photo in retirees:
        _remove_from_storage(supabase, photo.get("url"))


@router.delete("/{monument_id}/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_photo(
    monument_id: str,
    photo_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    require_project_access(supabase, monument_id, user_id, "co_owner")
    _m = supabase.table("monuments").select(COLUMNS).eq("id", monument_id).single().execute()
    if not _m.data:
        raise HTTPException(status_code=404, detail="Monument introuvable")
    monument = _m.data

    photos = cast(list, monument.get("photos") or [])
    updated = [p for p in photos if p["id"] != photo_id]

    if len(updated) == len(photos):
        raise HTTPException(status_code=404, detail="Photo introuvable")

    supabase.table("monuments").update({"photos": updated}).eq("id", monument_id).execute()
