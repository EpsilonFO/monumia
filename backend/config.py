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

#: Les comptes autorisés à retirer une aide du catalogue ou à reformuler une
#: question, depuis la page `/admin`. Liste d'UUID Supabase séparés par des
#: virgules, PROPRE À CHAQUE ENVIRONNEMENT : prod et beta ont chacun leur
#: projet Supabase, donc des identifiants différents pour les mêmes personnes.
#:
#: Une variable d'environnement plutôt qu'une colonne sur `users` : c'est une
#: liste de deux fondateurs, elle ne se gère pas depuis le produit, et la
#: doctrine du dépôt est de ne pas rajouter d'attribut de segment sur `users`.
_ADMIN_ENV = "ADMIN_USER_IDS"


def admin_user_ids() -> frozenset[str]:
    """Les identifiants admin configurés. Lue à CHAQUE appel, pas mise en
    cache : les tests la remplacent par `patch.dict(os.environ, ...)`, et le
    coût d'un split sur deux UUID est nul."""
    brut = os.environ.get(_ADMIN_ENV, "")
    return frozenset(part.strip() for part in brut.split(",") if part.strip())


def est_admin(user_id: str) -> bool:
    """Ce compte administre-t-il le catalogue ? Faux si la variable est absente
    — un environnement non configuré n'a aucun administrateur, jamais tous."""
    return bool(user_id) and user_id in admin_user_ids()
