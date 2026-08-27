import io
import re
import unicodedata
import uuid
import zipfile
from datetime import UTC
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from supabase import Client

from db import get_current_user_id, get_supabase
from routers.monuments import _enrich_monument
from services.dossier_service import create_dossier_from_aide
from services.project_access import (
    can_delete_document,
    can_view_document,
    get_project_role,
    require_project_access,
    role_at_least,
)

router = APIRouter(prefix="/dossiers", tags=["dossiers"])

COLUMNS = "*"

STORAGE_BUCKET = "documents"


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CreateDossierRequest(BaseModel):
    monument_id: str
    aide_id: str
    travaux_prevus: list[str]


class UpdateDossierRequest(BaseModel):
    titre: str | None = None
    description: str | None = None
    statut: str | None = None
    etape_actuelle: int | None = None
    progression_pourcentage: int | None = None
    montant_estime: float | None = None
    date_soumission: str | None = None


class UpdateChecklistItemRequest(BaseModel):
    statut: str  # 'fourni' | 'en_attente' | 'manquant'
    document_id: str | None = None


class UpdateSectionRequest(BaseModel):
    contenu: str


class AddCollaborateurRequest(BaseModel):
    email: str
    nom: str
    role: str  # 'proprietaire' | 'adjoint' | 'architecte' | 'secretaire' | 'autre'
    permissions: str  # 'lecture' | 'edition'


