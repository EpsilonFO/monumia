import contextlib
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from supabase import Client

from db import get_current_user_id, get_supabase
from pieces_schema import TYPE_DOCUMENTS, load_pieces
from services.project_access import (
    allowed_visibilities,
    best_document_role,
    can_modify_document,
    can_view_document,
    max_role,
    my_scope_roles,
    projet_role_depuis,
    projet_roles_propres,
    require_project_access,
    require_projet_access,
)

router = APIRouter(prefix="/documents", tags=["documents"])

COLUMNS = "*"

STORAGE_BUCKET = "documents"
SIGNED_URL_EXPIRY = 7 * 24 * 60 * 60  # 7 jours, en secondes


def _validate_storage_path(path: str, user_id: str) -> str:
    """Ensure a document storage path is scoped to the calling user's folder.

    The frontend stores files at "<user_id>/<random>.<ext>" and sends the
    relative path. Reject anything else: full URLs, traversal, or other users.
    """
    if not path or not isinstance(path, str):
        raise HTTPException(status_code=400, detail="Chemin de fichier invalide")
    if "://" in path or path.startswith("/") or ".." in path.split("/"):
        raise HTTPException(status_code=400, detail="Chemin de fichier invalide")
    expected_prefix = f"{user_id}/"
    if not path.startswith(expected_prefix):
        raise HTTPException(status_code=403, detail="Chemin de fichier non autorisé")
    return path


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CreateDocumentRequest(BaseModel):
    nom: str
    nom_fichier: str
    type: str
    tags: list[str] = []
    taille_fichier: int
    mime_type: str
    url: str
    monument_ids: list[str] = []
    # Backward compat: accept single monument_id and convert to monument_ids
    monument_id: str | None = None
    # Rattachement à des PROJETS de travaux : un document déposé dans l'onglet
    # Documents d'un chantier n'est visible que de son équipe.
    projet_ids: list[str] = []
    date_document: str | None = None
    description: str | None = None
    visibility: str | None = None
    allowed_user_ids: list[str] = []
    # La pièce du référentiel (data/pieces.yaml) que ce fichier incarne, quand
    # il est déposé depuis « À déposer pour vos aides ». C'est l'étiquette qui
    # le fait reprendre dans chaque dossier qui la demande (services/piece_reuse).
    piece_id: str | None = None

    @field_validator("type")
    @classmethod
    def _type_connu(cls, v: str) -> str:
        return _valider_type(v)

    @field_validator("piece_id")
    @classmethod
    def _piece_connue(cls, v: str | None) -> str | None:
        # Une étiquette inconnue ne serait reprise par aucun dossier : mieux vaut
        # un refus net qu'un document qui ne sert à rien sans le dire.
        if v is not None and v not in load_pieces():
            raise ValueError(f"pièce inconnue « {v} »")
        return v


def _valider_type(v: str) -> str:
    """Le type doit exister dans l'enum `document_type` : sans ce contrôle, la
    base refuse l'insertion et la route répond 500 au lieu de 422."""
    if v not in TYPE_DOCUMENTS:
        raise ValueError(f"type de document inconnu « {v} »")
    return v


class UpdateDocumentRequest(BaseModel):
    nom: str | None = None
    type: str | None = None
    tags: list[str] | None = None
    date_document: str | None = None
    description: str | None = None
    visibility: str | None = None
    allowed_user_ids: list[str] | None = None

    @field_validator("type")
    @classmethod
    def _type_connu(cls, v: str | None) -> str | None:
        return None if v is None else _valider_type(v)


