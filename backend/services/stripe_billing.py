"""Facturation Stripe : configuration, offres détenues, client HTTP.

Deux offres payantes, toutes deux des abonnements mensuels, et la seconde
contient la première :

  • « Veille »          — projets illimités, une équipe, échéancier, aides à
                          venir, emails.
  • « Multi-monuments » — tout cela, plus les monuments illimités et le
                          tableau de bord.

Aucune des deux ne se vend en libre-service aujourd'hui (`PLANS_VENDABLES` est
vide) : la page Tarifs n'affiche pas de montant et renvoie vers un courrier.
Stripe reste l'outil de FACTURATION — abonnement créé dans le dashboard, webhook
qui l'enregistre, portail client — mais plus le tunnel de vente.

Ce module est la seule autorité sur « quelles offres ce compte détient ». Ce
que chaque offre ouvre est décrit ailleurs, dans `services/offres.py` : la table
des droits est pure et se lit sans base de données, ce module ne fait que la
résoudre pour un utilisateur donné.

Stripe est optionnel : sans `STRIPE_SECRET_KEY`, `is_configured()` renvoie False
et la page Tarifs se rabat sur son état « bientôt disponible ». Le reste du site
fonctionne normalement — un déploiement sans clé ne casse rien, et l'offre
gratuite y est pleinement utilisable.
"""

import logging
import os
import time
from collections.abc import Iterable
from typing import Any

import stripe
from fastapi import HTTPException, Request
from supabase import Client

from config import request_app_origin
from services.offres import (
    PLAN_MULTI_MONUMENTS,
    PLAN_VEILLE,
    PLANS,
    PLANS_VENDABLES,
    Offre,
    as_dict,
    offre_pour,
)

__all__ = [
    "PLANS",
    "PLANS_VENDABLES",
    "PLAN_MULTI_MONUMENTS",
    "PLAN_VEILLE",
]

logger = logging.getLogger(__name__)

# Variable d'environnement portant le prix Stripe de chaque offre.
_PRICE_ENV = {
    PLAN_VEILLE: "STRIPE_PRICE_VEILLE",
    PLAN_MULTI_MONUMENTS: "STRIPE_PRICE_MULTI_MONUMENTS",
}

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
    env = _PRICE_ENV.get(plan)
    return _env(env) if env else None


def plan_pour_price(price: str | None) -> str | None:
    """Offre correspondant à un id de prix Stripe.

    Repli quand un abonnement arrive sans nos métadonnées (événement rejoué
    depuis un vieux payload, abonnement créé à la main dans le dashboard
    Stripe) : le prix, lui, est toujours là.

    C'est le rôle qui reste aux `STRIPE_PRICE_*` maintenant que rien ne se vend
    en libre-service : reconnaître l'offre d'un abonnement créé à la main dans
    le dashboard. Un prix négocié client par client n'y figure pas, et c'est
    alors `subscriptions.plan` qu'il faut renseigner à l'ouverture.
    """
    if not price:
        return None
    return next((plan for plan in PLANS if price_id(plan) == price), None)


def app_url() -> str:
    return (_env("APP_URL") or "https://app.monumia.fr").rstrip("/")


def return_origin(request: Request) -> str:
    """Origine où Stripe doit renvoyer l'utilisateur après paiement.

    Même règle que pour les liens d'invitation, d'où le helper partagé dans
    `config` : `APP_URL` reste le repli quand l'origine est absente ou inconnue.
    """
    return request_app_origin(request, app_url())


def is_configured() -> bool:
    """Vrai si un paiement en libre-service peut fonctionner : clé + un prix.

    Faux tant que `PLANS_VENDABLES` est vide, donc faux aujourd'hui : les deux
    offres se négocient. Ce n'est PAS un indicateur de « Stripe est branché » —
    la facturation d'une offre négociée, elle, n'a besoin que de la clé.
    """
    return bool(secret_key()) and any(price_id(p) for p in PLANS_VENDABLES)


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
    """Les offres réellement achetables en ligne, prix compris.

    Vide tant que `PLANS_VENDABLES` l'est : sans prix public, il n'y a rien à
    lire dans Stripe, et la page Tarifs affiche ses cartes « sur demande » sans
    rien attendre d'ici.
    """
    return [p for p in (_fetch_price(plan) for plan in PLANS_VENDABLES) if p is not None]


# ---------------------------------------------------------------------------
# Droits d'accès
# ---------------------------------------------------------------------------


def active_subscriptions(supabase: Client, user_id: str) -> list[dict]:
    """Les abonnements en cours du compte, du plus récent au plus ancien.

    Plusieurs lignes sont possibles : une montée de Veille vers Multi-monuments
    laisse les deux abonnements actifs le temps que le premier arrive à son
    terme. On les rend tous — ne garder que le dernier retirerait un droit que
    le client paye encore.
    """
    res = (
        supabase.table("subscriptions")
        .select("*")
        .eq("user_id", user_id)
        .in_("status", sorted(ACTIVE_SUBSCRIPTION_STATUSES))
        .order("created_at", desc=True)
        .execute()
    )
    return (res.data if res else None) or []


