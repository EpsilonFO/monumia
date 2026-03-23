from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import merimee, auth, monuments, documents, aides, notifications, dossiers, prospects, communes

app = FastAPI(title="Patrialta API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "https://patrialta.fr", "https://www.patrialta.fr"],
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
