"""Facturation Stripe : configuration, droits d'accès, client HTTP.

Deux offres payantes, cumulables et de portées différentes :

  • « Dossier »    — paiement unique, débloque UN projet, pour toujours.
  • « Abonnement » — récurrent mensuel, débloque TOUS les projets du compte.

Le calcul des droits vit ici plutôt que dans le routeur : c'est la seule
autorité sur « cet utilisateur a-t-il accès au détail des aides de ce projet »,
et l'onglet Aides comme la fiche d'une aide doivent lui poser la même question.

Stripe est optionnel : sans `STRIPE_SECRET_KEY`, `is_configured()` renvoie False
et la page Tarifs se rabat sur son état « bientôt disponible ». Le reste du site
fonctionne normalement — un déploiement sans clé ne casse rien.
"""

import logging
import os
import time
from typing import Any
from urllib.parse import urlparse

import stripe
from fastapi import HTTPException, Request
from supabase import Client

from config import resolve_app_origin

logger = logging.getLogger(__name__)

PLAN_DOSSIER = "dossier"
PLAN_ABONNEMENT = "abonnement"
PLANS = (PLAN_DOSSIER, PLAN_ABONNEMENT)

# Statuts Stripe qui ouvrent l'accès. `past_due` en fait partie volontairement :
# un prélèvement rejeté déclenche les relances de Stripe (plusieurs jours), et
# couper l'accès au premier échec punit un client dont la carte a simplement
# expiré. L'accès tombe quand l'abonnement passe `canceled` ou `unpaid`.
ACTIVE_SUBSCRIPTION_STATUSES = frozenset({"active", "trialing", "past_due"})


def _env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def secret_key() -> str | None:
    return _env("STRIPE_SECRET_KEY")


def webhook_secret() -> str | None:
    return _env("STRIPE_WEBHOOK_SECRET")


def price_id(plan: str) -> str | None:
    return _env("STRIPE_PRICE_DOSSIER" if plan == PLAN_DOSSIER else "STRIPE_PRICE_ABONNEMENT")


def app_url() -> str:
    return (_env("APP_URL") or "https://app.monumia.fr").rstrip("/")


def return_origin(request: Request) -> str:
    """Origine où Stripe doit renvoyer l'utilisateur après paiement.

    Déduite de la requête (en-tête `Origin`, puis `Referer`) et validée contre
    la liste blanche : un paiement lancé depuis localhost revient sur localhost,
    depuis beta sur beta, sans variable d'environnement à poser par machine.
    `APP_URL` reste le repli quand l'origine est absente ou inconnue, par
    exemple si un appel arrive sans en-tête.
    """
    origin = request.headers.get("origin")
    if not origin:
        referer = request.headers.get("referer")
        if referer:
            parsed = urlparse(referer)
            if parsed.scheme and parsed.netloc:
                origin = f"{parsed.scheme}://{parsed.netloc}"
    return resolve_app_origin(origin, app_url())


def is_configured() -> bool:
    """Vrai si le paiement peut fonctionner : clé + au moins un prix."""
    return bool(secret_key()) and any(price_id(p) for p in PLANS)


def is_test_mode() -> bool:
    key = secret_key() or ""
    return key.startswith("sk_test_")


def automatic_tax_enabled() -> bool:
    """Calcul automatique de la TVA par Stripe Tax — désactivé par défaut.

    Stripe refuse une session Checkout avec `automatic_tax` si l'adresse
    d'origine et les immatriculations fiscales ne sont pas renseignées. Le
    paiement doit fonctionner sur un compte neuf : on n'active donc Stripe Tax
    que sur demande explicite, une fois le paramétrage fait.
    """
    return os.environ.get("STRIPE_AUTOMATIC_TAX", "false").strip().lower() == "true"


def client() -> stripe.StripeClient:
    key = secret_key()
    if not key:
        # 503 et non 500 : le paiement n'est pas cassé, il n'est pas encore
        # ouvert. Le frontend distingue les deux.
        raise HTTPException(status_code=503, detail="Le paiement n'est pas encore disponible.")
    return stripe.StripeClient(key)


# ---------------------------------------------------------------------------
# Tarifs affichés — lus dans Stripe, jamais recopiés dans le code
# ---------------------------------------------------------------------------

# Le montant affiché sur /tarifs doit être celui qui sera débité. Le dupliquer
# côté code garantit qu'un jour les deux divergeront : on lit donc le prix dans
# Stripe. Cache de 5 min pour ne pas taper l'API à chaque affichage de la page.
_PRICE_CACHE_TTL = 300
_price_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _fetch_price(plan: str) -> dict[str, Any] | None:
    pid = price_id(plan)
    if not pid:
        return None

    cached = _price_cache.get(plan)
    if cached and time.monotonic() - cached[0] < _PRICE_CACHE_TTL:
        return cached[1]

    try:
        price = client().v1.prices.retrieve(pid)
    except Exception:
        # Un prix supprimé ou une clé invalide ne doit pas casser la page :
        # l'offre disparaît simplement de l'affichage.
        logger.exception("Stripe: lecture du prix %s (%s) impossible", pid, plan)
        return None

    recurring = getattr(price, "recurring", None)
    payload = {
        "plan": plan,
        "priceId": price.id,
        "amountCents": price.unit_amount,
        "currency": (price.currency or "eur").upper(),
        "interval": getattr(recurring, "interval", None) if recurring else None,
        "recurring": recurring is not None,
    }
    _price_cache[plan] = (time.monotonic(), payload)
    return payload