class AddEcheanceRequest(BaseModel):
    label: str
    date: str
    type: str  # 'ouverture' | 'limite' | 'instruction' | 'notification' | 'travaux'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_dossier_or_404(supabase: Client, dossier_id: str, user_id: str) -> dict:
    """Lecture : tout membre du projet du dossier y a accès."""
    result = supabase.table("dossiers").select(COLUMNS).eq("id", dossier_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    require_project_access(supabase, result.data["monument_id"], user_id, "member")
    return result.data


def _require_dossier_write(supabase: Client, dossier_id: str, user_id: str) -> dict:
    """Écriture : réservé aux owner/co_owner du projet du dossier."""
    result = supabase.table("dossiers").select(COLUMNS).eq("id", dossier_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    require_project_access(supabase, result.data["monument_id"], user_id, "co_owner")
    return result.data


def _document_uploader(supabase: Client, document_id: str) -> str | None:
    """user_id de l'auteur d'un document, ou None s'il est introuvable."""
    res = (
        supabase.table("documents").select("user_id").eq("id", document_id).maybe_single().execute()
    )
    if res and res.data:
        return res.data.get("user_id")
    return None


def _recalculate_progression(dossier: dict) -> int:
    checklist: list = dossier.get("checklist") or []
    obligatoires = [c for c in checklist if c.get("obligatoire")]
    if not obligatoires:
        return 0
    fournis = [c for c in obligatoires if c.get("statut") == "fourni"]
    return round(len(fournis) / len(obligatoires) * 100)


def _ascii_filename(value: str, fallback: str) -> str:
    """Nom de fichier sûr : ASCII, sans séparateur de chemin, longueur bornée.

    Les libellés de pièces viennent des YAML d'aides (accents, apostrophes,
    slashs) : tel quel, un libellé créerait des dossiers dans le zip ou casserait
    l'en-tête Content-Disposition.
    """
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", " ", ascii_only)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .-")
    return cleaned[:80] or fallback


def _highest_project_role(supabase: Client, monument_ids: list | None, user_id: str) -> str | None:
    """Rôle le plus élevé de l'utilisateur parmi les projets d'un document.

    Un document peut être rattaché à plusieurs projets : la visibilité s'évalue
    avec le rôle le plus fort, comme dans le router documents.
    """
    best = None
    for mid in monument_ids or []:
        role = get_project_role(supabase, mid, user_id)
        if role is not None and (best is None or role_at_least(role, best)):
            best = role
    return best


STEP_TO_STATUS = {
    1: "brouillon",
    2: "en_cours",
    3: "en_cours",
    4: "complet",
    5: "soumis",
}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("")
def list_dossiers(
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    memberships = (
        supabase.table("project_members")
        .select("monument_id")
        .eq("user_id", user_id)
        .execute()
        .data
    )
    monument_ids = [m["monument_id"] for m in memberships]
    if not monument_ids:
        return []
    result = (
        supabase.table("dossiers")
        .select(COLUMNS)
        .in_("monument_id", monument_ids)
        .order("date_derniere_modification", desc=True)
        .execute()
    )
    return result.data


@router.post("", status_code=status.HTTP_201_CREATED)
def create_dossier(
    body: CreateDossierRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    # Validate monument ownership
    require_project_access(supabase, body.monument_id, user_id, "co_owner")
    monument_result = (
        supabase.table("monuments").select("*").eq("id", body.monument_id).single().execute()
    )
    if not monument_result.data:
        raise HTTPException(status_code=404, detail="Monument introuvable")

    # Fetch aide par UUID ou slug : le moteur déterministe identifie les aides
    # par leur slug (lecture des YAML), donc body.aide_id peut être l'un ou l'autre.
    aide_query = supabase.table("aides_v3").select("*")
    aide_query = (
        aide_query.eq("id", body.aide_id)
        if _is_uuid(body.aide_id)
        else aide_query.eq("slug", body.aide_id)
    )
    aide_result = aide_query.maybe_single().execute()
    if not aide_result or not aide_result.data:
        raise HTTPException(status_code=404, detail="Aide introuvable")

    # Fetch user profile
    user_result = supabase.table("users").select("*").eq("id", user_id).single().execute()
    if not user_result.data:
        raise HTTPException(status_code=404, detail="Profil introuvable")

    monument = _enrich_monument(supabase, monument_result.data)
    # Resolve travaux codes → labels via ref_travaux
    travaux_labels = body.travaux_prevus
    if body.travaux_prevus:
        ref_result = (
            supabase.table("ref_travaux")
            .select("code, label")
            .in_("code", body.travaux_prevus)
            .execute()
        )
        if ref_result.data:
            code_to_label = {r["code"]: r["label"] for r in ref_result.data}
            travaux_labels = [code_to_label.get(c, c) for c in body.travaux_prevus]

    dossier = create_dossier_from_aide(
        aide=aide_result.data,
        monument=monument,
        user=user_result.data,
        travaux_prevus=travaux_labels,
    )
    dossier["user_id"] = user_id
    # Identité cohérente avec le front : on stocke l'identifiant tel qu'envoyé
    # (slug pour les aides du moteur déterministe), pas l'UUID interne aides_v3,
    # pour que le rattachement dossier↔aide (masquage de l'aide, suivi) matche.
    dossier["aide_id"] = body.aide_id

    result = supabase.table("dossiers").insert(dossier).execute()
    return result.data[0]


@router.get("/{dossier_id}")
def get_dossier(
    dossier_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    return _get_dossier_or_404(supabase, dossier_id, user_id)


@router.get("/{dossier_id}/archive")
def download_dossier_archive(
    dossier_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """Zip de toutes les pièces téléversées du dossier, dans l'ordre de la checklist.

    Les pièces que l'appelant n'a pas le droit de consulter (visibilité du
    document) sont silencieusement omises — même sémantique que le cadenas
    « Réservé » de la checklist côté front. Un fichier illisible en storage est
    omis lui aussi plutôt que de faire échouer tout le téléchargement.
    """
    dossier = _get_dossier_or_404(supabase, dossier_id, user_id)

    checklist: list = dossier.get("checklist") or []
    fournies = [
        item
        for item in sorted(checklist, key=lambda c: c.get("ordre") or 0)
        if item.get("documentId")
    ]

    buffer = io.BytesIO()
    added = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for index, item in enumerate(fournies, start=1):
            doc_res = (
                supabase.table("documents")
                .select("*")
                .eq("id", item["documentId"])
                .maybe_single()
                .execute()
            )
            doc = doc_res.data if doc_res else None
            if not doc:
                continue

            role = _highest_project_role(supabase, doc.get("monument_ids"), user_id)
            if not can_view_document(
                visibility=doc.get("visibility") or "team",
                allowed_user_ids=doc.get("allowed_user_ids") or [],
                uploader_id=doc.get("user_id"),
                viewer_id=user_id,
                viewer_role=role,
            ):
                continue

            storage_path = doc.get("url") or ""
            if not storage_path or "://" in storage_path:
                continue
            try:
                content = supabase.storage.from_(STORAGE_BUCKET).download(storage_path)
            except Exception:  # storage3 lève sur erreur HTTP
                continue
            if not content:
                continue

            label = item.get("label")
            if isinstance(label, dict):
                label = label.get("nom")
            base = _ascii_filename(str(label or doc.get("nom") or ""), f"piece-{index}")
            suffix = ""
            source_name = str(doc.get("nom_fichier") or storage_path)
            if "." in source_name.rsplit("/", 1)[-1]:
                suffix = "." + _ascii_filename(source_name.rsplit(".", 1)[-1], "bin")
            archive.writestr(f"{index:02d} - {base}{suffix}", content)
            added += 1

    if added == 0:
        raise HTTPException(status_code=404, detail="Aucune pièce téléversée à télécharger")

    name = _ascii_filename(str(dossier.get("titre") or ""), "dossier") + ".zip"
    utf8_name = quote(f"{dossier.get('titre') or 'dossier'}.zip")
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{name}\"; filename*=UTF-8''{utf8_name}"
            ),
        },
    )


@router.patch("/{dossier_id}")
def update_dossier(
    dossier_id: str,
    body: UpdateDossierRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    _require_dossier_write(supabase, dossier_id, user_id)

    updates = body.model_dump(exclude_none=True)
    if not updates:
        return _get_dossier_or_404(supabase, dossier_id, user_id)

    result = supabase.table("dossiers").update(updates).eq("id", dossier_id).execute()
    return result.data[0]


@router.delete("/{dossier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dossier(
    dossier_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    _require_dossier_write(supabase, dossier_id, user_id)
    supabase.table("dossiers").delete().eq("id", dossier_id).execute()


@router.patch("/{dossier_id}/checklist/{item_id}")
def update_checklist_item(
    dossier_id: str,
    item_id: str,
    body: UpdateChecklistItemRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    # Remplir une pièce du dossier est ouvert à tout membre du projet (un
    # collaborateur peut déposer ses propres documents). En revanche, remplacer ou
    # retirer une pièce déjà fournie suit la règle des documents : seul l'auteur de
    # la pièce existante, ou un chef de projet / adjoint, peut le faire.
    dossier = _get_dossier_or_404(supabase, dossier_id, user_id)
    role = get_project_role(supabase, dossier["monument_id"], user_id)

    checklist: list = dossier.get("checklist") or []
    target = next((c for c in checklist if c.get("id") == item_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Item de checklist introuvable")

    current_doc_id = target.get("documentId")
    if current_doc_id:
        uploader_id = _document_uploader(supabase, current_doc_id)
        if uploader_id is not None and not can_delete_document(
            role, is_uploader=(uploader_id == user_id)
        ):
            raise HTTPException(status_code=403, detail="Vous ne pouvez pas modifier cette pièce")

    target["statut"] = body.statut
    if body.document_id is not None:
        target["documentId"] = body.document_id

    progression = _recalculate_progression({**dossier, "checklist": checklist})
    supabase.table("dossiers").update(
        {
            "checklist": checklist,
            "progression_pourcentage": progression,
        }
    ).eq("id", dossier_id).execute()

    return _get_dossier_or_404(supabase, dossier_id, user_id)


@router.patch("/{dossier_id}/sections/{section_id}")
def update_section(
    dossier_id: str,
    section_id: str,
    body: UpdateSectionRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    dossier = _require_dossier_write(supabase, dossier_id, user_id)

    sections: list = dossier.get("sections") or []
    updated = False
    for section in sections:
        if section.get("id") == section_id:
            section["contenu"] = body.contenu
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail="Section introuvable")

    supabase.table("dossiers").update({"sections": sections}).eq("id", dossier_id).execute()
    return _get_dossier_or_404(supabase, dossier_id, user_id)


@router.post("/{dossier_id}/collaborateurs", status_code=status.HTTP_201_CREATED)
def add_collaborateur(
    dossier_id: str,
    body: AddCollaborateurRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    import uuid

    dossier = _require_dossier_write(supabase, dossier_id, user_id)

    collaborateurs: list = dossier.get("collaborateurs") or []
    new_collab = {
        "id": str(uuid.uuid4()),
        "email": body.email,
        "nom": body.nom,
        "role": body.role,
        "permissions": body.permissions,
        "inviteAcceptee": False,
    }
    collaborateurs.append(new_collab)

    supabase.table("dossiers").update({"collaborateurs": collaborateurs}).eq(
        "id", dossier_id
    ).execute()
    return new_collab


@router.delete("/{dossier_id}/collaborateurs/{collab_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_collaborateur(
    dossier_id: str,
    collab_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    dossier = _require_dossier_write(supabase, dossier_id, user_id)

    collaborateurs: list = dossier.get("collaborateurs") or []
    updated = [c for c in collaborateurs if c.get("id") != collab_id]

    if len(updated) == len(collaborateurs):
        raise HTTPException(status_code=404, detail="Collaborateur introuvable")

    supabase.table("dossiers").update({"collaborateurs": updated}).eq("id", dossier_id).execute()


@router.post("/{dossier_id}/echeances", status_code=status.HTTP_201_CREATED)
def add_echeance(
    dossier_id: str,
    body: AddEcheanceRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    import uuid

    dossier = _require_dossier_write(supabase, dossier_id, user_id)

    echeances: list = dossier.get("echeances") or []
    new_echeance = {
        "id": str(uuid.uuid4()),
        "label": body.label,
        "date": body.date,
        "type": body.type,
        "accomplie": False,
    }
    echeances.append(new_echeance)

    supabase.table("dossiers").update({"echeances": echeances}).eq("id", dossier_id).execute()
    return new_echeance


@router.patch(
    "/{dossier_id}/echeances/{echeance_id}/toggle",
    status_code=status.HTTP_204_NO_CONTENT,
)
def toggle_echeance(
    dossier_id: str,
    echeance_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    dossier = _require_dossier_write(supabase, dossier_id, user_id)

    echeances: list = dossier.get("echeances") or []
    updated = False
    for e in echeances:
        if e.get("id") == echeance_id:
            e["accomplie"] = not e.get("accomplie", False)
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail="Échéance introuvable")

    supabase.table("dossiers").update({"echeances": echeances}).eq("id", dossier_id).execute()


@router.post("/{dossier_id}/submit", status_code=status.HTTP_204_NO_CONTENT)
def submit_dossier(
    dossier_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    from datetime import datetime

    _require_dossier_write(supabase, dossier_id, user_id)

    supabase.table("dossiers").update(
        {
            "statut": "soumis",
            "etape_actuelle": 5,
            "progression_pourcentage": 100,
            "date_soumission": datetime.now(UTC).isoformat(),
        }
    ).eq("id", dossier_id).execute()
