"""Client OpenRouter du paquet : un appel, un coût facturé, un modèle servi, ou une panne classée.

Deux points d'accès, un seul client : `completer` (les LLM, chat completions)
et `decider` (Jev, modèle de décision qui rend des probabilités). Chaque réponse
porte ce qu'OpenRouter facture (`usage.cost`) et le modèle qui a répondu : le
coût n'est jamais une estimation au tarif d'un registre (celui de providall
tarifait `or-glm` à la moitié de son prix au 2026-10-10).

Une erreur n'est jamais une réponse : réseau, délai, crédits, clé, réponse vide,
JSON invalide, réponse de Jev sans probabilité, modèle servi hors de la liste
acceptée lèvent `Panne`, avec une classe que l'appelant journalise et rejoue,
jamais un jugement. Les classes transitoires sont relancées une fois.

Avec `journal`, chaque tentative, réussie ou non, est ajoutée à un fichier JSONL.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import threading
import time
from collections.abc import Callable, Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

URL = "https://openrouter.ai/api/v1/chat/completions"
URL_DECISIONS = "https://openrouter.ai/api/alpha/decisions"
TRANSITOIRES = frozenset({408, 429, 500, 502, 503, 504, 524, 529})
# Une panne de ces classes ne se résout pas en attendant : pas de relance.
DEFINITIVES = frozenset({"credits", "cle", "requete", "modele_substitue"})


class Panne(Exception):
    """Un appel qui n'a pas rendu de réponse exploitable. `classe` dit pourquoi."""

    def __init__(self, classe: str, message: str) -> None:
        super().__init__(f"{classe} : {message}")
        self.classe = classe


@dataclass(frozen=True)
class Reponse:
    """Ce qu'un LLM a rendu."""

    texte: str
    donnees: Any
    modele_servi: str
    fournisseur: str | None
    cout_usd: float | None
    jetons_entree: int
    jetons_sortie: int
    jetons_raisonnement: int
    duree_s: float


@dataclass(frozen=True)
class Avis:
    """La réponse de Jev à une question : une distribution, jamais un texte."""

    type: str
    probabilites: dict[str, float]
    choix: str | None = None

    def proba(self, option: str) -> float:
        return self.probabilites.get(option, 0.0)


@dataclass(frozen=True)
class Decision:
    """Ce que Jev a rendu pour un état et des questions."""

    avis: dict[str, Avis]
    modele_servi: str
    cout_usd: float | None
    jetons_entree: int
    duree_s: float


# --------------------------------------------------------------------------
# Questions de Jev
# --------------------------------------------------------------------------


def choix(instructions: str, criteres: dict[str, str]) -> dict[str, Any]:
    """Une option parmi `criteres` (clé = valeur rendue, valeur = description)."""
    return {"type": "choice", "instructions": instructions, "criteria": criteres}


def noul(instructions: str, vrai: str, faux: str) -> dict[str, Any]:
    """Vrai ou faux. L'avis porte les probabilités de `true` et de `false`."""
    return {"type": "noul", "instructions": instructions, "criteria": {"true": vrai, "false": faux}}


def echelle(instructions: str, niveaux: list[str]) -> dict[str, Any]:
    """Un niveau sur une échelle ordonnée, du plus bas au plus haut."""
    return {"type": "score", "instructions": instructions, "criteria": niveaux}


def lire_avis(nom: str, brut: Any) -> Avis:
    """L'avis d'une question, ou une panne s'il n'a pas de probabilité utilisable.

    Une réponse `noul` vide lue comme une probabilité nulle écartait une page
    sans recours dans l'ancien pipeline : ici, c'est une panne.
    """
    if not isinstance(brut, dict):
        raise Panne("reponse_invalide", f"{nom} : réponse absente")
    if brut.get("type") == "noul":
        p = brut.get("noul")
        if not isinstance(p, int | float) or not 0.0 <= p <= 1.0:
            raise Panne("reponse_invalide", f"{nom} : probabilité noul absente ou hors bornes")
        return Avis("noul", {"true": float(p), "false": 1.0 - float(p)})
    probabilites = brut.get("probabilities")
    if not isinstance(probabilites, dict) or not probabilites:
        raise Panne("reponse_invalide", f"{nom} : distribution absente")
    try:
        distribution = {str(k): float(v) for k, v in probabilites.items()}
    except (TypeError, ValueError) as exc:
        raise Panne("reponse_invalide", f"{nom} : distribution illisible") from exc
    return Avis(str(brut.get("type") or "choice"), distribution, brut.get("choice"))


