import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from logging_config import setup_logging
from routers import (
    aides,
    auth,
    communes,
    dashboard,
    documents,
    dossiers,
    invitations,
    merimee,
    monuments,
    notifications,
    prospects,
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

# Les réponses JSON partaient non compressées : le catalogue d'aides pesait
# 1,1 Mo sur le fil. Seuil à 1 Ko pour ne rien compresser inutilement.
app.add_middleware(GZipMiddleware, minimum_size=1024)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://monumia.fr",
        "https://www.monumia.fr",
        "https://app.monumia.fr",
        "https://beta.monumia.fr",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(merimee.router)
app.include_router(auth.router)
app.include_router(monuments.router)
app.include_router(documents.router)
app.include_router(aides.router)
app.include_router(notifications.router)
app.include_router(dossiers.router)
app.include_router(suivi.router)
app.include_router(prospects.router)
app.include_router(sharing.router)
app.include_router(communes.router)
app.include_router(templates.router)
app.include_router(invitations.router)
app.include_router(dashboard.router)
app.include_router(waitlist.router)
