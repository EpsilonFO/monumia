import contextlib
import logging
import os
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from supabase import Client

from db import get_anon_supabase, get_current_auth_user, get_current_user_id, get_supabase
from services import stripe_billing as billing
from services.roles import est_admin

logger = logging.getLogger(__name__)

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
    # Inscription venue du parcours découverte : le lien de confirmation doit
    # ramener sur l'écran de reprise du brouillon, pas sur l'espace. Un booléen
    # et non une URL — le client ne choisit pas où Supabase redirige.
    reprise: bool = False


class RegisterCollaboratorRequest(BaseModel):
    email: str
    password: str
    prenom: str
    nom: str
    metier: str
    telephone: str | None = None
    # Jeton de l'invitation d'où vient l'inscription : le lien de confirmation
    # ramène sur elle, sinon le collaborateur confirme son adresse et se
    # retrouve dans un espace vide, sans le monument qui l'avait fait venir.
    invitation: str | None = None


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


class ResendConfirmationRequest(BaseModel):
    email: str
    reprise: bool = False
    invitation: str | None = None


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

    # Administration du catalogue : un CONFORT d'affichage (le lien vers /admin
    # dans le profil, le garde de route côté SPA). L'autorité reste
    # `require_admin`, sur chaque route du router d'administration.
    profile["estAdmin"] = est_admin(supabase, user_id)

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


DETAIL_DEJA_INSCRIT = "Un compte existe déjà avec cette adresse."
DETAIL_NON_CONFIRME = (
    "Votre adresse email n'est pas encore confirmée. "
    "Ouvrez le message que nous vous avons envoyé pour activer votre compte."
)


def _erreur_inscription(exc: Exception) -> HTTPException:
    """Traduit l'échec d'un `sign_up` Supabase en réponse exploitable.

    Le cas de loin le plus fréquent est l'adresse déjà inscrite, et il mérite
    son propre statut : le front y attache un lien « Se connecter » plutôt
    qu'un toast rouge. C'est devenu vital avec le parcours découverte — le
    visiteur arrive sur l'inscription avec un brouillon complet derrière lui,
    et un message anglais sans issue lui ferait perdre tout son travail.

    Le message de la bibliothèque n'est pas un contrat : on cherche « already »
    (« User already registered », « already been registered »…) et on retombe
    sur le 400 générique pour tout le reste.
    """
    message = str(exc)
    if "already" in message.lower():
        return HTTPException(status_code=409, detail=DETAIL_DEJA_INSCRIT)
    return HTTPException(status_code=400, detail=message)


def _url_retour_confirmation(*, reprise: bool = False, invitation: str | None = None) -> str:
    """Où atterrit le lien de confirmation d'email.

    Toujours `/auth/callback` : c'est le seul écran qui sache lire les jetons du
    fragment d'URL, poser le cookie de refresh et entrer dans l'application
    (cf. `AuthCallbackPage`). L'intention voyage en paramètre de requête plutôt
    qu'en `sessionStorage`, parce que le lien s'ouvre presque toujours dans un
    AUTRE onglet — souvent sur un autre appareil — où rien du parcours n'a
    survécu.

    Le client ne fournit jamais l'URL, seulement l'intention : une redirection
    libre serait une redirection ouverte signée par notre domaine. Le jeton
    d'invitation est encodé, faute de quoi un jeton biscornu déplacerait le
    point d'atterrissage.
    """
    base = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    if invitation:
        return f"{base}/auth/callback?invitation={quote(invitation, safe='')}"
    if reprise:
        return f"{base}/auth/callback?reprise=brouillon"
    return f"{base}/auth/callback"


def _utilisateur_obfusque(auth_user) -> bool:
    """Vrai si Supabase a rendu un utilisateur FACTICE pour une adresse déjà prise.

    Confirmation d'email activée, `sign_up` ne lève plus sur une adresse déjà
    inscrite et confirmée : il rend un utilisateur sans identité, pour ne pas
    révéler l'existence du compte. Il faut reconnaître ce cas ici, sinon on
    enchaîne sur un `insert` de profil en doublon (500) au lieu du 409 sur
    lequel le front accroche son lien « Se connecter ».

    `identities` absent ou `None` n'est PAS un utilisateur factice : on ne
    conclut que sur une liste explicitement vide. Se tromper de sens coûterait
    cher — on écraserait le profil d'un compte existant.
    """
    identities = getattr(auth_user, "identities", None)
    return identities is not None and len(identities) == 0


def _profil_existe(supabase: Client, user_id: str) -> bool:
    """Le profil applicatif est-il déjà là ?

    Cas visé : une adresse inscrite mais JAMAIS confirmée qui se réinscrit.
    Supabase renvoie alors le MÊME utilisateur et relance l'email — geste
    parfaitement légitime (le premier message s'est perdu), mais le profil
    existe déjà et le réinsérer violerait la clé primaire.
    """
    result = supabase.table("users").select("id").eq("id", user_id).limit(1).execute()
    return bool(result.data)


def _reponse_inscription(
    supabase: Client,
    user_id: str,
    session,
    response: Response,
) -> dict:
    """La réponse d'une inscription, avec ou sans session.

    `access_token` NUL est le cas normal quand la confirmation d'email est
    exigée : le compte existe, mais la session n'ouvre qu'après le clic dans
    l'email. C'est ce que le front lit pour afficher « allez voir votre boîte »
    au lieu d'entrer dans l'application (un `setAuth` sans jeton poserait un
    état mi-connecté que `ProtectedRoute` rejetterait sans rien expliquer).
    """
    if session and session.refresh_token:
        _set_refresh_cookie(response, session.refresh_token)
    return {
        "access_token": session.access_token if session else None,
        "token_type": "bearer",
        "user": _get_profile(supabase, user_id),
    }