class AddToProjectsRequest(BaseModel):
    monument_ids: list[str] = []
    projet_ids: list[str] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_document_any(supabase: Client, document_id: str) -> dict:
    result = supabase.table("documents").select(COLUMNS).eq("id", document_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Document introuvable")
    return result.data


def _require_document_read(supabase: Client, document_id: str, user_id: str) -> dict:
    """Lecture : l'auteur du document, ou tout membre d'un monument / projet où il pend."""
    doc = _get_document_any(supabase, document_id)
    if doc.get("user_id") == user_id:
        return doc
    if _highest_project_role(supabase, doc, user_id) is not None:
        return doc
    raise HTTPException(status_code=404, detail="Document introuvable")


def _require_document_view(supabase: Client, document_id: str, user_id: str) -> dict:
    """Consultation : l'auteur, le chef de projet, ou selon la visibilité du document.

    Renvoie 404 (et non 403) pour ne pas révéler l'existence d'un document masqué.
    """
    doc = _get_document_any(supabase, document_id)
    role = _highest_project_role(supabase, doc, user_id)
    if can_view_document(
        visibility=doc.get("visibility") or "team",
        allowed_user_ids=doc.get("allowed_user_ids") or [],
        uploader_id=doc.get("user_id"),
        viewer_id=user_id,
        viewer_role=role,
    ):
        return doc
    raise HTTPException(status_code=404, detail="Document introuvable")


def _highest_project_role(supabase: Client, doc: dict, user_id: str) -> str | None:
    """Rôle le plus élevé du viewer sur ce document — monuments ET projets confondus."""
    monument_roles, projet_roles = my_scope_roles(supabase, user_id)
    return best_document_role(
        doc.get("monument_ids"), doc.get("projet_ids"), monument_roles, projet_roles
    )


def _can_modify(doc: dict, role: str | None, user_id: str) -> bool:
    """Vrai si `user_id` (rôle `role`) peut modifier/supprimer/déplacer `doc`.

    Exige le droit de consultation : un adjoint exclu d'un document « personnes
    choisies » ne peut donc rien en faire.
    """
    return can_modify_document(
        visibility=doc.get("visibility") or "team",
        allowed_user_ids=doc.get("allowed_user_ids") or [],
        uploader_id=doc.get("user_id"),
        viewer_id=user_id,
        viewer_role=role,
    )


def _resolve_visibility(
    requested: str | None,
    allowed_user_ids: list[str],
    role: str | None,
    *,
    has_project: bool,
) -> tuple[str, list[str]]:
    """Normalise/valide la visibilité demandée selon le rôle de l'auteur.

    Document sans projet → 'team' (pas de contexte de partage). Sinon, défaut
    SÛR : 'responsables' (chef + adjoints) pour tout le monde — un document
    fraîchement déposé n'est jamais visible par toute l'équipe tant que l'auteur
    ne l'a pas explicitement décidé (popup « Gérer l'accès » au dépôt). La liste
    `allowed_user_ids` n'est conservée que pour 'custom'.
    """
    if not has_project:
        return "team", []
    visibility = requested or "responsables"
    if visibility not in allowed_visibilities(role):
        raise HTTPException(status_code=422, detail="Visibilité non autorisée pour votre rôle")
    return visibility, (list(allowed_user_ids) if visibility == "custom" else [])


def _merge_ids(existing: list[str], new: list[str]) -> list[str]:
    """Les ids existants plus les nouveaux, ordre préservé, sans doublon.

    Rattacher un document à un monument ou à un projet associe le *même*
    document — jamais de copie : on allonge simplement le tableau.
    """
    merged = list(existing)
    for mid in new:
        if mid not in merged:
            merged.append(mid)
    return merged


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _should_auto_trash(
    monument_ids: list | None, projet_ids: list | None, dossiers_utilises: list | None
) -> bool:
    """Vrai si le document ne pend plus à RIEN (monument, projet, dossier) → corbeille."""
    return not (monument_ids or []) and not (projet_ids or []) and not (dossiers_utilises or [])


def _filter_visible(
    rows: list[dict],
    user_id: str,
    monument_roles: dict[str, str],
    projet_roles: dict[str, str],
) -> list[dict]:
    """Ne garde que les documents que `user_id` a le droit de voir (règle existante)."""
    return [
        r
        for r in rows
        if can_view_document(
            visibility=r.get("visibility") or "team",
            allowed_user_ids=r.get("allowed_user_ids") or [],
            uploader_id=r.get("user_id"),
            viewer_id=user_id,
            viewer_role=best_document_role(
                r.get("monument_ids"), r.get("projet_ids"), monument_roles, projet_roles
            ),
        )
    ]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("")
def list_documents(
    monument_id: str | None = Query(None),
    projet_id: str | None = Query(None),
    type: str | None = Query(None),
    trashed: bool = Query(False),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """Documents d'un monument, d'un projet, ou tout ce que je peux voir.

    Les deux périmètres suivent les deux niveaux de partage, et ne sont donc pas
    symétriques : `?projet_id=` ne rend que les pièces du chantier, jamais celles
    du bien (l'équipe d'un projet n'y a pas droit) ; `?monument_id=` rend les
    pièces du bien ET celles de tous ses chantiers, que son équipe voit déjà.
    """
    if projet_id:
        _, role = require_projet_access(supabase, projet_id, user_id, "member")
        query = (
            supabase.table("documents")
            .select(COLUMNS)
            .contains("projet_ids", [projet_id])
            .is_("trashed_at", "null")
            .order("date_upload", desc=True)
        )
        if type:
            query = query.eq("type", type)
        rows = query.execute().data or []
        return [
            r
            for r in rows
            if can_view_document(
                visibility=r.get("visibility") or "team",
                allowed_user_ids=r.get("allowed_user_ids") or [],
                uploader_id=r.get("user_id"),
                viewer_id=user_id,
                viewer_role=role,
            )
        ]

    if monument_id:
        # Réservé à l'équipe du MONUMENT : un membre d'un seul de ses projets
        # n'a rien à faire dans les pièces du bien.
        role = require_project_access(supabase, monument_id, user_id, "member")
        # Les pièces des chantiers y figurent aussi, SANS être rattachées au
        # monument : les retirer du projet les retire d'ici, et l'équipe d'un
        # projet ne les voit pas pour autant pendre au bien.
        projets = (
            supabase.table("projets")
            .select("id, user_id")
            .eq("monument_id", monument_id)
            .execute()
            .data
        ) or []
        clauses = [f"monument_ids.cs.{{{monument_id}}}"]
        if projets:
            clauses.append(f"projet_ids.ov.{{{','.join(str(p['id']) for p in projets)}}}")
        query = (
            supabase.table("documents")
            .select(COLUMNS)
            .or_(",".join(clauses))
            .is_("trashed_at", "null")
            .order("date_upload", desc=True)
        )
        if type:
            query = query.eq("type", type)
        rows = query.execute().data or []
        # Rôle EFFECTIF sur chaque chantier : celui du monument, relevé au besoin
        # par une appartenance propre au projet (même règle que `max_role`).
        propres = projet_roles_propres(supabase, user_id) if projets else {}
        projet_roles = {
            str(p["id"]): r
            for p in projets
            if (r := projet_role_depuis(p, role, propres, user_id)) is not None
        }
        return _filter_visible(rows, user_id, {monument_id: role}, projet_roles)

    # Vue « Mes documents » : tout ce que je peux voir (mes uploads + les pièces
    # des monuments et des projets où je suis membre), filtré par les droits de
    # consultation.
    monument_roles, projet_roles = my_scope_roles(supabase, user_id)

    if trashed:
        # Corbeille personnelle : uniquement MES documents jetés.
        query = (
            supabase.table("documents")
            .select(COLUMNS)
            .eq("user_id", user_id)
            .not_.is_("trashed_at", "null")
        )
        if type:
            query = query.eq("type", type)
        return query.order("date_upload", desc=True).execute().data or []

    query = supabase.table("documents").select(COLUMNS).is_("trashed_at", "null")
    clauses = [f"user_id.eq.{user_id}"]
    if monument_roles:
        clauses.append(f"monument_ids.ov.{{{','.join(monument_roles)}}}")
    if projet_roles:
        clauses.append(f"projet_ids.ov.{{{','.join(projet_roles)}}}")
    query = query.or_(",".join(clauses))
    if type:
        query = query.eq("type", type)
    rows = query.order("date_upload", desc=True).execute().data or []
    return _filter_visible(rows, user_id, monument_roles, projet_roles)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_document(
    body: CreateDocumentRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    # Merge monument_id (single, backward compat) into monument_ids
    monument_ids = list(body.monument_ids)
    if body.monument_id and body.monument_id not in monument_ids:
        monument_ids.append(body.monument_id)
    projet_ids = list(body.projet_ids)

    # Accès (membre suffit pour déposer) + rôle le plus élevé sur les rattachements.
    top_role: str | None = None
    for mid in monument_ids:
        top_role = max_role(top_role, require_project_access(supabase, mid, user_id, "member"))
    for pid in projet_ids:
        _, r = require_projet_access(supabase, pid, user_id, "member")
        top_role = max_role(top_role, r)

    visibility, allowed_ids = _resolve_visibility(
        body.visibility,
        body.allowed_user_ids,
        top_role,
        has_project=bool(monument_ids or projet_ids),
    )

    # The client uploads to <user_id>/... in storage, then submits the path here.
    safe_path = _validate_storage_path(body.url, user_id)

    payload = body.model_dump(
        exclude_none=True, exclude={"monument_id", "url", "visibility", "allowed_user_ids"}
    )
    row = {
        **payload,
        "url": safe_path,
        "monument_ids": monument_ids,
        "projet_ids": projet_ids,
        "user_id": user_id,
        "dossiers_utilises": [],
        "visibility": visibility,
        "allowed_user_ids": allowed_ids,
    }

    result = supabase.table("documents").insert(row).execute()
    return result.data[0]


@router.get("/{document_id}")
def get_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    return _require_document_view(supabase, document_id, user_id)


@router.get("/{document_id}/signed-url")
def get_document_signed_url(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """URL signée pour consulter un document.

    La signature est faite côté serveur avec le client service-role : elle
    contourne la RLS storage (restreinte au dossier du dépositaire) afin que
    *tout membre* d'un projet du document — pas seulement son auteur — puisse le
    consulter. L'accès est contrôlé au niveau applicatif par _require_document_view.
    """
    doc = _require_document_view(supabase, document_id, user_id)
    storage_path = doc.get("url") or ""
    if not storage_path or "://" in storage_path:
        raise HTTPException(status_code=400, detail="Chemin de fichier invalide")
    try:
        res = supabase.storage.from_(STORAGE_BUCKET).create_signed_url(
            storage_path, SIGNED_URL_EXPIRY
        )
    except Exception as exc:  # storage3 lève sur erreur HTTP
        raise HTTPException(
            status_code=502, detail="Impossible de générer le lien du document"
        ) from exc
    signed = res.get("signedURL") or res.get("signedUrl")
    if not signed:
        raise HTTPException(status_code=502, detail="Lien du document indisponible")
    return {"signed_url": signed}


@router.patch("/{document_id}")
def update_document(
    document_id: str,
    body: UpdateDocumentRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    doc = _get_document_any(supabase, document_id)
    role = _highest_project_role(supabase, doc, user_id)
    if not _can_modify(doc, role, user_id):
        raise HTTPException(status_code=403, detail="Vous ne pouvez pas modifier ce document")

    updates = body.model_dump(exclude_none=True)

    # Visibilité : valider selon le rôle, et purger la liste hors mode 'custom'.
    if "visibility" in updates or "allowed_user_ids" in updates:
        new_vis = updates.get("visibility", doc.get("visibility") or "team")
        if new_vis not in allowed_visibilities(role):
            raise HTTPException(status_code=422, detail="Visibilité non autorisée pour votre rôle")
        updates["visibility"] = new_vis
        updates["allowed_user_ids"] = (
            updates.get("allowed_user_ids", doc.get("allowed_user_ids") or [])
            if new_vis == "custom"
            else []
        )

    if not updates:
        return doc

    result = supabase.table("documents").update(updates).eq("id", document_id).execute()
    return result.data[0]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    doc = _get_document_any(supabase, document_id)
    uploader_id = doc.get("user_id")

    # Suppression : l'auteur, ou un owner/co_owner POUVANT CONSULTER le document
    # (un adjoint exclu d'un doc « personnes choisies » ne peut rien faire). Un
    # simple membre ne peut supprimer que ses propres documents.
    role = _highest_project_role(supabase, doc, user_id)
    if not _can_modify(doc, role, user_id):
        raise HTTPException(status_code=403, detail="Vous ne pouvez pas supprimer ce document")

    # Le fichier est stocké sous "<uploader_id>/..." — valider contre l'auteur, pas l'appelant.
    storage_path = doc.get("url", "") or ""
    safe_path = None
    if (
        uploader_id
        and storage_path.startswith(f"{uploader_id}/")
        and ".." not in storage_path.split("/")
    ):
        safe_path = storage_path
    _detacher_des_checklists(supabase, document_id)
    supabase.table("documents").delete().eq("id", document_id).execute()
    # Le stockage en DERNIER : un échec à mi-chemin dans l'autre ordre laisse
    # une ligne vivante dont le fichier n'existe plus — aperçu mort, suppression
    # qui re-échoue à chaque essai. Un objet orphelin dans le bucket est, lui,
    # inoffensif.
    if safe_path:
        with contextlib.suppress(Exception):
            supabase.storage.from_(STORAGE_BUCKET).remove([safe_path])


@router.post("/{document_id}/link/{dossier_id}", status_code=status.HTTP_204_NO_CONTENT)
def link_to_dossier(
    document_id: str,
    dossier_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    doc = _require_document_view(supabase, document_id, user_id)

    dossier = (
        supabase.table("dossiers")
        .select("id, projet_id")
        .eq("id", dossier_id)
        .maybe_single()
        .execute()
    )
    if not dossier or not dossier.data:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    # Tout membre du PROJET peut rattacher au dossier un document qu'il peut
    # consulter (le sien, typiquement) — le dépôt de pièces n'est pas réservé aux
    # chefs, et un collaborateur invité sur le seul chantier doit pouvoir le faire.
    require_projet_access(supabase, dossier.data["projet_id"], user_id, "member")

    dossiers: list = doc.get("dossiers_utilises") or []
    if dossier_id not in dossiers:
        dossiers.append(dossier_id)
        supabase.table("documents").update({"dossiers_utilises": dossiers}).eq(
            "id", document_id
        ).execute()


@router.delete("/{document_id}/link/{dossier_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_from_dossier(
    document_id: str,
    dossier_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    doc = _require_document_read(supabase, document_id, user_id)

    dossier = (
        supabase.table("dossiers")
        .select("id, projet_id")
        .eq("id", dossier_id)
        .maybe_single()
        .execute()
    )
    if dossier and dossier.data:
        # Retirer une pièce d'un dossier suit la règle de modification des documents :
        # l'auteur de la pièce, ou un chef de projet / adjoint POUVANT la consulter.
        _, role = require_projet_access(supabase, dossier.data["projet_id"], user_id, "member")
        if not _can_modify(doc, role, user_id):
            raise HTTPException(
                status_code=403, detail="Vous ne pouvez pas retirer cette pièce du dossier"
            )

    dossiers: list = doc.get("dossiers_utilises") or []
    updated = [d for d in dossiers if d != dossier_id]

    patch: dict = {"dossiers_utilises": updated}
    if _should_auto_trash(doc.get("monument_ids"), doc.get("projet_ids"), updated):
        patch["trashed_at"] = _now_iso()
    supabase.table("documents").update(patch).eq("id", document_id).execute()


@router.post("/{document_id}/projects")
def add_document_to_projects(
    document_id: str,
    body: AddToProjectsRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """Rattache un document existant à d'autres monuments et / ou projets.

    On allonge les tableaux `monument_ids` / `projet_ids` : le même fichier et la
    même ligne servent partout, aucune copie n'est jamais faite.
    """
    if not body.monument_ids and not body.projet_ids:
        raise HTTPException(status_code=400, detail="Aucune cible fournie")

    # Accès partagé : seul quelqu'un pouvant consulter le document peut le repartager.
    source = _require_document_view(supabase, document_id, user_id)

    # Tout membre d'une cible peut y associer le document (modèle lien, pas de copie).
    for mid in body.monument_ids:
        require_project_access(supabase, mid, user_id, "member")
    for pid in body.projet_ids:
        require_projet_access(supabase, pid, user_id, "member")

    updates: dict = {}
    if body.monument_ids:
        updates["monument_ids"] = _merge_ids(source.get("monument_ids") or [], body.monument_ids)
    if body.projet_ids:
        updates["projet_ids"] = _merge_ids(source.get("projet_ids") or [], body.projet_ids)

    result = supabase.table("documents").update(updates).eq("id", document_id).execute()
    return result.data[0]


def _detacher_des_checklists(supabase: Client, document_id: str) -> None:
    """Détache un document de toutes les checklists qui le référencent.

    Jeter ou supprimer un document vide `dossiers_utilises` de SON côté, mais
    les checklists des dossiers (JSONB) pointent toujours vers lui : la pièce
    resterait « fournie » avec un fichier fantôme, que le front afficherait
    verrouillée (« Réservé ») sans plus aucune action possible. Les pièces
    concernées repassent à « manquant » — la reprise pourra proposer un autre
    fichier. La recherche par `@>` couvre aussi les pièces simplement
    « reprises », que `dossiers_utilises` ne connaît pas (le lien au dossier ne
    se crée qu'à la confirmation).
    """
    # Import local : documents → dossiers serait un cycle au niveau module
    # (dossiers importe déjà des helpers de routers), et seul ce recalcul est
    # nécessaire ici.
    from routers.dossiers import _recalculate_progression

    rows = (
        supabase.table("dossiers")
        .select("id, checklist")
        # Chaîne JSON impérativement : postgrest-py sérialise une LISTE avec
        # ','.join(...), qui lève TypeError sur des dicts — l'endpoint entier
        # répondait 500 (« failed to fetch » côté client).
        .contains("checklist", json.dumps([{"documentId": document_id}]))
        .execute()
        .data
        or []
    )
    for dossier in rows:
        checklist = dossier.get("checklist") or []
        modifie = False
        for item in checklist:
            if item.get("documentId") == document_id:
                item["documentId"] = None
                if item.get("statut") in ("fourni", "repris"):
                    item["statut"] = "manquant"
                item.pop("origine", None)
                item.pop("perime", None)
                modifie = True
        if modifie:
            supabase.table("dossiers").update(
                {
                    "checklist": checklist,
                    "progression_pourcentage": _recalculate_progression({"checklist": checklist}),
                }
            ).eq("id", dossier["id"]).execute()


@router.post("/{document_id}/trash")
def trash_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """Mettre un document à la corbeille : le détacher de tous ses projets/dossiers
    et poser `trashed_at`. Récupérable via /restore, supprimable définitivement via DELETE."""
    doc = _get_document_any(supabase, document_id)
    role = _highest_project_role(supabase, doc, user_id)
    if not _can_modify(doc, role, user_id):
        raise HTTPException(status_code=403, detail="Vous ne pouvez pas supprimer ce document")
    _detacher_des_checklists(supabase, document_id)
    patch = {
        "monument_ids": [],
        "projet_ids": [],
        "dossiers_utilises": [],
        "trashed_at": _now_iso(),
    }
    result = supabase.table("documents").update(patch).eq("id", document_id).execute()
    return result.data[0]


@router.post("/{document_id}/restore")
def restore_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """Restaurer un document de la corbeille (revient en « Sans projet »)."""
    doc = _get_document_any(supabase, document_id)
    if doc.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Seul l'auteur peut restaurer ce document")
    result = (
        supabase.table("documents").update({"trashed_at": None}).eq("id", document_id).execute()
    )
    return result.data[0]


@router.delete("/{document_id}/projects/{monument_id}")
def remove_document_from_project(
    document_id: str,
    monument_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """Retirer un document d'UN projet. Si c'était sa dernière attache (plus aucun
    projet ni dossier), il part automatiquement en corbeille. Renvoie le document à jour."""
    doc = _get_document_any(supabase, document_id)
    role = _highest_project_role(supabase, doc, user_id)
    if not _can_modify(doc, role, user_id):
        raise HTTPException(
            status_code=403, detail="Vous ne pouvez pas retirer ce document du monument"
        )

    monuments = [m for m in (doc.get("monument_ids") or []) if m != monument_id]
    patch: dict = {"monument_ids": monuments}
    if _should_auto_trash(monuments, doc.get("projet_ids"), doc.get("dossiers_utilises")):
        patch["trashed_at"] = _now_iso()
    result = supabase.table("documents").update(patch).eq("id", document_id).execute()
    return result.data[0]


@router.delete("/{document_id}/projets/{projet_id}")
def remove_document_from_projet(
    document_id: str,
    projet_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """Retirer un document d'UN projet de travaux. Si c'était sa dernière attache
    (plus aucun monument, projet ni dossier), il part en corbeille."""
    doc = _get_document_any(supabase, document_id)
    role = _highest_project_role(supabase, doc, user_id)
    if not _can_modify(doc, role, user_id):
        raise HTTPException(
            status_code=403, detail="Vous ne pouvez pas retirer ce document du projet"
        )

    projets = [p for p in (doc.get("projet_ids") or []) if p != projet_id]
    patch: dict = {"projet_ids": projets}
    if _should_auto_trash(doc.get("monument_ids"), projets, doc.get("dossiers_utilises")):
        patch["trashed_at"] = _now_iso()
    result = supabase.table("documents").update(patch).eq("id", document_id).execute()
    return result.data[0]
