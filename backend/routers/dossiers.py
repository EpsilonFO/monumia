import logging
import uuid
from datetime import UTC
from typing import Literal, Self

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, model_validator
from supabase import Client

from db import get_current_user_id, get_supabase
from routers.monuments import _enrich_monument
from services.dossier_service import create_dossier_from_aide
from services.piece_reuse import apply_reuse
from services.project_access import (
    best_role,
    can_delete_document,
    can_view_document,
    get_project_role,
    require_project_access,
)

router = APIRouter(prefix="/dossiers", tags=["dossiers"])

logger = logging.getLogger(__name__)

COLUMNS = "*"


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
    # Vocabulaire fermé : le statut part tel quel dans le JSONB de la checklist,
    # une chaîne libre y écrirait n'importe quoi (et « fourni » mal orthographié
    # ferait disparaître la pièce de la progression sans erreur).
    statut: Literal["fourni", "repris", "en_attente", "manquant"]
    document_id: str | None = None
    # `document_id: None` signifie « champ non fourni » (le front n'envoie la clé
    # que pour rattacher). Rejeter une pièce reprise demande de VIDER le champ :
    # d'où ce drapeau explicite, plutôt qu'une sémantique du null ambiguë.
    detacher: bool = False

    @model_validator(mode="after")
    def _refuse_fourni_sans_document(self) -> Self:
        """« fourni » + détachement produirait une pièce comptée dans la
        progression sans aucun document derrière : un dossier qui se déclare
        complet tout seul, ce que la conception exclut explicitement."""
        if self.statut == "fourni" and self.detacher:
            raise ValueError("Une pièce « fournie » ne peut pas être détachée de son document")
        return self


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


def _fetch_aide(supabase: Client, aide_id: str | None) -> dict | None:
    """Fiche d'aide par UUID ou slug.

    Le moteur déterministe identifie les aides par leur slug (lecture des YAML),
    donc un `aide_id` — celui du corps de requête comme celui stocké dans
    `dossiers.aide_id` — peut être l'un ou l'autre.
    """
    if not aide_id:
        return None
    query = supabase.table("aides_v3").select("*")
    query = query.eq("id", aide_id) if _is_uuid(aide_id) else query.eq("slug", aide_id)
    result = query.maybe_single().execute()
    return result.data if result else None


def _resoudre_piece_ids(supabase: Client, dossier: dict) -> tuple[list[dict], int]:
    """Re-remplit les `pieceId` absents de la checklist, depuis l'aide du dossier.

    Le `pieceId` est figé dans le JSONB au moment de la création : les dossiers
    créés avant le rattachement du corpus n'en portent aucun, et la reprise y
    serait un no-op définitif — précisément sur les dossiers pour lesquels elle
    a le plus de valeur.

    Le rapprochement est exact, pas flou : le `label` d'un item EST le
    `documents_requis[].nom` de l'aide (cf. `create_dossier_from_aide`), et l'on
    ne rapproche qu'à l'intérieur d'une même aide. Renvoie une NOUVELLE
    checklist et le nombre d'items nouvellement rattachés.
    """
    checklist = [dict(item) for item in dossier.get("checklist") or []]
    orphelins = [item for item in checklist if not item.get("pieceId")]
    if not orphelins:
        return checklist, 0

    aide = _fetch_aide(supabase, dossier.get("aide_id"))
    if not aide:
        # Aide supprimée ou renommée : rien à re-résoudre. Ce n'est pas une
        # erreur — les items déjà rattachés restent traités par la reprise.
        return checklist, 0

    documents_requis = aide.get("documents_requis") or aide.get("documentsRequis") or []
    piece_par_nom: dict[str, str] = {}
    for doc in documents_requis:
        if not isinstance(doc, dict):
            continue
        nom = doc.get("nom") or doc.get("label")
        piece_id = doc.get("piece_id") or doc.get("pieceId")
        if isinstance(nom, str) and piece_id:
            piece_par_nom[nom] = piece_id

    resolus = 0
    for item in orphelins:
        label = item.get("label")
        piece_id = piece_par_nom.get(label) if isinstance(label, str) else None
        if piece_id:
            item["pieceId"] = piece_id
            resolus += 1
    return checklist, resolus


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