def public_plans() -> list[dict[str, Any]]:
    """Les offres payantes réellement vendables, prix compris."""
    return [p for p in (_fetch_price(plan) for plan in PLANS) if p is not None]


# ---------------------------------------------------------------------------
# Droits d'accès
# ---------------------------------------------------------------------------


def _has_manual_grant(supabase: Client, user_id: str) -> bool:
    """Flag historique `has_aides_access` : porte de service (beta, démos)."""
    res = (
        supabase.table("users")
        .select("has_aides_access")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    return bool(res and res.data and res.data.get("has_aides_access"))


def active_subscription(supabase: Client, user_id: str) -> dict | None:
    """Abonnement en cours du compte, ou None."""
    res = (
        supabase.table("subscriptions")
        .select("*")
        .eq("user_id", user_id)
        .in_("status", sorted(ACTIVE_SUBSCRIPTION_STATUSES))
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = (res.data if res else None) or []
    return rows[0] if rows else None


def unlocked_monument_ids(supabase: Client, user_id: str) -> list[str]:
    """Projets débloqués à l'unité, vus par cet utilisateur.

    Le déblocage porte sur le PROJET, pas sur l'acheteur : si le propriétaire a
    payé, l'architecte invité travaille sur un projet débloqué sans repayer.
    D'où la lecture par monument_id (tous acheteurs confondus) et non par
    user_id. Aucune fuite possible : la liste est bornée aux projets dont
    l'utilisateur est déjà membre.
    """
    members = (
        supabase.table("project_members").select("monument_id").eq("user_id", user_id).execute()
    )
    owned = supabase.table("monuments").select("id").eq("user_id", user_id).execute()

    accessible = {row["monument_id"] for row in (members.data or [])}
    accessible |= {row["id"] for row in (owned.data or [])}
    if not accessible:
        return []

    unlocks = (
        supabase.table("monument_unlocks")
        .select("monument_id")
        .in_("monument_id", sorted(accessible))
        .execute()
    )
    return sorted({row["monument_id"] for row in (unlocks.data or []) if row["monument_id"]})


def monument_is_unlocked(supabase: Client, monument_id: str) -> bool:
    """Un déblocage « Dossier » existe-t-il sur ce projet, par qui que ce soit ?"""
    res = (
        supabase.table("monument_unlocks")
        .select("id")
        .eq("monument_id", monument_id)
        .limit(1)
        .execute()
    )
    return bool(res and res.data)


def access_snapshot(supabase: Client, user_id: str) -> dict[str, Any]:
    """État complet des droits — la réponse de GET /billing/access.

    Le frontend s'appuie sur CET appel, et non sur le profil persisté dans le
    localStorage : un profil bricolé côté navigateur ne débloque rien.
    """
    subscription = active_subscription(supabase, user_id)
    all_access = subscription is not None or _has_manual_grant(supabase, user_id)
    return {
        "allAccess": all_access,
        # Inutile d'énumérer les projets quand tout est ouvert.
        "unlockedMonumentIds": [] if all_access else unlocked_monument_ids(supabase, user_id),
        "subscription": (
            {
                "status": subscription["status"],
                "currentPeriodEnd": subscription.get("current_period_end"),
                "cancelAtPeriodEnd": subscription.get("cancel_at_period_end", False),
            }
            if subscription
            else None
        ),
        "configured": is_configured(),
        "testMode": is_test_mode(),
    }


def has_monument_access(supabase: Client, user_id: str, monument_id: str) -> bool:
    """Autorité unique pour « peut voir le détail des aides de ce projet »."""
    if _has_manual_grant(supabase, user_id):
        return True
    if active_subscription(supabase, user_id) is not None:
        return True
    return monument_is_unlocked(supabase, monument_id)


# ---------------------------------------------------------------------------
# Client Stripe rattaché au compte
# ---------------------------------------------------------------------------


def ensure_customer(supabase: Client, user_id: str) -> str:
    """Id du Customer Stripe du compte, créé au premier paiement.

    Réutilisé ensuite : sans ça, Stripe verrait un nouveau client à chaque
    achat et le portail de facturation n'afficherait qu'un seul paiement.
    """
    res = (
        supabase.table("users")
        .select("stripe_customer_id, email, prenom, nom")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    profile = (res.data if res else None) or {}
    existing = profile.get("stripe_customer_id")
    if existing:
        return existing

    full_name = " ".join(part for part in (profile.get("prenom"), profile.get("nom")) if part)
    customer = client().v1.customers.create(
        params={
            "email": profile.get("email"),
            "name": full_name or None,
            # Permet de retrouver le compte Monumia depuis le dashboard Stripe.
            "metadata": {"user_id": user_id},
        }
    )
    supabase.table("users").update({"stripe_customer_id": customer.id}).eq("id", user_id).execute()
    return customer.id
