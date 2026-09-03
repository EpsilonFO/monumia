import contextlib
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from supabase import Client

from db import get_anon_supabase, get_current_auth_user, get_current_user_id, get_supabase

router = APIRouter(prefix="/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: str
    password: str
    prenom: str
    nom: str
    telephone: str | None = None


class RegisterCollaboratorRequest(BaseModel):
    email: str
    password: str
    prenom: str
    nom: str
    metier: str
    telephone: str | None = None


class RegisterOauthRequest(BaseModel):
    """Comme RegisterRequest, sans email/password : l'utilisateur auth existe
    déjà (créé par le provider OAuth), l'email est lu depuis le token."""

    prenom: str
    nom: str
    telephone: str | None = None


class RegisterCollaboratorOauthRequest(BaseModel):
    prenom: str
    nom: str
    metier: str
    telephone: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class OauthSessionRequest(BaseModel):
    refresh_token: str


class UpdateProfileRequest(BaseModel):
    prenom: str | None = None
    nom: str | None = None
    email: str | None = None
    telephone: str | None = None


class UpdateNotificationsRequest(BaseModel):
    urgentDeadlines: bool | None = None
    newAidesMatched: bool | None = None
    dossierUpdates: bool | None = None
    emailNotifications: bool | None = None


class ForgotPasswordRequest(BaseModel):
    email: str


# ---------------------------------------------------------------------------
# Cookie de refresh token (httpOnly : jamais lisible par le JavaScript)
# ---------------------------------------------------------------------------

REFRESH_COOKIE = "monumia_refresh"
REFRESH_COOKIE_MAX_AGE = 30 * 24 * 3600  # 30 jours, renouvelé à chaque rotation
# path="/" et non "/auth" : le path d'un cookie est comparé à l'URL vue par le
# NAVIGATEUR. En prod le front tape /api/auth/refresh (nginx retire /api avant
# de proxifier vers FastAPI qui, lui, voit /auth). Un cookie posé sur /auth ne
# serait donc jamais renvoyé sur /api/auth/* → refresh 401 → déconnexion à
# chaque réouverture. "/" couvre local (/auth) comme prod (/api/auth).
REFRESH_COOKIE_PATH = "/"


def _cookie_secure() -> bool:
    # true par défaut (prod HTTPS) ; COOKIE_SECURE=false en local http.
    return os.environ.get("COOKIE_SECURE", "true").lower() != "false"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        max_age=REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_profile(supabase: Client, user_id: str) -> dict:
    result = supabase.table("users").select("*").eq("id", user_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    profile = result.data

    # Normalize snake_case DB keys to camelCase for the frontend
    if "notification_preferences" in profile:
        profile["notificationPreferences"] = profile.pop("notification_preferences")
    if "onboarding_complete" in profile:
        profile["onboardingComplete"] = profile.pop("onboarding_complete")
    if "created_at" in profile:
        profile["createdAt"] = profile.pop("created_at")
    if "account_type" in profile:
        profile["accountType"] = profile.pop("account_type")
    # `metier` reste tel quel (déjà en une seule clé compatible)

    return profile


def _default_notification_preferences() -> dict:
    return {
        "urgentDeadlines": True,
        "newAidesMatched": True,
        "dossierUpdates": True,
        "emailNotifications": False,
    }


def _prefill_from_auth_user(auth_user) -> dict:
    """Prénom/nom/email depuis les métadonnées du provider OAuth (Google)."""
    meta = getattr(auth_user, "user_metadata", None) or {}
    prenom = (meta.get("given_name") or "").strip()
    nom = (meta.get("family_name") or "").strip()
    if not prenom and not nom:
        full = (meta.get("full_name") or meta.get("name") or "").strip()
        if full:
            parts = full.split(" ", 1)
            prenom = parts[0]
            nom = parts[1] if len(parts) > 1 else ""
    return {"email": auth_user.email, "prenom": prenom, "nom": nom}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_password(password: str) -> None:
    """Politique de mot de passe : au moins 8 caractères et 1 chiffre."""
    if len(password) < 8 or not any(c.isdigit() for c in password):
        raise HTTPException(
            status_code=400,
            detail="Le mot de passe doit contenir au moins 8 caractères et 1 chiffre.",
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    response: Response,
    anon: Client = Depends(get_anon_supabase),
    supabase: Client = Depends(get_supabase),
):
    _validate_password(body.password)
    # 1. Create auth user
    try:
        auth_response = anon.auth.sign_up(
            {
                "email": body.email,
                "password": body.password,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not auth_response.user:
        raise HTTPException(status_code=400, detail="Échec de la création du compte")

    user_id = auth_response.user.id

    # 2. Insert profile row
    profile: dict[str, Any] = {
        "id": user_id,
        "email": body.email,
        "prenom": body.prenom,
        "nom": body.nom,
        "telephone": body.telephone,
        "onboarding_complete": False,
        "notification_preferences": _default_notification_preferences(),
    }

    supabase.table("users").insert(profile).execute()

    session = auth_response.session
    if session and session.refresh_token:
        _set_refresh_cookie(response, session.refresh_token)
    return {
        "access_token": session.access_token if session else None,
        "token_type": "bearer",
        "user": _get_profile(supabase, user_id),
    }


@router.post("/register-collaborator", status_code=status.HTTP_201_CREATED)
def register_collaborator(
    body: RegisterCollaboratorRequest,
    response: Response,
    anon: Client = Depends(get_anon_supabase),
    supabase: Client = Depends(get_supabase),
):
    """Inscription allégée pour un invité : onboarding déjà terminé."""
    _validate_password(body.password)
    try:
        auth_response = anon.auth.sign_up({"email": body.email, "password": body.password})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not auth_response.user:
        raise HTTPException(status_code=400, detail="Échec de la création du compte")

    user_id = auth_response.user.id

    profile: dict[str, Any] = {
        "id": user_id,
        "email": body.email,
        "prenom": body.prenom,
        "nom": body.nom,
        "telephone": body.telephone,
        "account_type": "collaborateur",
        "metier": body.metier,
        "onboarding_complete": True,
        "notification_preferences": _default_notification_preferences(),
    }
    supabase.table("users").insert(profile).execute()

    session = auth_response.session
    if session and session.refresh_token:
        _set_refresh_cookie(response, session.refresh_token)
    return {
        "access_token": session.access_token if session else None,
        "token_type": "bearer",
        "user": _get_profile(supabase, user_id),
    }


@router.post("/login")
def login(
    body: LoginRequest,
    response: Response,
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
    except Exception as e:
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect") from e

    if not auth_response.user or not auth_response.session:
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

    user_id = auth_response.user.id

    _set_refresh_cookie(response, auth_response.session.refresh_token)
    return {
        "access_token": auth_response.session.access_token,
        "token_type": "bearer",
        "user": _get_profile(supabase, user_id),
    }


@router.get("/oauth/profile-status")
def oauth_profile_status(
    auth_user=Depends(get_current_auth_user),
    supabase: Client = Depends(get_supabase),
):
    """Après un login OAuth : le profil applicatif existe-t-il déjà ?

    exists=true  → connexion normale (le front pose la session).
    exists=false → le front envoie l'utilisateur dans l'onboarding, prérempli.
    """
    result = supabase.table("users").select("id").eq("id", auth_user.id).maybe_single().execute()
    if result is not None and result.data:
        return {"exists": True, "user": _get_profile(supabase, auth_user.id)}
    return {"exists": False, "prefill": _prefill_from_auth_user(auth_user)}


@router.post("/register-oauth", status_code=status.HTTP_201_CREATED)
def register_oauth(
    body: RegisterOauthRequest,
    auth_user=Depends(get_current_auth_user),
    supabase: Client = Depends(get_supabase),
):
    """Fin d'onboarding d'un compte créé via OAuth : crée la ligne users.

    Idempotent : une re-soumission (double clic, retry réseau) renvoie le
    profil existant au lieu d'échouer.
    """
    existing = supabase.table("users").select("id").eq("id", auth_user.id).maybe_single().execute()
    if existing is not None and existing.data:
        return {"user": _get_profile(supabase, auth_user.id)}

    profile: dict[str, Any] = {
        "id": auth_user.id,
        "email": auth_user.email,
        "prenom": body.prenom,
        "nom": body.nom,
        "telephone": body.telephone,
        "onboarding_complete": False,
        "notification_preferences": _default_notification_preferences(),
    }
    # Course entre deux soumissions : la ligne vient d'être créée par
    # l'autre requête — l'idempotence retombe sur le profil existant.
    with contextlib.suppress(Exception):
        supabase.table("users").insert(profile).execute()

    return {"user": _get_profile(supabase, auth_user.id)}


@router.post("/register-collaborator-oauth", status_code=status.HTTP_201_CREATED)
def register_collaborator_oauth(
    body: RegisterCollaboratorOauthRequest,
    auth_user=Depends(get_current_auth_user),
    supabase: Client = Depends(get_supabase),
):
    """Miroir OAuth de /register-collaborator : onboarding déjà terminé."""
    existing = supabase.table("users").select("id").eq("id", auth_user.id).maybe_single().execute()
    if existing is not None and existing.data:
        return {"user": _get_profile(supabase, auth_user.id)}

    profile: dict[str, Any] = {
        "id": auth_user.id,
        "email": auth_user.email,
        "prenom": body.prenom,
        "nom": body.nom,
        "telephone": body.telephone,
        "account_type": "collaborateur",
        "metier": body.metier,
        "onboarding_complete": True,
        "notification_preferences": _default_notification_preferences(),
    }
    # Course entre deux soumissions : la ligne vient d'être créée par
    # l'autre requête — l'idempotence retombe sur le profil existant.
    with contextlib.suppress(Exception):
        supabase.table("users").insert(profile).execute()

    return {"user": _get_profile(supabase, auth_user.id)}


@router.post("/oauth/session", status_code=status.HTTP_204_NO_CONTENT)
def oauth_session(
    body: OauthSessionRequest,
    response: Response,
    user_id: str = Depends(get_current_user_id),
):
    """Échange unique post-callback OAuth : le refresh token reçu dans le hash
    d'URL part en cookie httpOnly et ne repassera plus jamais côté client.
    Le Bearer (access token du même hash) authentifie l'appel."""
    _set_refresh_cookie(response, body.refresh_token)


@router.post("/forgot-password")
def forgot_password(
    body: ForgotPasswordRequest,
    anon: Client = Depends(get_anon_supabase),
):
    """Envoie un email de réinitialisation de mot de passe.

    Réponse toujours 200 : on ne révèle pas si l'adresse correspond à un compte.
    """
    import os

    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    # On n'expose jamais l'erreur au client (ne pas révéler si l'adresse existe).
    with contextlib.suppress(Exception):
        anon.auth.reset_password_for_email(
            body.email,
            {"redirect_to": f"{frontend_url}/reset-password"},
        )
    return {"message": "Si un compte existe pour cette adresse, un email a été envoyé."}


@router.post("/refresh")
def refresh(
    request: Request,
    response: Response,
    body: RefreshRequest | None = None,
    anon: Client = Depends(get_anon_supabase),
    supabase: Client = Depends(get_supabase),
):
    """Renouvelle la session. Le refresh token vient du cookie httpOnly ;
    le body reste accepté transitoirement (migration des sessions qui
    l'avaient encore en localStorage)."""
    refresh_token = request.cookies.get(REFRESH_COOKIE) or (body.refresh_token if body else None)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Aucun refresh token")

    try:
        auth_response = anon.auth.refresh_session(refresh_token)
    except Exception as e:
        raise HTTPException(status_code=401, detail="Refresh token invalide ou expiré") from e

    if not auth_response.session:
        raise HTTPException(status_code=401, detail="Impossible de rafraîchir la session")

    user_id = auth_response.user.id if auth_response.user else auth_response.session.user.id

    _set_refresh_cookie(response, auth_response.session.refresh_token)
    return {
        "access_token": auth_response.session.access_token,
        "token_type": "bearer",
        "user": _get_profile(supabase, user_id),
    }


_optional_bearer = HTTPBearer(auto_error=False)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    anon: Client = Depends(get_anon_supabase),
):
    """Déconnexion : efface toujours le cookie, révoque la session si possible.

    L'auth est facultative : un access token expiré ne doit pas empêcher
    d'effacer le cookie (sinon la session ressusciterait au prochain boot)."""
    with contextlib.suppress(Exception):
        anon.auth.sign_out()
    _clear_refresh_cookie(response)


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
    updates: dict[str, Any] = {k: v for k, v in body.model_dump().items() if v is not None}
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

    supabase.table("users").update({"notification_preferences": merged}).eq("id", user_id).execute()
    return _get_profile(supabase, user_id)
