import os
from functools import lru_cache

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client, ClientOptions, create_client

from services.roles import est_admin

load_dotenv()
load_dotenv(".env.local", override=True)  # local overrides, gitignored

_bearer = HTTPBearer()

# Secret HS256 du projet (Settings → API → JWT Secret). Optionnel : seulement
# utile si le projet signe encore avec la clé symétrique héritée. Avec des clés
# asymétriques (ES256/RS256, le défaut des projets récents) le JWKS suffit.
_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET")


@lru_cache(maxsize=1)
def _service_client() -> Client:
    """Client service-role unique pour tout le process.

    Un client par requête (le comportement d'origine) rouvrait une connexion
    TLS vers Supabase à chaque appel et repartait avec un cache JWKS vide : le
    singleton réutilise le pool httpx et garde les clés de signature en
    mémoire. Le partage est sûr ici — `supabase.table(...)` construit un
    nouveau query builder à chaque appel, et aucun code ne mute l'état du
    client (pas de `postgrest.auth()`, pas de `sign_in` : les opérations
    d'authentification passent par le client anon, créé par requête).
    """
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SECRET_KEY"]
    # Pas de timer d'auto-refresh sur un client à durée de vie infinie : la clé
    # service-role n'a pas de session à rafraîchir.
    options = ClientOptions(auto_refresh_token=False, persist_session=False)
    return create_client(url, key, options)


def get_supabase() -> Client:
    """Service-role client — full DB access, for internal operations."""
    return _service_client()


def get_anon_supabase() -> Client:
    """Anon client — used for Auth operations (login, register, logout).

    auto_refresh_token doit rester désactivé : le client est créé par requête,
    mais le timer d'auto-refresh de gotrue survit à la requête et consommerait
    en arrière-plan le refresh token rendu au frontend (rotation à usage
    unique → session du client invalidée, déconnexion forcée à l'expiration).
    """
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_PUBLISHABLE_KEY"]
    options = ClientOptions(auto_refresh_token=False, persist_session=False)
    return create_client(url, key, options)


def verify_token(token: str, supabase: Client) -> dict:
    """Valide la signature du JWT et renvoie ses claims.

    Vérifier en local évite un aller-retour vers l'API Auth sur CHAQUE requête
    (mesuré à 110-210 ms en production). Trois voies, par ordre de préférence :

      1. Clé asymétrique (ES256/RS256) : `get_claims` valide la signature avec
         le JWKS, téléchargé une fois puis gardé en cache dans le client — d'où
         l'importance du singleton ci-dessus.
      2. Clé symétrique (HS256) : validation locale si `SUPABASE_JWT_SECRET`
         est configuré.
      3. Sinon : repli sur l'API Auth distante (comportement d'origine), pour
         qu'un projet encore en HS256 sans secret configuré continue de
         fonctionner, simplement sans le gain de latence.

    Contrepartie assumée : une session révoquée (déconnexion) reste acceptée
    jusqu'à l'expiration de son access token, la révocation n'étant plus
    vérifiée côté serveur à chaque appel.
    """
    header = jwt.get_unverified_header(token)
    alg = header.get("alg")

    if alg != "HS256" and header.get("kid"):
        response = supabase.auth.get_claims(token)
        # supabase-py renvoie un TypedDict ; on tolère aussi la forme objet au
        # cas où une version ultérieure changerait d'avis.
        claims = (
            response.get("claims")
            if isinstance(response, dict)
            else getattr(response, "claims", None)
        )
        if not claims:
            raise ValueError("No claims in token")
        return dict(claims)

    if alg == "HS256" and _JWT_SECRET:
        return jwt.decode(
            token,
            _JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )

    # Repli distant : coûteux, mais toujours correct.
    response = supabase.auth.get_user(token)
    if response is None or response.user is None:
        raise ValueError("No user in response")
    return {"sub": response.user.id}


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    supabase: Client = Depends(get_supabase),
) -> str:
    """Extract and verify the JWT, returning the authenticated user's UUID."""
    token = credentials.credentials
    try:
        claims = verify_token(token, supabase)
        user_id = claims.get("sub")
        if not user_id:
            raise ValueError("No sub claim in token")
        return user_id
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
        ) from e


def get_current_auth_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    supabase: Client = Depends(get_supabase),
):
    """Comme get_current_user_id, mais renvoie l'utilisateur auth complet.

    Nécessaire au flux OAuth : email et user_metadata (given_name…) doivent
    venir du token, jamais du client. N'exige PAS de ligne dans public.users.

    Reste sur l'appel distant : ce chemin ne sert qu'à l'inscription OAuth
    (quelques appels par compte), et il a besoin de l'objet utilisateur complet
    tel que le renvoie Supabase, pas des seuls claims du token.
    """
    token = credentials.credentials
    try:
        response = supabase.auth.get_user(token)
        if response is None or response.user is None:
            raise ValueError("No user in response")
        return response.user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
        ) from e


def require_admin(
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
) -> str:
    """Réserve une route à l'administration du catalogue (cf. `services.roles`).

    403 et non 404 : la route existe, elle n'est simplement pas pour ce compte.
    Le profil porte `estAdmin` pour l'affichage, mais c'est ici qu'est
    l'autorité — un bouton caché ne protège rien.
    """
    if not est_admin(supabase, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé à l'administration",
        )
    return user_id