# --------------------------------------------------------------------------
# Client
# --------------------------------------------------------------------------


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
        fournisseurs: dict[str, Any] | None = None,
        acceptes: Collection[str] | None = None,
        delai_s: float | None = None,
        role: str = "",
    ) -> Reponse:
        """Un appel de LLM. Avec `schema`, la réponse est un JSON strict, rendu dans `donnees`."""
        corps: dict[str, Any] = {
            "model": modele,
            "messages": messages,
            "max_tokens": max_tokens,
            "usage": {"include": True},
        }
        if effort:
            corps["reasoning"] = {"effort": effort}
        preferences = dict(fournisseurs or {})
        if schema is not None:
            corps["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": nom_schema, "strict": True, "schema": schema},
            }
            # Seuls les fournisseurs qui tiennent le schéma sont admis.
            preferences["require_parameters"] = True
        if preferences:
            corps["provider"] = preferences

        def analyser(brut: dict[str, Any], trace: dict[str, Any], debut: float) -> Reponse:
            usage = brut.get("usage") or {}
            details = usage.get("completion_tokens_details") or {}
            choisi = (brut.get("choices") or [{}])[0]
            texte = ((choisi.get("message") or {}).get("content")) or ""
            trace.update(
                fournisseur=brut.get("provider"),
                jetons_sortie=usage.get("completion_tokens"),
                fin=choisi.get("finish_reason"),
            )
            if not texte.strip():
                raise Panne("reponse_vide", f"fin {choisi.get('finish_reason')}")
            donnees: Any = None
            if schema is not None:
                try:
                    donnees = json.loads(texte)
                except json.JSONDecodeError as exc:
                    raise Panne("json_invalide", str(exc)) from exc
            return Reponse(
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

        return self._appeler(URL, corps, modele, analyser, acceptes, delai_s, role)

    def decider(
        self,
        modele: str,
        etat: str | dict[str, Any] | list[Any],
        questions: dict[str, Any],
        *,
        acceptes: Collection[str] | None = None,
        delai_s: float | None = 15.0,
        role: str = "",
    ) -> Decision:
        """Un appel de Jev : un état, des questions fermées, une distribution par question."""
        corps = {"model": modele, "state": etat, "questions": questions}

        def analyser(brut: dict[str, Any], trace: dict[str, Any], debut: float) -> Decision:
            reponses = brut.get("answers") or {}
            avis = {nom: lire_avis(nom, reponses.get(nom)) for nom in questions}
            usage = brut.get("usage") or {}
            return Decision(
                avis=avis,
                modele_servi=brut.get("model") or modele,
                cout_usd=usage.get("cost"),
                jetons_entree=int(usage.get("input_tokens") or 0),
                duree_s=round(time.monotonic() - debut, 2),
            )

        return self._appeler(URL_DECISIONS, corps, modele, analyser, acceptes, delai_s, role)

    # ---------------------------------------------------------------- interne

    def _appeler[T](
        self,
        url: str,
        corps: dict[str, Any],
        modele: str,
        analyser: Callable[[dict[str, Any], dict[str, Any], float], T],
        acceptes: Collection[str] | None,
        delai_s: float | None,
        role: str,
    ) -> T:
        derniere: Panne | None = None
        for n in range(self.tentatives):
            try:
                return self._une_tentative(url, corps, modele, analyser, acceptes, delai_s, role)
            except Panne as exc:
                derniere = exc
                if exc.classe in DEFINITIVES:
                    raise
                if n + 1 < self.tentatives:
                    time.sleep(2 if n == 0 else 8)
        assert derniere is not None
        raise derniere

    def _une_tentative[T](
        self,
        url: str,
        corps: dict[str, Any],
        modele: str,
        analyser: Callable[[dict[str, Any], dict[str, Any], float], T],
        acceptes: Collection[str] | None,
        delai_s: float | None,
        role: str,
    ) -> T:
        debut = time.monotonic()
        trace: dict[str, Any] = {
            "t": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "point": "decisions" if url == URL_DECISIONS else "chat",
            "modele_demande": modele,
            "role": role,
        }
        try:
            try:
                if delai_s is None:
                    r = self._http.post(url, json=corps)
                else:
                    r = self._http.post(url, json=corps, timeout=delai_s)
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
            try:
                brut = r.json()
            except json.JSONDecodeError as exc:
                raise Panne("reponse_invalide", "corps de réponse illisible") from exc
            if not isinstance(brut, dict):
                raise Panne("reponse_invalide", "corps de réponse inattendu")
            if "error" in brut:
                raise Panne("fournisseur", str(brut["error"])[:300])
            usage = brut.get("usage") or {}
            trace.update(
                modele_servi=brut.get("model"),
                cout_usd=usage.get("cost"),
                jetons_entree=usage.get("prompt_tokens") or usage.get("input_tokens"),
            )
            servi = brut.get("model") or ""
            if acceptes is not None and servi not in acceptes:
                raise Panne("modele_substitue", f"servi « {servi} », accepté : {sorted(acceptes)}")
            resultat = analyser(brut, trace, debut)
            trace["duree_s"] = round(time.monotonic() - debut, 2)
            self._tracer(trace)
            return resultat
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
