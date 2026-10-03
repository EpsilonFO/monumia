"""Origines autorisées, partagées par CORS et par toutes les URLs que le backend
fabrique à destination d'un navigateur (retours de paiement, liens d'invitation).

Une seule liste pour ces usages : une origine acceptée par CORS est une origine
où l'on accepte de renvoyer l'utilisateur, et l'inverse aussi. Deux listes
finiraient par diverger.
"""

import os
from urllib.parse import urlparse

from fastapi import Request

# Ports de développement : 3000 = application (frontend/vite.config.ts),
# 3001 = landing (landing/vite.config.ts).
ALLOWED_ORIGINS: tuple[str, ...] = (
    "http://localhost:3000",
    "http://localhost:3001",
    "https://monumia.fr",
    "https://www.monumia.fr",
    "https://app.monumia.fr",
    "https://beta.monumia.fr",
)


def resolve_app_origin(origin: str | None, fallback: str) -> str:
    """Origine où renvoyer l'utilisateur, validée contre la liste blanche.

    Stripe redirige le navigateur vers l'URL qu'on lui donne. La déduire de
    l'en-tête `Origin` évite de configurer une variable par environnement (et
    d'atterrir en production depuis un poste de développement), mais cet en-tête
    vient du client : accepter n'importe quelle valeur ouvrirait une redirection
    arbitraire, avec l'identifiant de session de paiement dans l'URL. D'où la
    liste blanche, et le repli sur la valeur configurée en cas de doute.
    """
    if origin and origin.rstrip("/") in ALLOWED_ORIGINS:
        return origin.rstrip("/")
    return fallback.rstrip("/")


def default_app_url() -> str:
    """Origine de repli de l'application, quand la requête n'en dit rien."""
    return (os.environ.get("APP_URL", "").strip() or "https://app.monumia.fr").rstrip("/")


def request_app_origin(request: Request, fallback: str | None = None) -> str:
    """Origine de l'application déduite de la requête, validée par la liste blanche.

    Sert à fabriquer une URL que le navigateur suivra ensuite : retour de
    paiement, lien d'invitation envoyé par email. Une action lancée depuis la
    beta doit renvoyer vers la beta, et depuis localhost vers localhost — sans
    variable d'environnement à poser par machine, et sans risque de renvoyer un
    testeur de la beta vers la production.

    `Origin` d'abord (présent sur toute requête cross-origin, et sur les POST
    même en same-origin), puis `Referer`. La liste blanche est indispensable :
    ces deux en-têtes viennent du client.
    """
    origin = request.headers.get("origin")
    if not origin:
        referer = request.headers.get("referer")
        if referer:
            parsed = urlparse(referer)
            if parsed.scheme and parsed.netloc:
                origin = f"{parsed.scheme}://{parsed.netloc}"
    return resolve_app_origin(origin, fallback or default_app_url())


# ---------------------------------------------------------------------------
# Administration du catalogue
# ---------------------------------------------------------------------------

#: SOCLE d'amorçage de l'administration du catalogue. Liste d'UUID Supabase
#: séparés par des virgules, PROPRE À CHAQUE ENVIRONNEMENT : prod et beta ont
#: chacun leur projet Supabase, donc des identifiants différents pour les mêmes
#: personnes.
#:
#: La liste des administrateurs vit désormais en base (`services/roles.py`,
#: table `comptes_roles`, rôle `admin`), où elle se lit avec un email à côté et
#: se gère depuis `/admin`. Cette variable reste lue pour deux raisons, et deux
#: seulement : ouvrir la porte quand la table est vide (environnement neuf,
#: migration fraîchement appliquée), et donner une liste que l'application ne
#: peut pas vider — on ne peut donc pas se verrouiller dehors. Elle peut être
#: vidée du `.env` une fois les mêmes comptes inscrits en base.
_ADMIN_ENV = "ADMIN_USER_IDS"


def admin_user_ids() -> frozenset[str]:
    """Le socle configuré. Lu à CHAQUE appel, pas mis en cache : les tests le
    remplacent par `patch.dict(os.environ, ...)`, et le coût d'un split sur deux
    UUID est nul. C'est `services.roles.est_admin` qui tranche, en unissant ce
    socle aux lignes de la base."""
    brut = os.environ.get(_ADMIN_ENV, "")
    return frozenset(part.strip() for part in brut.split(",") if part.strip())
