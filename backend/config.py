"""Origines autorisées, partagées par CORS et les redirections de paiement.

Une seule liste pour les deux usages : une origine acceptée par CORS est une
origine où l'on accepte de renvoyer l'utilisateur après un paiement, et
l'inverse aussi. Deux listes finiraient par diverger.
"""

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
