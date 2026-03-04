from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import merimee

app = FastAPI(title="Patrialta API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(merimee.router)
