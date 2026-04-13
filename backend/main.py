from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from logging_config import setup_logging
from routers import (
    aides,
    auth,
    communes,
    documents,
    dossiers,
    merimee,
    monuments,
    notifications,
    prospects,
)

setup_logging()

app = FastAPI(title="Patrialta API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://patrialta.fr",
        "https://www.patrialta.fr",
        "https://app.patrialta.fr",
        "https://beta.patrialta.fr",
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
app.include_router(prospects.router)
app.include_router(communes.router)
