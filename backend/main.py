import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from config import ALLOWED_ORIGINS
from logging_config import setup_logging
from routers import (
    admin,
    aides,
    auth,
    billing,
    communes,
    dashboard,
    documents,
    dossiers,
    invitations,
    merimee,
    monuments,
    notifications,
    projet_sharing,
    projets,
    sharing,
    suivi,
    templates,
    waitlist,
)

setup_logging()

logger = logging.getLogger(__name__)


def _prechauffer() -> None:
    """Paie au démarrage ce que le premier visiteur payait après chaque déploiement.

    Le chargement des YAML du catalogue coûte plus de trois secondes, et le
    premier appel qui le déclenchait pouvait être un visiteur anonyme sur la
    route publique du diagnostic invité. L'ordre compte :

    1. le catalogue et l'ontologie, en cache module-level ;
    2. l'attribut `postgrest` du client service-role, dont l'initialisation
       paresseuse n'est pas verrouillée : deux threads concurrents au tout
       premier appel créeraient deux clients PostgREST, donc deux pools TLS ;
    3. les deux caches à TTL 60 s (surcouche d'administration et rôles de
       compte), qui lisent la base au travers de ce client.

    Aucune étape n'est bloquante : une base injoignable au démarrage ne doit
    pas empêcher le process de servir, les caches se rempliront au premier
    appel comme avant.
    """
    from aides_schema import load_all_aides, load_facts, load_pending_facts
    from db import _service_client
    from services import catalogue_admin, roles

    try:
        load_all_aides()
        load_facts()
        load_pending_facts()
    except Exception:
        logger.exception("Préchargement du catalogue en échec")
    try:
        client = _service_client()
        client.postgrest  # noqa: B018 — force l'initialisation, cf. docstring
        catalogue_admin.catalogue_effectif(client)
        roles._en_base(client)
    except Exception:
        logger.exception("Préchauffage du client Supabase en échec")


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # Aucune requête n'est servie avant la fin du lifespan : le préchargement
    # retarde au pire le premier visiteur d'un démarrage, qui l'aurait payé de
    # toute façon, et plus aucun des suivants.
    _prechauffer()
    yield


# Disable interactive API docs outside development. Production exposure of
# /docs, /redoc, and /openapi.json gives attackers a free map of every route.
_ENV = os.environ.get("ENV", "production").lower()
_DOCS_ENABLED = _ENV in {"development", "dev", "local"}

app = FastAPI(
    title="Monumia API",
    docs_url="/docs" if _DOCS_ENABLED else None,
    redoc_url="/redoc" if _DOCS_ENABLED else None,
    openapi_url="/openapi.json" if _DOCS_ENABLED else None,
    lifespan=_lifespan,
)

# Les réponses JSON partaient non compressées, alors qu'un diagnostic complet
# (toutes les aides, conditions détaillées) pèse plusieurs centaines de Ko sur
# le fil. Seuil à 1 Ko pour ne rien compresser inutilement.
#
# Niveau 5 et non le défaut de Starlette (9, le plus lent de zlib) : sur un
# diagnostic, le niveau 9 coûtait neuf fois le moteur lui-même pour 6 % de
# taille en moins. C'est aussi le réglage de nginx (nginx/nginx.conf).
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)

app.add_middleware(
    CORSMiddleware,
    # Même liste que les redirections de retour de paiement (config.py).
    allow_origins=list(ALLOWED_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(merimee.router)
app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(monuments.router)
app.include_router(projets.router)
app.include_router(projet_sharing.router)
app.include_router(documents.router)
app.include_router(aides.router)
app.include_router(notifications.router)
app.include_router(dossiers.router)
app.include_router(suivi.router)
app.include_router(sharing.router)
app.include_router(communes.router)
app.include_router(templates.router)
app.include_router(invitations.router)
app.include_router(dashboard.router)
app.include_router(waitlist.router)
app.include_router(billing.router)