def active_subscription(supabase: Client, user_id: str) -> dict | None:
    """Le plus récent abonnement en cours, ou None.

    Reste utile là où il ne s'agit pas de calculer un droit mais de répondre
    « ce compte est-il déjà abonné ? » — le garde-fou anti-double-souscription
    de POST /billing/checkout.
    """
    rows = active_subscriptions(supabase, user_id)
    return rows[0] if rows else None


def _plan_de(row: dict) -> str | None:
    """L'offre portée par une ligne d'abonnement.

    `plan` est la source normale (posée par le webhook depuis nos métadonnées).
    Le repli par `stripe_price_id` couvre les abonnements créés sans elles ;
    NULL sur les deux = abonnement antérieur aux trois offres, qui n'ouvre rien.
    """
    return row.get("plan") or plan_pour_price(row.get("stripe_price_id"))


def active_plans(supabase: Client, user_id: str) -> set[str]:
    """Les offres que ce compte détient. Vide = offre gratuite."""
    plans = {_plan_de(row) for row in active_subscriptions(supabase, user_id)}
    return {p for p in plans if p in PLANS}


def plans_par_compte(supabase: Client, user_ids: Iterable[str]) -> dict[str, set[str]]:
    """Les offres détenues, pour plusieurs comptes d'un coup.

    Une seule requête quel que soit le nombre de comptes : la liste des
    monuments accessibles peut appartenir à plusieurs propriétaires, et un
    aller-retour Supabase par propriétaire se paierait sur chaque affichage de
    « Mes monuments ». Les comptes sans abonnement actif sont absents du
    résultat — leur ensemble de plans est vide, donc l'offre gratuite.
    """
    ids = sorted(set(user_ids))
    if not ids:
        return {}
    rows = (
        (
            supabase.table("subscriptions")
            .select("user_id, plan, stripe_price_id")
            .in_("user_id", ids)
            .in_("status", sorted(ACTIVE_SUBSCRIPTION_STATUSES))
            .execute()
        ).data
    ) or []
    par_compte: dict[str, set[str]] = {}
    for row in rows:
        plan = _plan_de(row)
        if plan in PLANS:
            par_compte.setdefault(row["user_id"], set()).add(plan)
    return par_compte


def offre_du_compte(supabase: Client, user_id: str) -> Offre:
    """L'offre effective du compte — l'autorité unique sur ses droits.

    Tout point du produit qui restreint quelque chose passe par ici : quotas de
    monuments et de projets, suppressions, tableau de bord, échéancier, aides à
    venir, emails de rappel. Ce qu'ouvre chaque offre est dans
    `services/offres.py`.
    """
    return offre_pour(active_plans(supabase, user_id))


def peut_recevoir_rappels(supabase: Client, user_id: str) -> bool:
    """Ce compte reçoit-il les emails de veille ?

    Deux emails sont concernés, et aucun ne part sur l'offre gratuite :
    l'annonce qu'une aide « Disponibles bientôt » vient d'ouvrir son guichet, et
    le rappel avant une date limite.

    Point de branchement unique du job de rappels : il doit appeler cette
    fonction pour chaque destinataire, en plus de ses préférences de
    notification — l'offre décide s'il a droit au service, les préférences s'il
    le souhaite.
    """
    return offre_du_compte(supabase, user_id).rappels_email


def _a_un_client_stripe(supabase: Client, user_id: str) -> bool:
    """Ce compte est-il rattaché à un Customer Stripe ?

    C'est la condition du portail de facturation, et elle ne se déduit PAS de
    la présence d'un abonnement : une offre sur mesure ouverte directement en
    base donne des droits sans passer par Stripe.
    """
    res = (
        supabase.table("users")
        .select("stripe_customer_id")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    return bool(((res.data if res else None) or {}).get("stripe_customer_id"))


def access_snapshot(supabase: Client, user_id: str) -> dict[str, Any]:
    """État complet des droits — la réponse de GET /billing/access.

    Le frontend s'appuie sur CET appel, et non sur le profil persisté dans le
    localStorage : un profil bricolé côté navigateur ne débloque rien. Il reçoit
    l'offre déjà résolue plutôt que la liste des plans à interpréter — les deux
    côtés tiennent la même table (`frontend/src/lib/offres.ts`), mais c'est le
    serveur qui tranche.
    """
    subscriptions = active_subscriptions(supabase, user_id)
    plans = sorted({p for p in (_plan_de(r) for r in subscriptions) if p in PLANS})
    principale = next((r for r in subscriptions if _plan_de(r) in PLANS), None)
    return {
        "plans": plans,
        "offre": as_dict(offre_pour(plans)),
        # Le portail Stripe n'existe que pour un compte rattaché à un Customer.
        # Une offre ouverte à la main — Multi-monuments se négocie, cf.
        # PLANS_VENDABLES — n'en a pas : proposer « Gérer mon abonnement »
        # mènerait à un 404. Mieux vaut que le front ne le propose pas.
        "portail": _a_un_client_stripe(supabase, user_id),
        "subscription": (
            {
                "plan": _plan_de(principale),
                "status": principale["status"],
                "currentPeriodEnd": principale.get("current_period_end"),
                "cancelAtPeriodEnd": principale.get("cancel_at_period_end", False),
            }
            if principale
            else None
        ),
        "configured": is_configured(),
        "testMode": is_test_mode(),
    }


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
