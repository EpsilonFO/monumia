"""Cycle de vie des invitations à un projet (fonctions pures)."""

import secrets
from datetime import UTC, datetime, timedelta

INVITATION_TTL_DAYS = 14


def generate_invite_token() -> str:
    """Token aléatoire, url-safe, bearer du lien d'invitation."""
    return secrets.token_urlsafe(32)


def invitation_expiry_iso(now: datetime) -> str:
    """Date d'expiration ISO, TTL jours après `now`."""
    return (now + timedelta(days=INVITATION_TTL_DAYS)).isoformat()


def is_invitation_acceptable(status: str, expires_at_iso: str) -> bool:
    """True si l'invitation est encore acceptable (pending + non expirée)."""
    if status != "pending":
        return False
    try:
        expires_at = datetime.fromisoformat(expires_at_iso)
    except ValueError:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return datetime.now(UTC) < expires_at
