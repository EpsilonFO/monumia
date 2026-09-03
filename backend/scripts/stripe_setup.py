"""Prépare un compte Stripe pour Monumia : produits, prix, webhook.

À lancer une fois en mode test, puis une fois en mode live. Le script est
idempotent : relancé, il retrouve les produits déjà créés par leur `lookup_key`
au lieu d'en empiler des doublons.

    # mode test
    uv run python scripts/stripe_setup.py --key sk_test_xxx

    # mode réel, avec le montant définitif
    uv run python scripts/stripe_setup.py --key sk_live_xxx \\
        --veille 50 \\
        --webhook-url https://app.monumia.fr/api/billing/webhook

Il ne crée que l'offre Veille, et ce prix ne sert PAS à la vendre en ligne :
les deux offres se négocient (cf. services/offres.py, PLANS_VENDABLES). Il sert
à facturer un client une fois l'offre convenue, et à ce que le webhook
reconnaisse son abonnement. Une offre à prix négocié se pose directement dans
`subscriptions.plan` (cf. docs/stripe-setup.md).

Il affiche à la fin les trois variables à recopier dans backend/.env. Rien
n'est écrit sur le disque : les secrets restent sous vos yeux, pas dans un
fichier généré par un script.

Changer un prix plus tard ne se fait PAS en modifiant le montant d'un prix
existant (Stripe les rend immuables, pour que l'historique des factures reste
vrai) : on relance le script avec `--force-new-price`, et on remplace l'id dans
le .env.
"""

from __future__ import annotations

import argparse
import sys

import stripe

# Clés stables qui servent à retrouver un prix déjà créé. Ne les changez pas :
# c'est le seul lien entre deux exécutions du script.
LOOKUP_VEILLE = "monumia_veille_mensuel"

# Événements dont le backend a réellement besoin. Les deux offres sont des
# abonnements : `checkout.session.*` ne sert plus à rien, l'état complet arrive
# avec customer.subscription.created. En demander moins réduit le bruit dans le
# dashboard et le volume de requêtes vers le webhook.
WEBHOOK_EVENTS = [
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
]

DEFAULT_WEBHOOK_URL = "https://app.monumia.fr/api/billing/webhook"


def euros_to_cents(value: str) -> int:
    """« 149 » ou « 149,50 » → 14900 / 14950."""
    cleaned = value.replace(",", ".").replace("€", "").strip()
    cents = round(float(cleaned) * 100)
    if cents <= 0:
        raise argparse.ArgumentTypeError("Le montant doit être supérieur à zéro.")
    return cents


def find_price(client: stripe.StripeClient, lookup_key: str) -> stripe.Price | None:
    found = client.v1.prices.list(params={"lookup_keys": [lookup_key], "active": True, "limit": 1})
    return found.data[0] if found.data else None


def ensure_product(client: stripe.StripeClient, name: str, description: str) -> stripe.Product:
    """Produit retrouvé par son nom exact, créé sinon."""
    for product in client.v1.products.list(
        params={"active": True, "limit": 100}
    ).auto_paging_iter():
        if product.name == name:
            return product
    return client.v1.products.create(params={"name": name, "description": description})


def ensure_price(
    client: stripe.StripeClient,
    *,
    product: stripe.Product,
    lookup_key: str,
    amount_cents: int,
    recurring: bool,
    force_new: bool,
) -> tuple[stripe.Price, bool]:
    """Renvoie (prix, vient_d_être_créé)."""
    existing = find_price(client, lookup_key)
    if existing and not force_new:
        return existing, False

    if existing:
        # Un `lookup_key` ne peut désigner qu'un prix à la fois : on le libère
        # avant de le rattacher au nouveau (chaîne vide = effacer, côté API).
        # L'ancien prix reste actif pour les abonnements déjà en cours, il n'est
        # simplement plus proposé à la vente.
        client.v1.prices.update(existing.id, params={"lookup_key": ""})

    params: dict = {
        "product": product.id,
        "unit_amount": amount_cents,
        "currency": "eur",
        "lookup_key": lookup_key,
    }
    if recurring:
        params["recurring"] = {"interval": "month"}
    return client.v1.prices.create(params=params), True