def _ensure_document_visible(supabase: Client, document_id: str, user_id: str) -> None:
    """Refuse de rattacher un document que l'appelant n'a pas le droit de voir.

    `get_supabase()` fournit le client service-role : sans ce contrôle, tout
    membre pourrait rattacher — et donc, via l'estampillage, faire entrer dans
    le stock de reprise de la victime — la ligne `documents` de n'importe qui,
    y compris d'un autre projet. Un document introuvable est laissé passer
    (rien à protéger : l'écriture qui suit sur un id inexistant ne touche
    aucune ligne). Même convention que `_require_document_view` dans
    `routers/documents.py` : 404 et non 403, pour ne pas révéler l'existence
    d'un document masqué.
    """
    res = (
        supabase.table("documents")
        .select("user_id, visibility, allowed_user_ids, monument_ids")
        .eq("id", document_id)
        .maybe_single()
        .execute()
    )
    doc = res.data if res else None
    if not doc:
        return
    monument_ids = doc.get("monument_ids") or []
    # Rôle le plus élevé de l'appelant parmi les projets du document, résolu
    # projet par projet (comme `_highest_project_role` dans `routers/documents.py`)
    # plutôt que via `my_project_roles` : ce dernier balaie TOUS les projets de
    # l'appelant, coûteux et inutile ici où le document ne porte qu'une poignée
    # de `monument_ids`.
    roles = {mid: r for mid in monument_ids if (r := get_project_role(supabase, mid, user_id))}
    role = best_role(monument_ids, roles)
    if not can_view_document(
        visibility=doc.get("visibility") or "team",
        allowed_user_ids=doc.get("allowed_user_ids") or [],
        uploader_id=doc.get("user_id"),
        viewer_id=user_id,
        viewer_role=role,
    ):
        raise HTTPException(status_code=404, detail="Document introuvable")


