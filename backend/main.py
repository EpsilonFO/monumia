import os

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

# Disable interactive API docs outside development. Production exposure of
# /docs, /redoc, and /openapi.json gives attackers a free map of every route.
_ENV = os.environ.get("ENV", "production").lower()
_DOCS_ENABLED = _ENV in {"development", "dev", "local"}

app = FastAPI(
    title="Monumia API",
    docs_url="/docs" if _DOCS_ENABLED else None,
    redoc_url="/redoc" if _DOCS_ENABLED else None,
    openapi_url="/openapi.json" if _DOCS_ENABLED else None,
)

# Les réponses JSON partaient non compressées, alors qu'un diagnostic complet
# (toutes les aides, conditions détaillées) pèse plusieurs centaines de Ko sur
# le fil. Seuil à 1 Ko pour ne rien compresser inutilement.
app.add_middleware(GZipMiddleware, minimum_size=1024)

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
