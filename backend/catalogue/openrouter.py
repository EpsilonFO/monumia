"""Client OpenRouter du paquet : un appel, un coût facturé, un modèle servi, ou une panne classée.

Chaque réponse porte ce qu'OpenRouter facture (`usage.cost`), le modèle qui a
répondu et le fournisseur qui l'a servi : le coût n'est jamais une estimation
au tarif d'un registre (le registre de providall tarifait `or-glm` à la moitié
de son prix au 2026-10-10). Une erreur n'est jamais une réponse : réseau, délai,
crédits, réponse vide ou JSON invalide lèvent `Panne`, avec une classe que
l'appelant journalise et rejoue, jamais un jugement.

Avec `journal`, chaque tentative, réussie ou non, est ajoutée à un fichier JSONL.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

URL = "https://openrouter.ai/api/v1/chat/completions"
TRANSITOIRES = frozenset({408, 429, 500, 502, 503, 504, 524, 529})


class Panne(Exception):
    """Un appel qui n'a pas rendu de réponse exploitable. `classe` dit pourquoi."""

    def __init__(self, classe: str, message: str) -> None:
        super().__init__(f"{classe} : {message}")
        self.classe = classe


@dataclass(frozen=True)
class Reponse:
    texte: str
    donnees: Any
    modele_servi: str
    fournisseur: str | None
    cout_usd: float | None
    jetons_entree: int
    jetons_sortie: int
    jetons_raisonnement: int
    duree_s: float


class Client:
    def __init__(
        self,
        cle: str | None = None,
        *,
        timeout: float = 600.0,
        tentatives: int = 2,
        journal: Path | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        cle = cle or os.environ.get("OPENROUTER_API_KEY")
        if not cle:
            raise Panne("cle", "OPENROUTER_API_KEY absente")
        self.tentatives = tentatives
        self.journal = journal
        self._verrou = threading.Lock()
        self._http = httpx.Client(
            timeout=timeout,
            transport=transport,
            headers={"Authorization": f"Bearer {cle}", "Content-Type": "application/json"},
        )

    def completer(
        self,
        modele: str,
        messages: list[dict[str, str]],
        *,
        schema: dict[str, Any] | None = None,
        nom_schema: str = "sortie",
        effort: str | None = "medium",
        max_tokens: int = 32000,
        role: str = "",
    ) -> Reponse:
        corps: dict[str, Any] = {
            "model": modele,
            "messages": messages,
            "max_tokens": max_tokens,
            "usage": {"include": True},
        }
        if effort:
            corps["reasoning"] = {"effort": effort}
        if schema is not None:
            corps["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": nom_schema, "strict": True, "schema": schema},
            }
            # Seuls les fournisseurs qui tiennent le schéma sont admis.
            corps["provider"] = {"require_parameters": True}
        derniere: Panne | None = None
        for n in range(self.tentatives):
            try:
                return self._un_appel(corps, modele, schema is not None, role)
            except Panne as exc:
                derniere = exc
                if exc.classe in ("credits", "cle", "requete"):
                    raise
                time.sleep(2 if n == 0 else 8)
        assert derniere is not None
        raise derniere

    def _un_appel(
        self, corps: dict[str, Any], modele: str, json_attendu: bool, role: str
    ) -> Reponse:
        debut = time.monotonic()
        trace: dict[str, Any] = {
            "t": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "modele_demande": modele,
            "role": role,
        }
        try:
            try:
                r = self._http.post(URL, json=corps)
            except httpx.TimeoutException as exc:
                raise Panne("delai", str(exc)) from exc
            except httpx.TransportError as exc:
                raise Panne("reseau", str(exc)) from exc
            if r.status_code == 402:
                raise Panne("credits", r.text[:300])
            if r.status_code in (401, 403):
                raise Panne("cle", r.text[:300])
            if r.status_code in TRANSITOIRES:
                raise Panne("fournisseur", f"HTTP {r.status_code} : {r.text[:300]}")
            if r.status_code != 200:
                raise Panne("requete", f"HTTP {r.status_code} : {r.text[:300]}")
            brut = r.json()
            if "error" in brut:
                raise Panne("fournisseur", str(brut["error"])[:300])
            usage = brut.get("usage") or {}
            details = usage.get("completion_tokens_details") or {}
            choix = (brut.get("choices") or [{}])[0]
            texte = ((choix.get("message") or {}).get("content")) or ""
            trace.update(
                modele_servi=brut.get("model"),
                fournisseur=brut.get("provider"),
                cout_usd=usage.get("cost"),
                jetons_entree=usage.get("prompt_tokens"),
                jetons_sortie=usage.get("completion_tokens"),
                fin=choix.get("finish_reason"),
            )
            if not texte.strip():
                raise Panne("reponse_vide", f"fin {choix.get('finish_reason')}")
            donnees: Any = None
            if json_attendu:
                try:
                    donnees = json.loads(texte)
                except json.JSONDecodeError as exc:
                    raise Panne("json_invalide", str(exc)) from exc
            reponse = Reponse(
                texte=texte,
                donnees=donnees,
                modele_servi=brut.get("model") or modele,
                fournisseur=brut.get("provider"),
                cout_usd=usage.get("cost"),
                jetons_entree=int(usage.get("prompt_tokens") or 0),
                jetons_sortie=int(usage.get("completion_tokens") or 0),
                jetons_raisonnement=int(details.get("reasoning_tokens") or 0),
                duree_s=round(time.monotonic() - debut, 2),
            )
            trace["duree_s"] = reponse.duree_s
            self._tracer(trace)
            return reponse
        except Panne as exc:
            trace.update(
                panne=exc.classe, message=str(exc)[:300], duree_s=round(time.monotonic() - debut, 2)
            )
            self._tracer(trace)
            raise

    def _tracer(self, ligne: dict[str, Any]) -> None:
        if self.journal is None:
            return
        with self._verrou, self.journal.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")

    def fermer(self) -> None:
        self._http.close()
