import os
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client

load_dotenv()

_bearer = HTTPBearer()


def get_supabase() -> Client:
    """Service-role client — full DB access, for internal operations."""
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SECRET_KEY"]
    return create_client(url, key)


def get_anon_supabase() -> Client:
    """Anon client — used for Auth operations (login, register, logout)."""
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_PUBLISHABLE_KEY"]
    return create_client(url, key)


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    supabase: Client = Depends(get_supabase),
) -> str:
    """Extract and verify the JWT, returning the authenticated user's UUID."""
    token = credentials.credentials
    try:
        user = supabase.auth.get_user(token)
        return user.user.id
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
        )
