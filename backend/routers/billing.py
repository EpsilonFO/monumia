"""Paiement Stripe : ouverture d'un Checkout, portail client, webhook.

Trois principes tiennent la sécurité de ce routeur :

  1. Le montant n'est JAMAIS transmis par le client. Le frontend envoie un nom
     d'offre ; le prix vient de la configuration serveur. Sans ça, n'importe qui
     pourrait acheter un abonnement à 1 centime.
  2. Le webhook ne fait confiance qu'à la signature Stripe. Le corps brut est
     vérifié avant d'être lu, et l'utilisateur concerné est déduit des métadonnées
     que NOUS avons posées à la création de la session — jamais d'un champ envoyé
     par l'appelant.
  3. Chaque événement n'est traité qu'une fois (table stripe_events), Stripe
     garantissant seulement une livraison « au moins une fois ».
"""

import contextlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from supabase import Client

from db import get_current_user_id, get_supabase
from services import stripe_billing as billing
from services.project_access import require_project_access

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


class CheckoutRequest(BaseModel):
    plan: str  # 'dossier' | 'abonnement'
    monumentId: str | None = None


# ---------------------------------------------------------------------------
# Lecture : droits et tarifs
# ---------------------------------------------------------------------------


@router.get("/access")
def get_access(
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """Droits d'accès du compte — l'autorité côté client sur ce qui est débloqué."""
    return billing.access_snapshot(supabase, user_id)


@router.get("/plans")
def get_plans():
    """Offres vendables et leurs prix, tels que configurés dans Stripe.

    Endpoint public : la page Tarifs est accessible sans être connecté.
    `configured: false` → Stripe n'est pas branché, la page affiche son état
    d'attente au lieu de boutons qui échoueraient.
    """
    if not billing.is_configured():
        return {"configured": False, "plans": []}
    return {
        "configured": True,
        "testMode": billing.is_test_mode(),
        "plans": billing.public_plans(),
    }


# ---------------------------------------------------------------------------
# Écriture : ouverture d'une session de paiement
# ---------------------------------------------------------------------------


@router.post("/checkout")
def create_checkout(
    body: CheckoutRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """Ouvre une session Stripe Checkout et renvoie l'URL où rediriger.

    Le paiement se déroule intégralement chez Stripe : aucun numéro de carte ne
    transite par Monumia.
    """
    plan = body.plan
    if plan not in billing.PLANS:
        raise HTTPException(status_code=400, detail="Offre inconnue")

    price = billing.price_id(plan)
    if not price:
        raise HTTPException(status_code=503, detail="Cette offre n'est pas encore disponible.")

    monument_id: str | None = None
    if plan == billing.PLAN_DOSSIER:
        if not body.monumentId:
            raise HTTPException(status_code=400, detail="Projet manquant")
        # Le projet doit être le sien : sans ce contrôle, un paiement pourrait
        # débloquer le projet d'un tiers (dont l'id se devine mal, mais se fuite).
        require_project_access(supabase, body.monumentId, user_id, "co_owner")
        monument_id = body.monumentId

        if billing.monument_is_unlocked(supabase, monument_id):
            raise HTTPException(status_code=409, detail="Ce projet est déjà débloqué.")
        if billing.active_subscription(supabase, user_id) is not None:
            raise HTTPException(
                status_code=409,
                detail="Votre abonnement couvre déjà tous vos projets.",
            )
    elif billing.active_subscription(supabase, user_id) is not None:
        raise HTTPException(status_code=409, detail="Vous êtes déjà abonné.")

    customer_id = billing.ensure_customer(supabase, user_id)
    # Retour sur l'origine d'où vient la demande (localhost, beta, prod) plutôt
    # que sur une URL fixe : un paiement lancé depuis un poste de développement
    # atterrissait sinon en production.
    base = billing.return_origin(request)
    # Métadonnées posées côté serveur : c'est la seule source du webhook pour
    # savoir qui a payé et pour quel projet.
    metadata = {"user_id": user_id, "plan": plan}
    if monument_id:
        metadata["monument_id"] = monument_id

    # Le projet est repassé dans les URL de retour : Stripe emmène l'utilisateur
    # hors du site, et sans lui la page de retour ne saurait pas où le renvoyer.
    projet = f"&projet={monument_id}" if monument_id else ""

    params: dict[str, Any] = {
        "mode": "subscription" if plan == billing.PLAN_ABONNEMENT else "payment",
        "customer": customer_id,
        "line_items": [{"price": price, "quantity": 1}],
        "success_url": (
            f"{base}/tarifs?paiement=succes&plan={plan}{projet}&session_id={{CHECKOUT_SESSION_ID}}"
        ),
        "cancel_url": f"{base}/tarifs?paiement=annule{projet}",
        "client_reference_id": user_id,
        "metadata": metadata,
        "locale": "fr",
        # Adresse de facturation demandée : nécessaire pour une facture valable
        # et pour le calcul de la TVA par pays.
        "billing_address_collection": "required",
    }
    # Le calcul automatique de la TVA exige une adresse d'origine et des
    # immatriculations fiscales renseignées dans Stripe : l'activer sur un
    # compte neuf fait échouer la création de la session. Donc opt-in explicite,
    # une fois Stripe Tax paramétré.
    if billing.automatic_tax_enabled():
        params["automatic_tax"] = {"enabled": True}
    if plan == billing.PLAN_ABONNEMENT:
        # Recopiées sur l'abonnement lui-même : les événements
        # customer.subscription.* n'ont pas accès aux métadonnées de la session.
        params["subscription_data"] = {"metadata": metadata}
    else:
        # Rattache la facture au paiement unique, pour que le client la retrouve
        # dans son portail.
        params["invoice_creation"] = {"enabled": True}
        params["payment_intent_data"] = {"metadata": metadata}

    try:
        session = billing.client().v1.checkout.sessions.create(params=params)
    except stripe.StripeError as e:
        logger.exception("Stripe: création de la session Checkout impossible")
        raise HTTPException(
            status_code=502, detail="Stripe a refusé la demande de paiement."
        ) from e

    return {"url": session.url, "sessionId": session.id}


@router.post("/portal")
def create_portal_session(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """Portail de facturation Stripe : factures, moyen de paiement, résiliation.

    Déléguer la résiliation à Stripe évite de réimplémenter (et de maintenir) un
    écran de gestion d'abonnement, et l'annulation y est immédiatement conforme.
    """
    res = (
        supabase.table("users")
        .select("stripe_customer_id")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    customer_id = (res.data or {}).get("stripe_customer_id") if res else None
    if not customer_id:
        raise HTTPException(status_code=404, detail="Aucun paiement enregistré pour ce compte.")

    try:
        session = billing.client().v1.billing_portal.sessions.create(
            params={
                "customer": customer_id,
                "return_url": f"{billing.return_origin(request)}/tarifs",
            }
        )
    except stripe.StripeError as e:
        logger.exception("Stripe: création de la session portail impossible")
        raise HTTPException(status_code=502, detail="Portail de facturation indisponible.") from e

    return {"url": session.url}


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------


def _already_processed(supabase: Client, event_id: str, event_type: str) -> bool:
    """Marque l'événement comme traité ; True s'il l'était déjà.

    L'insertion elle-même sert de verrou : la clé primaire rejette le doublon,
    ce qui est atomique là où un SELECT puis INSERT laisserait passer deux
    livraisons simultanées.

    Seule une violation d'unicité (23505) vaut « déjà traité ». Toute autre
    erreur est propagée : la prendre pour un doublon ferait silencieusement
    sauter le traitement d'un paiement réel sur une simple coupure réseau, et
    Stripe n'insisterait pas puisqu'il aurait reçu un 200.
    """
    try:
        supabase.table("stripe_events").insert({"id": event_id, "type": event_type}).execute()
        return False
    except Exception as e:
        if _is_unique_violation(e):
            return True
        logger.exception("Stripe: journalisation de l'événement %s impossible", event_id)
        # 500 → Stripe réessaiera l'événement.
        raise HTTPException(status_code=500, detail="Journalisation impossible") from e


def _is_unique_violation(error: Exception) -> bool:
    """Vrai si l'erreur Supabase est un conflit de clé unique (Postgres 23505)."""
    code = getattr(error, "code", None)
    if code == "23505" or code == 23505:
        return True
    return "23505" in str(error) or "duplicate key" in str(error).lower()


def _user_id_for_customer(supabase: Client, customer_id: str | None) -> str | None:
    if not customer_id:
        return None
    res = (
        supabase.table("users")
        .select("id")
        .eq("stripe_customer_id", customer_id)
        .maybe_single()
        .execute()
    )
    return (res.data or {}).get("id") if res else None


def _as_id(value: Any) -> str | None:
    """Un champ Stripe expansible est soit un id, soit l'objet complet."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return getattr(value, "id", None) or (value.get("id") if isinstance(value, dict) else None)


def _period_end_iso(subscription: Any) -> str | None:
    """Fin de la période en cours, au format ISO.

    Stripe a déplacé `current_period_end` de l'abonnement vers ses lignes de
    facturation : on lit la nouvelle position, avec repli sur l'ancienne pour
    rester compatible avec les versions d'API plus anciennes.
    """
    timestamp = subscription.get("current_period_end")
    if timestamp is None:
        items = (subscription.get("items") or {}).get("data") or []
        timestamp = items[0].get("current_period_end") if items else None
    if timestamp is None:
        return None
    return datetime.fromtimestamp(int(timestamp), tz=UTC).isoformat()


def _record_unlock(supabase: Client, session: dict) -> None:
    """Paiement unique encaissé → le projet est débloqué."""
    metadata = session.get("metadata") or {}
    user_id = metadata.get("user_id") or session.get("client_reference_id")
    monument_id = metadata.get("monument_id")
    if not user_id or not monument_id:
        logger.error(
            "Stripe: session %s payée sans user_id/monument_id exploitable", session.get("id")
        )
        return

    row = {
        "user_id": user_id,
        "monument_id": monument_id,
        "stripe_checkout_session_id": session["id"],
        "stripe_payment_intent_id": _as_id(session.get("payment_intent")),
        "amount_cents": session.get("amount_total"),
        "currency": (session.get("currency") or "eur").lower(),
    }
    try:
        supabase.table("monument_unlocks").insert(row).execute()
    except Exception as e:
        # Les deux index uniques (session, couple compte+projet) peuvent rejeter
        # légitimement : rejeu d'un événement, ou seconde session ouverte avant
        # que la première n'aboutisse. Le projet est débloqué dans tous les cas.
        if _is_unique_violation(e):
            logger.info(
                "Stripe: déblocage déjà enregistré pour le projet %s (session %s)",
                monument_id,
                session["id"],
            )
            return
        # Une vraie panne d'écriture, en revanche, doit remonter : l'argent est
        # encaissé et l'accès manque. Le 500 fait réessayer Stripe.
        logger.exception(
            "Stripe: enregistrement du déblocage impossible (session %s)", session["id"]
        )
        raise HTTPException(status_code=500, detail="Enregistrement impossible") from e


def _upsert_subscription(supabase: Client, subscription: dict) -> None:
    """Reflète l'état d'un abonnement Stripe dans la base."""
    metadata = subscription.get("metadata") or {}
    customer_id = _as_id(subscription.get("customer"))
    user_id = metadata.get("user_id") or _user_id_for_customer(supabase, customer_id)
    if not user_id:
        logger.error(
            "Stripe: abonnement %s sans compte Monumia identifiable", subscription.get("id")
        )
        return

    items = (subscription.get("items") or {}).get("data") or []
    price = _as_id(items[0].get("price")) if items else None

    supabase.table("subscriptions").upsert(
        {
            "stripe_subscription_id": subscription["id"],
            "user_id": user_id,
            "stripe_customer_id": customer_id or "",
            "stripe_price_id": price,
            "status": subscription.get("status", "incomplete"),
            "current_period_end": _period_end_iso(subscription),
            "cancel_at_period_end": bool(subscription.get("cancel_at_period_end")),
            # Horodatage calculé en Python : passer la chaîne "now()" par l'API
            # REST l'enverrait comme littéral, pas comme appel SQL.
            "updated_at": datetime.now(UTC).isoformat(),
        },
        on_conflict="stripe_subscription_id",
    ).execute()


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    supabase: Client = Depends(get_supabase),
):
    """Réception des événements Stripe — non authentifié, signé.

    Aucun `Depends` d'authentification ici : l'appelant est Stripe, pas un
    utilisateur. C'est la signature HMAC de l'en-tête `Stripe-Signature` qui
    tient le rôle du token, et elle porte sur le corps BRUT — le lire via
    `await request.body()` avant tout parsing JSON est donc indispensable.
    """
    secret = billing.webhook_secret()
    if not secret:
        raise HTTPException(status_code=503, detail="Webhook non configuré")

    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        # `construct_event` sert ici de VÉRIFICATEUR de signature. Son résultat
        # est un StripeObject, dont l'accès aux champs passe par __getattr__ et
        # n'expose pas `.get()` : les handlers travaillent donc sur le corps brut
        # relu en dictionnaires simples, une fois la signature prouvée.
        stripe.Webhook.construct_event(payload, signature, secret)
        event = json.loads(payload)
        event_type = event["type"]
        event_id = event["id"]
    except stripe.SignatureVerificationError as e:
        # 400 et non 401 : c'est la convention attendue par Stripe, qui cesse de
        # réessayer sur une 4xx.
        raise HTTPException(status_code=400, detail="Signature invalide") from e
    except Exception as e:
        # Signature valide mais corps inexploitable (JSON tronqué, enveloppe
        # d'un autre format). Réessayer ne changerait rien : 400 pour que Stripe
        # arrête, et une trace pour comprendre.
        logger.exception("Stripe: corps de webhook illisible")
        raise HTTPException(status_code=400, detail="Charge utile invalide") from e
    if _already_processed(supabase, event_id, event_type):
        return {"received": True, "duplicate": True}

    try:
        _handle_event(supabase, event_type, event["data"]["object"])
    except Exception:
        # Le verrou d'idempotence a déjà été posé. Le retirer est indispensable :
        # sans ça la nouvelle tentative de Stripe serait classée « doublon » et
        # le paiement resterait sans effet, définitivement.
        with contextlib.suppress(Exception):
            supabase.table("stripe_events").delete().eq("id", event_id).execute()
        raise

    return {"received": True}


def _handle_event(supabase: Client, event_type: str, obj: Any) -> None:
    if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
        # `payment_status` couvre les moyens de paiement différés (SEPA,
        # virement), où la session est « complete » sans que l'argent soit là :
        # l'encaissement effectif arrive alors en async_payment_succeeded.
        if obj.get("mode") == "payment" and obj.get("payment_status") == "paid":
            _record_unlock(supabase, obj)
        # Le mode subscription n'est pas traité ici : customer.subscription.created
        # arrive avec l'état complet de l'abonnement, période comprise.

    elif event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        _upsert_subscription(supabase, obj)

    else:
        logger.info("Stripe: événement %s reçu, non traité", event_type)