def _recalculate_progression(dossier: dict) -> int:
    checklist: list = dossier.get("checklist") or []
    obligatoires = [c for c in checklist if c.get("obligatoire")]
    if not obligatoires:
        return 0
    fournis = [c for c in obligatoires if c.get("statut") == "fourni"]
    return round(len(fournis) / len(obligatoires) * 100)


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

    aide = _fetch_aide(supabase, body.aide_id)
    if not aide:
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
        aide=aide,
        monument=monument,
        user=user_result.data,
        travaux_prevus=travaux_labels,
    )
    dossier["user_id"] = user_id
    # Identité cohérente avec le front : on stocke l'identifiant tel qu'envoyé
    # (slug pour les aides du moteur déterministe), pas l'UUID interne aides_v3,
    # pour que le rattachement dossier↔aide (masquage de l'aide, suivi) matche.
    dossier["aide_id"] = body.aide_id

    # Pré-remplissage : les pièces déjà déposées ailleurs sont rattachées dans
    # un état « repris » à confirmer — jamais « fourni », pour qu'un dossier ne
    # se déclare pas complet sans relecture.
    #
    # La reprise est un confort, pas un prérequis : elle est sur le chemin
    # critique d'une fonctionnalité qui marchait avant elle. Une erreur
    # PostgREST, un référentiel illisible ou une table `documents` indisponible
    # ne doivent pas transformer la création de dossier en 500 ; on journalise
    # et l'on poursuit avec la checklist d'origine.
    try:
        dossier["checklist"], _ = apply_reuse(
            supabase, dossier["checklist"], body.monument_id, user_id
        )
    except Exception:
        logger.exception(
            "Reprise des pièces impossible, création du dossier poursuivie (monument=%s, aide=%s)",
            body.monument_id,
            body.aide_id,
        )

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

    # Confirmer une pièce reprise n'est pas un remplacement : le document
    # attaché ne change pas, on accepte seulement une suggestion déjà en place.
    # La garde protège contre le remplacement/retrait du document d'autrui —
    # elle ne doit donc pas s'appliquer ici. Tous les autres chemins (y compris
    # le rejet via `detacher`, qui lui retire bien le document) restent gardés.
    est_confirmation = (
        body.statut == "fourni"
        and body.document_id is None
        and not body.detacher
        and target.get("origine") == "repris"
    )

    current_doc_id = target.get("documentId")
    if current_doc_id and not est_confirmation:
        uploader_id = _document_uploader(supabase, current_doc_id)
        if uploader_id is not None and not can_delete_document(
            role, is_uploader=(uploader_id == user_id)
        ):
            raise HTTPException(status_code=403, detail="Vous ne pouvez pas modifier cette pièce")

    target["statut"] = body.statut
    if body.detacher:
        target["documentId"] = None
        target.pop("origine", None)
        target.pop("perime", None)
    elif body.document_id is not None:
        piece_id = target.get("pieceId")
        if piece_id:
            # Le client supabase est service-role (RLS inopérante) : sans ce
            # contrôle, n'importe quel membre pourrait rattacher — et donc,
            # juste après, estampiller — la ligne `documents` de n'importe qui,
            # y compris d'un autre projet. Seuls les items du référentiel
            # (porteurs d'un `pieceId`) alimentent ensuite le stock de reprise
            # par `piece_id` ; c'est ce chemin, et lui seul, qui porte le risque
            # décrit (un item hors référentiel ne peut pas empoisonner le stock
            # d'autrui, faute d'estampillage).
            _ensure_document_visible(supabase, body.document_id, user_id)
        target["documentId"] = body.document_id
        # L'item n'est plus « repris » dès qu'un document est choisi à la main.
        target.pop("origine", None)
        target.pop("perime", None)
        # Estampillage : le document incarne désormais cette pièce canonique.
        # C'est le SEUL chemin de remplissage de documents.piece_id — le stock
        # se constitue par l'usage normal, sans saisie supplémentaire.
        if piece_id:
            supabase.table("documents").update({"piece_id": piece_id}).eq(
                "id", body.document_id
            ).execute()
    elif body.statut == "fourni":
        # Confirmation d'une pièce reprise : le document reste, l'item devient
        # définitif et sort de l'état « à vérifier ».
        target.pop("origine", None)
        target.pop("perime", None)

    progression = _recalculate_progression({**dossier, "checklist": checklist})
    supabase.table("dossiers").update(
        {
            "checklist": checklist,
            "progression_pourcentage": progression,
        }
    ).eq("id", dossier_id).execute()

    return _get_dossier_or_404(supabase, dossier_id, user_id)


@router.post("/{dossier_id}/reprendre-pieces")
def reprendre_pieces(
    dossier_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """Rejoue la reprise sur un dossier existant.

    Sans cet endpoint la fonctionnalité ne servirait qu'aux nouveaux dossiers,
    alors que les utilisateurs qui ont un stock sont précisément les anciens.

    Les `pieceId` sont re-résolus depuis l'aide avant la reprise : sans cela
    l'endpoint serait un no-op définitif sur tous les dossiers créés avant le
    rattachement du corpus, c'est-à-dire sur ceux qu'il vise.

    Le résultat dépend de l'appelant : le stock est filtré par SA visibilité.

    Contrairement à la création de dossier, aucun filet ici : la reprise EST
    l'objet de l'appel, son échec doit remonter à l'utilisateur.
    """
    dossier = _require_dossier_write(supabase, dossier_id, user_id)

    checklist, resolus = _resoudre_piece_ids(supabase, dossier)
    checklist, repris = apply_reuse(supabase, checklist, dossier["monument_id"], user_id)
    # Les `pieceId` re-résolus valent la peine d'être persistés même sans
    # reprise : ils rendent la prochaine tentative immédiate.
    if repris or resolus:
        supabase.table("dossiers").update(
            {
                "checklist": checklist,
                "progression_pourcentage": _recalculate_progression(
                    {**dossier, "checklist": checklist}
                ),
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