def _email_non_confirme(exc: Exception) -> bool:
    """L'échec de connexion vient-il d'une adresse non confirmée ?

    GoTrue répond « Email not confirmed » (code `email_not_confirmed`). Le
    distinguer d'un mot de passe faux est indispensable : sans ça l'utilisateur
    lit « Email ou mot de passe incorrect », ressaisit trois fois le bon mot de
    passe, puis demande une réinitialisation qui ne réglera rien.
    """
    message = str(exc).lower()
    return "not confirmed" in message or "email_not_confirmed" in message


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
                "options": {"email_redirect_to": _url_retour_confirmation(reprise=body.reprise)},
            }
        )
    except Exception as e:
        raise _erreur_inscription(e) from e

    if not auth_response.user:
        raise HTTPException(status_code=400, detail="Échec de la création du compte")
    if _utilisateur_obfusque(auth_response.user):
        raise HTTPException(status_code=409, detail=DETAIL_DEJA_INSCRIT)

    user_id = auth_response.user.id

    # Réinscription d'une adresse jamais confirmée : Supabase vient de relancer
    # l'email et rend le même utilisateur. Le profil est déjà là, l'offre déjà
    # octroyée — il n'y a plus qu'à redire d'aller voir sa boîte.
    if _profil_existe(supabase, user_id):
        return _reponse_inscription(supabase, user_id, auth_response.session, response)

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
    # Tout compte neuf repart avec l'offre du moment (cf. PLAN_A_LA_CREATION).
    billing.octroyer_offre_initiale(supabase, user_id)

    return _reponse_inscription(supabase, user_id, auth_response.session, response)


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
        auth_response = anon.auth.sign_up(
            {
                "email": body.email,
                "password": body.password,
                "options": {
                    "email_redirect_to": _url_retour_confirmation(invitation=body.invitation)
                },
            }
        )
    except Exception as e:
        raise _erreur_inscription(e) from e

    if not auth_response.user:
        raise HTTPException(status_code=400, detail="Échec de la création du compte")
    if _utilisateur_obfusque(auth_response.user):
        raise HTTPException(status_code=409, detail=DETAIL_DEJA_INSCRIT)

    user_id = auth_response.user.id

    if _profil_existe(supabase, user_id):
        return _reponse_inscription(supabase, user_id, auth_response.session, response)

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
    # Tout compte neuf repart avec l'offre du moment (cf. PLAN_A_LA_CREATION).
    billing.octroyer_offre_initiale(supabase, user_id)

    return _reponse_inscription(supabase, user_id, auth_response.session, response)


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
        # 403 et non 401 : les identifiants sont BONS, c'est l'adresse qui
        # n'est pas confirmée. Le front distingue les deux — le 403 propose de
        # renvoyer l'email, le 401 reste « email ou mot de passe incorrect ».
        if _email_non_confirme(e):
            raise HTTPException(status_code=403, detail=DETAIL_NON_CONFIRME) from e
        # Le 401 rendu au front ne distingue rien (mot de passe faux, clé API
        # invalide, Supabase injoignable) : la cause réelle n'est lisible qu'ici.
        # Jamais le mot de passe, seulement de quoi repérer une saisie altérée.
        logger.warning(
            "Connexion refusée par Supabase (%s, status=%s, code=%s) : %s | email=%r, mdp=%d car.",
            type(e).__name__,
            getattr(e, "status", None),
            getattr(e, "code", None),
            e,
            body.email,
            len(body.password),
        )
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect") from e

    if not auth_response.user or not auth_response.session:
        logger.warning(
            "Connexion sans session ni utilisateur rendus par Supabase : email=%r", body.email
        )
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
    # Même octroi que pour une inscription par mot de passe. L'appel est
    # idempotent : la course entre deux soumissions réécrit la même ligne.
    billing.octroyer_offre_initiale(supabase, auth_user.id)

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
    # Même octroi que pour une inscription par mot de passe. L'appel est
    # idempotent : la course entre deux soumissions réécrit la même ligne.
    billing.octroyer_offre_initiale(supabase, auth_user.id)

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


@router.post("/resend-confirmation")
def resend_confirmation(
    body: ResendConfirmationRequest,
    anon: Client = Depends(get_anon_supabase),
):
    """Renvoie l'email de confirmation d'inscription.

    Le premier message se perd (spam, adresse mal tapée, onglet fermé), et sans
    ce recours le compte est mort : l'adresse est prise, donc l'inscription
    répond 409, et la connexion 403. C'est le seul chemin de sortie.

    Réponse toujours 200, comme `/forgot-password` : ni l'existence du compte
    ni son état de confirmation ne se déduisent d'ici. Supabase applique en
    outre sa propre limite de fréquence, qui remonterait en erreur.
    """
    with contextlib.suppress(Exception):
        anon.auth.resend(
            {
                "type": "signup",
                "email": body.email,
                "options": {
                    "email_redirect_to": _url_retour_confirmation(
                        reprise=body.reprise, invitation=body.invitation
                    )
                },
            }
        )
    return {
        "message": "Si une confirmation est en attente pour cette adresse, un email a été envoyé."
    }


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
