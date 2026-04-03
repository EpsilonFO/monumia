
from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from db import get_current_user_id, get_supabase
from services.dossier_service import create_dossier_from_aide

router = APIRouter(prefix="/dossiers", tags=["dossiers"])

COLUMNS = "*"


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
    statut: str   # 'fourni' | 'en_attente' | 'manquant'
    document_id: str | None = None


class UpdateSectionRequest(BaseModel):
    contenu: str


class AddCollaborateurRequest(BaseModel):
    email: str
    nom: str
    role: str          # 'proprietaire' | 'adjoint' | 'architecte' | 'secretaire' | 'autre'
    permissions: str   # 'lecture' | 'edition'


class AddEcheanceRequest(BaseModel):
    label: str
    date: str
    type: str   # 'ouverture' | 'limite' | 'instruction' | 'notification' | 'travaux'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_dossier_or_404(supabase: Client, dossier_id: str, user_id: str) -> dict:
    result = (
        supabase.table("dossiers")
        .select(COLUMNS)
        .eq("id", dossier_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    return result.data


def _recalculate_progression(dossier: dict) -> int:
    checklist: list = dossier.get("checklist") or []
    obligatoires = [c for c in checklist if c.get("obligatoire")]
    if not obligatoires:
        return 0
    fournis = [c for c in obligatoires if c.get("statut") == "fourni"]
    return round(len(fournis) / len(obligatoires) * 100)


STEP_TO_STATUS = {1: "brouillon", 2: "en_cours", 3: "en_cours", 4: "complet", 5: "soumis"}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("")
def list_dossiers(
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    result = (
        supabase.table("dossiers")
        .select(COLUMNS)
        .eq("user_id", user_id)
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
    monument_result = (
        supabase.table("monuments").select("*").eq("id", body.monument_id).eq("user_id", user_id).single().execute()
    )
    if not monument_result.data:
        raise HTTPException(status_code=404, detail="Monument introuvable")

    # Fetch aide
    aide_result = supabase.table("aides").select("*").eq("id", body.aide_id).single().execute()
    if not aide_result.data:
        raise HTTPException(status_code=404, detail="Aide introuvable")

    # Fetch user profile
    user_result = supabase.table("users").select("*").eq("id", user_id).single().execute()
    if not user_result.data:
        raise HTTPException(status_code=404, detail="Profil introuvable")

    dossier = create_dossier_from_aide(
        aide=aide_result.data,
        monument=monument_result.data,
        user=user_result.data,
        travaux_prevus=body.travaux_prevus,
    )
    dossier["user_id"] = user_id

    result = supabase.table("dossiers").insert(dossier).execute()
    return result.data[0]


@router.get("/{dossier_id}")
def get_dossier(
    dossier_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    return _get_dossier_or_404(supabase, dossier_id, user_id)


@router.patch("/{dossier_id}")
def update_dossier(
    dossier_id: str,
    body: UpdateDossierRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    _get_dossier_or_404(supabase, dossier_id, user_id)

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
    _get_dossier_or_404(supabase, dossier_id, user_id)
    supabase.table("dossiers").delete().eq("id", dossier_id).execute()


@router.patch("/{dossier_id}/checklist/{item_id}")
def update_checklist_item(
    dossier_id: str,
    item_id: str,
    body: UpdateChecklistItemRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    dossier = _get_dossier_or_404(supabase, dossier_id, user_id)

    checklist: list = dossier.get("checklist") or []
    updated = False
    for item in checklist:
        if item.get("id") == item_id:
            item["statut"] = body.statut
            if body.document_id is not None:
                item["documentId"] = body.document_id
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail="Item de checklist introuvable")

    progression = _recalculate_progression({**dossier, "checklist": checklist})
    supabase.table("dossiers").update({
        "checklist": checklist,
        "progression_pourcentage": progression,
    }).eq("id", dossier_id).execute()

    return _get_dossier_or_404(supabase, dossier_id, user_id)


@router.patch("/{dossier_id}/sections/{section_id}")
def update_section(
    dossier_id: str,
    section_id: str,
    body: UpdateSectionRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    dossier = _get_dossier_or_404(supabase, dossier_id, user_id)

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
    dossier = _get_dossier_or_404(supabase, dossier_id, user_id)

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

    supabase.table("dossiers").update({"collaborateurs": collaborateurs}).eq("id", dossier_id).execute()
    return new_collab


@router.delete("/{dossier_id}/collaborateurs/{collab_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_collaborateur(
    dossier_id: str,
    collab_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    dossier = _get_dossier_or_404(supabase, dossier_id, user_id)

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
    dossier = _get_dossier_or_404(supabase, dossier_id, user_id)

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


@router.patch("/{dossier_id}/echeances/{echeance_id}/toggle", status_code=status.HTTP_204_NO_CONTENT)
def toggle_echeance(
    dossier_id: str,
    echeance_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    dossier = _get_dossier_or_404(supabase, dossier_id, user_id)

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
    _get_dossier_or_404(supabase, dossier_id, user_id)

    supabase.table("dossiers").update({
        "statut": "soumis",
        "etape_actuelle": 5,
        "progression_pourcentage": 100,
        "date_soumission": datetime.now(UTC).isoformat(),
    }).eq("id", dossier_id).execute()
