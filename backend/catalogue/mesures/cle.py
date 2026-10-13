"""Relevé de l'usage de la clé OpenRouter, avant et après chaque série payante.

Commande, depuis backend/ :

    uv run python -m catalogue.mesures.cle

Appel gratuit à `GET https://openrouter.ai/api/v1/key`. Affiche `usage`, `limit`,
`limit_remaining` et `expires_at`, jamais la clé. `limit_remaining` est le reste
sur le plafond propre de la clé, pas le solde du compte, qui ne se lit pas avec
cette clé.
"""

from __future__ import annotations

import json
import os

import httpx
from pipeline import llm

URL = "https://openrouter.ai/api/v1/key"


def releve() -> dict[str, object]:
    llm.charger_env()
    cle = os.environ.get("OPENROUTER_API_KEY")
    if not cle:
        raise SystemExit("OPENROUTER_API_KEY absente de backend/.env.local")
    reponse = httpx.get(URL, headers={"Authorization": f"Bearer {cle}"}, timeout=30)
    reponse.raise_for_status()
    donnees = reponse.json()["data"]
    return {k: donnees.get(k) for k in ("usage", "limit", "limit_remaining", "expires_at")}


if __name__ == "__main__":
    print(json.dumps(releve(), ensure_ascii=False))