def ensure_webhook(client: stripe.StripeClient, url: str) -> tuple[str, str | None]:
    """Renvoie (id de l'endpoint, secret de signature si tout juste créé).

    Stripe ne montre le secret qu'à la création. Si l'endpoint existait déjà, le
    secret doit être relevé dans le dashboard — d'où le None.
    """
    for endpoint in client.v1.webhook_endpoints.list(params={"limit": 100}).auto_paging_iter():
        if endpoint.url == url:
            # Remet la liste d'événements à jour, au cas où elle aurait dérivé.
            client.v1.webhook_endpoints.update(
                endpoint.id, params={"enabled_events": WEBHOOK_EVENTS}
            )
            return endpoint.id, None

    created = client.v1.webhook_endpoints.create(
        params={
            "url": url,
            "enabled_events": WEBHOOK_EVENTS,
            "description": "Monumia — abonnements",
        }
    )
    return created.id, created.secret


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key", required=True, help="Clé secrète Stripe (sk_test_… ou sk_live_…)")
    parser.add_argument(
        "--veille",
        type=euros_to_cents,
        default=5000,
        metavar="EUROS",
        help="Prix mensuel de l'offre Veille, en euros (défaut : 50)",
    )
    parser.add_argument(
        "--webhook-url",
        default=DEFAULT_WEBHOOK_URL,
        help=f"URL publique du webhook (défaut : {DEFAULT_WEBHOOK_URL})",
    )
    parser.add_argument(
        "--no-webhook",
        action="store_true",
        help="Ne pas créer d'endpoint webhook (utile en local, où l'on passe par « stripe listen »)",
    )
    parser.add_argument(
        "--force-new-price",
        action="store_true",
        help="Créer de nouveaux prix même s'ils existent (pour changer un montant)",
    )
    args = parser.parse_args()

    if not args.key.startswith(("sk_test_", "sk_live_", "rk_test_", "rk_live_")):
        print("La clé doit commencer par sk_test_ ou sk_live_.", file=sys.stderr)
        return 1

    live = args.key.startswith(("sk_live_", "rk_live_"))
    client = stripe.StripeClient(args.key)
    mode = "RÉEL (les cartes seront débitées)" if live else "test"
    print(f"Mode : {mode}\n")

    veille_product = ensure_product(
        client,
        "Monumia — Veille",
        "Projets illimités, échéancier, aides à venir et rappels par email.",
    )
    veille_price, veille_new = ensure_price(
        client,
        product=veille_product,
        lookup_key=LOOKUP_VEILLE,
        amount_cents=args.veille,
        recurring=True,
        force_new=args.force_new_price,
    )
    print(
        f"{'créé  ' if veille_new else 'existe'}  Veille           "
        f"{veille_price.unit_amount / 100:.2f} €/mois — {veille_price.id}"
    )

    webhook_secret = None
    if not args.no_webhook:
        endpoint_id, webhook_secret = ensure_webhook(client, args.webhook_url)
        state = "créé  " if webhook_secret else "existe"
        print(f"{state}  Webhook      {args.webhook_url} — {endpoint_id}")

    print("\n" + "─" * 72)
    print("À recopier dans backend/.env (et backend/.env.beta pour la beta) :\n")
    print(f"STRIPE_SECRET_KEY={args.key}")
    print(f"STRIPE_PRICE_VEILLE={veille_price.id}")
    if webhook_secret:
        print(f"STRIPE_WEBHOOK_SECRET={webhook_secret}")
    elif not args.no_webhook:
        print(
            "STRIPE_WEBHOOK_SECRET=<à relever dans le dashboard : "
            "Développeurs → Webhooks → votre endpoint → « Signing secret »>"
        )
    print("─" * 72)
    if not live:
        print(
            "\nCarte de test : 4242 4242 4242 4242, date future, CVC au choix.\n"
            "Refus volontaire : 4000 0000 0000 0002."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
