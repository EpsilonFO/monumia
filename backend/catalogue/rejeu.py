"""Rejouer des réponses de modèles enregistrées : des tests sans réseau ni dépense.

Une requête se reconnaît à l'empreinte de son corps JSON (clés triées) ; le
transport rend la réponse enregistrée pour cette empreinte, et une erreur 599
« non enregistrée » sinon, pour qu'un test ne passe jamais par hasard sur une
requête qu'on n'a pas prévue. `Enregistreur` enveloppe un vrai transport et
garde chaque échange, pour constituer un jeu de rejeu à partir d'un run réel.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import httpx


def empreinte_requete(contenu: bytes) -> str:
    try:
        canonique = json.dumps(json.loads(contenu), sort_keys=True, ensure_ascii=False)
    except json.JSONDecodeError:
        canonique = contenu.decode("utf-8", errors="replace")
    return hashlib.sha256(canonique.encode()).hexdigest()


def transport_rejeu(enregistrements: dict[str, tuple[int, Any]]) -> httpx.MockTransport:
    """Un transport qui rend, pour chaque empreinte de requête, le statut et le JSON enregistrés."""

    def repondre(requete: httpx.Request) -> httpx.Response:
        cle = empreinte_requete(requete.content)
        if cle not in enregistrements:
            return httpx.Response(599, json={"error": f"requête non enregistrée {cle[:12]}"})
        statut, corps = enregistrements[cle]
        return httpx.Response(statut, json=corps)

    return httpx.MockTransport(repondre)


class Enregistreur(httpx.BaseTransport):
    """Enveloppe un transport réel et garde chaque échange (empreinte, statut, JSON)."""

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self._transport = transport or httpx.HTTPTransport()
        self.enregistrements: dict[str, tuple[int, Any]] = {}

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        reponse = self._transport.handle_request(request)
        reponse.read()
        try:
            corps = reponse.json()
        except json.JSONDecodeError:
            corps = {"texte": reponse.text}
        self.enregistrements[empreinte_requete(request.content)] = (reponse.status_code, corps)
        return httpx.Response(reponse.status_code, json=corps)
