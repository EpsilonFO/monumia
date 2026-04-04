from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from db import get_supabase, get_anon_supabase, get_current_user_id

router = APIRouter(prefix="/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: str
    password: str
    prenom: str
    nom: str
    segment: str  # 'commune' | 'prive' | 'btp'
    telephone: Optional[str] = None
    commune_code_insee: Optional[str] = None
    commune_fonction: Optional[str] = None
    prive_type_proprietaire: Optional[str] = None
    prive_regime_fiscal: Optional[str] = None
    btp: Optional[dict] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UpdateProfileRequest(BaseModel):
    prenom: Optional[str] = None
    nom: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None


class UpdateNotificationsRequest(BaseModel):
    urgentDeadlines: Optional[bool] = None
    newAidesMatched: Optional[bool] = None
    dossierUpdates: Optional[bool] = None
    emailNotifications: Optional[bool] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_profile(supabase: Client, user_id: str) -> dict:
    result = supabase.table("users").select("*").eq("id", user_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    profile = result.data

    # Build the commune object from the FK + communes reference table
    code_insee = profile.pop("commune_code_insee", None)
    fonction = profile.pop("commune_fonction", None)
    if code_insee:
        commune_result = (
            supabase.table("communes")
            .select("nom_commune, departement, region, population")
            .eq("code_insee", code_insee)
            .maybe_single()
            .execute()
        )
        commune_row = commune_result.data
        profile["commune"] = {
            "codeInsee": code_insee,
            "nom": commune_row["nom_commune"] if commune_row else code_insee,
            "departement": commune_row["departement"] if commune_row else "",
            "region": commune_row["region"] if commune_row else "",
            "population": commune_row["population"] if commune_row else 0,
            "fonction": fonction or "autre",
        }
    else:
        profile["commune"] = None

    # Build the prive object from scalar columns
    type_proprietaire = profile.pop("prive_type_proprietaire", None)
    regime_fiscal = profile.pop("prive_regime_fiscal", None)
    if type_proprietaire:
        profile["prive"] = {
            "typeProprietaire": type_proprietaire,
            "regimeFiscal": regime_fiscal,
        }
    else:
        profile["prive"] = None

    # Normalize snake_case DB keys to camelCase for the frontend
    if "notification_preferences" in profile:
        profile["notificationPreferences"] = profile.pop("notification_preferences")
    if "onboarding_complete" in profile:
        profile["onboardingComplete"] = profile.pop("onboarding_complete")
    if "created_at" in profile:
        profile["createdAt"] = profile.pop("created_at")

    return profile


def _default_notification_preferences() -> dict:
    return {
        "urgentDeadlines": True,
        "newAidesMatched": True,
        "dossierUpdates": True,
        "emailNotifications": False,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    anon: Client = Depends(get_anon_supabase),
    supabase: Client = Depends(get_supabase),
):
    # 1. Create auth user
    try:
        auth_response = anon.auth.sign_up(
            {
                "email": body.email,
                "password": body.password,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not auth_response.user:
        raise HTTPException(status_code=400, detail="Échec de la création du compte")

    user_id = auth_response.user.id

    # 2. Insert profile row
    profile: dict[str, Any] = {
        "id": user_id,
        "email": body.email,
        "prenom": body.prenom,
        "nom": body.nom,
        "segment": body.segment,
        "telephone": body.telephone,
        "commune_code_insee": body.commune_code_insee,
        "commune_fonction": body.commune_fonction,
        "prive_type_proprietaire": body.prive_type_proprietaire,
        "prive_regime_fiscal": body.prive_regime_fiscal,
        "btp": body.btp,
        "onboarding_complete": False,
        "notification_preferences": _default_notification_preferences(),
    }

    supabase.table("users").insert(profile).execute()

    session = auth_response.session
    return {
        "access_token": session.access_token if session else None,
        "refresh_token": session.refresh_token if session else None,
        "token_type": "bearer",
        "user": _get_profile(supabase, user_id),
    }


@router.post("/login")
def login(
    body: LoginRequest,
    anon: Client = Depends(get_anon_supabase),
    supabase: Client = Depends(get_supabase),
):
    try:
        auth_response = anon.auth.sign_in_with_password(
            {
                "email": body.email,
                "password": body.password,
            }
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

    if not auth_response.user or not auth_response.session:
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

    user_id = auth_response.user.id

    return {
        "access_token": auth_response.session.access_token,
        "refresh_token": auth_response.session.refresh_token,
        "token_type": "bearer",
        "user": _get_profile(supabase, user_id),
    }


@router.post("/refresh")
def refresh(
    body: RefreshRequest,
    anon: Client = Depends(get_anon_supabase),
    supabase: Client = Depends(get_supabase),
):
    try:
        auth_response = anon.auth.refresh_session(body.refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Refresh token invalide ou expiré")

    if not auth_response.session:
        raise HTTPException(
            status_code=401, detail="Impossible de rafraîchir la session"
        )

    user_id = (
        auth_response.user.id if auth_response.user else auth_response.session.user.id
    )

    return {
        "access_token": auth_response.session.access_token,
        "refresh_token": auth_response.session.refresh_token,
        "token_type": "bearer",
        "user": _get_profile(supabase, user_id),
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    user_id: str = Depends(get_current_user_id),
    anon: Client = Depends(get_anon_supabase),
):
    try:
        anon.auth.sign_out()
    except Exception:
        pass  # Already invalid token — still return 204


@router.get("/me")
def get_me(
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    return _get_profile(supabase, user_id)


@router.patch("/me")
def update_me(
    body: UpdateProfileRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    updates: dict[str, Any] = {
        k: v for k, v in body.model_dump().items() if v is not None
    }
    if not updates:
        return _get_profile(supabase, user_id)

    supabase.table("users").update(updates).eq("id", user_id).execute()
    return _get_profile(supabase, user_id)


@router.patch("/me/notifications")
def update_notifications(
    body: UpdateNotificationsRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    current = _get_profile(supabase, user_id)
    current_prefs: dict = (
        current.get("notificationPreferences") or _default_notification_preferences()
    )

    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    merged = {**current_prefs, **patch}

    supabase.table("users").update({"notification_preferences": merged}).eq(
        "id", user_id
    ).execute()
    return _get_profile(supabase, user_id)
