"""Client des modèles de DÉCISION (Jev) : des questions typées, des probabilités.

Un modèle de décision ne rédige rien. On lui donne un état (texte ou JSON) et
des questions fermées ; il rend, pour chacune, une distribution de
probabilités et une confiance. Trois formes de question :

    choix   une option parmi des critères nommés  → `choix`, `probabilites`
    noul    vrai ou faux                          → `noul` (probabilité du vrai)
    echelle un niveau sur une échelle ordonnée    → `score`, `probabilites`

Pourquoi pas providall : son pivot est celui de chat-completions (messages en
entrée, texte ou JSON en sortie), et Jev n'est servi que par
`POST /api/alpha/decisions`, sous un format qui n'a rien de commun. Passer
d'un LLM à Jev change de toute façon le code appelant (on ne pose plus les
mêmes questions), si bien qu'un alias de plus dans le registre n'apporterait
rien. Ce module restera local tant que Jev n'aura pas fait ses preuves ; s'il
sert à plusieurs étages, il remontera dans providall sous la forme d'un
`decide()`.

Configuration : `OPENROUTER_API_KEY` (la même que le reste du pipeline),
`DECISION_MODEL` (défaut `typesafe/jev-1.13`), `DECISION_URL`.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

URL_DEFAUT = "https://openrouter.ai/api/alpha/decisions"
MODELE_DEFAUT = "typesafe/jev-1.13"

# 402 n'en fait pas partie : des crédits épuisés ne reviennent pas en
# attendant, et une boucle de relances ne ferait que retarder le constat.
STATUTS_TRANSITOIRES = frozenset({429, 500, 502, 503, 524, 529})


# --------------------------------------------------------------------------
# Questions
# --------------------------------------------------------------------------


def choix(instructions: str, criteres: dict[str, str]) -> dict[str, Any]:
    """Une option parmi `criteres` (clé = valeur rendue, valeur = description)."""
    return {"type": "choice", "instructions": instructions, "criteria": criteres}


def noul(instructions: str, vrai: str, faux: str) -> dict[str, Any]:
    """Vrai ou faux. La réponse est la probabilité du vrai."""
    return {
        "type": "noul",
        "instructions": instructions,
        "criteria": {"true": vrai, "false": faux},
    }


def echelle(instructions: str, niveaux: list[str]) -> dict[str, Any]:
    """Un niveau sur une échelle ordonnée, du plus bas au plus haut."""
    return {"type": "score", "instructions": instructions, "criteria": niveaux}


# --------------------------------------------------------------------------
# Réponses
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Reponse:
    """La réponse à UNE question. Seuls les champs de son type sont remplis."""

    type: str
    choix: str | None = None
    noul: float | None = None
    score: float | None = None
    confiance: float | None = None
    probabilites: dict[str, float] = field(default_factory=dict)

    def proba(self, option: str) -> float:
        """Probabilité d'une option ; pour un noul, `"true"` ou `"false"`."""
        if self.type == "noul" and self.noul is not None:
            return self.noul if option == "true" else 1.0 - self.noul
        return self.probabilites.get(option, 0.0)

    @classmethod
    def depuis_json(cls, data: dict[str, Any]) -> Reponse:
        return cls(
            type=data.get("type", ""),
            choix=data.get("choice"),
            noul=data.get("noul"),
            score=data.get("score"),
            confiance=data.get("confidence"),
            probabilites={k: float(v) for k, v in (data.get("probabilities") or {}).items()},
        )


@dataclass(frozen=True)
class Decision:
    reponses: dict[str, Reponse]
    modele: str
    id: str
    jetons_entree: int
    cout_usd: float | None
    latence_s: float
    brut: dict[str, Any]


class ErreurDecision(Exception):
    def __init__(self, message: str, *, statut: int | None = None) -> None:
        super().__init__(message)
        self.statut = statut


# --------------------------------------------------------------------------
# Client
# --------------------------------------------------------------------------


class ClientDecision:
    """Un appel = un état + des questions. Sûr entre threads (httpx.Client l'est)."""

    def __init__(
        self,
        modele: str | None = None,
        *,
        url: str | None = None,
        cle: str | None = None,
        timeout: float = 60.0,
        tentatives: int = 4,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.modele = modele or os.environ.get("DECISION_MODEL") or MODELE_DEFAUT
        self.url = url or os.environ.get("DECISION_URL") or URL_DEFAUT
        cle = cle or os.environ.get("OPENROUTER_API_KEY")
        if not cle:
            raise ErreurDecision("OPENROUTER_API_KEY absente (backend/.env.local)")
        self.tentatives = tentatives
        self._http = httpx.Client(
            timeout=timeout,
            transport=transport,
            headers={"Authorization": f"Bearer {cle}", "Content-Type": "application/json"},
        )

    def decider(
        self, etat: str | dict[str, Any] | list[Any], questions: dict[str, Any]
    ) -> Decision:
        corps = {"model": self.modele, "state": etat, "questions": questions}
        derniere: ErreurDecision | None = None
        for n in range(self.tentatives):
            debut = time.monotonic()
            try:
                r = self._http.post(self.url, json=corps)
            except httpx.TransportError as exc:
                derniere = ErreurDecision(f"réseau : {exc}")
                time.sleep(2**n)
                continue
            latence = time.monotonic() - debut
            if r.status_code == 200:
                return self._lire(r.json(), questions, latence)
            derniere = ErreurDecision(
                f"HTTP {r.status_code} : {r.text[:300]}", statut=r.status_code
            )
            if r.status_code not in STATUTS_TRANSITOIRES:
                raise derniere
            attente = r.headers.get("retry-after")
            time.sleep(float(attente) if attente and attente.isdigit() else 2**n)
        assert derniere is not None
        raise derniere

    def _lire(self, data: dict[str, Any], questions: dict[str, Any], latence: float) -> Decision:
        reponses = {k: Reponse.depuis_json(v) for k, v in (data.get("answers") or {}).items()}
        # Une question sans réponse n'est pas une réponse « non » : c'est un
        # format qui a changé, et le traiter comme une probabilité nulle
        # écarterait en silence tout ce qu'on lui soumet.
        manquantes = sorted(set(questions) - set(reponses))
        if manquantes:
            raise ErreurDecision(f"réponse sans {', '.join(manquantes)} : {str(data)[:300]}")
        usage = data.get("usage") or {}
        return Decision(
            reponses=reponses,
            modele=data.get("model", self.modele),
            id=data.get("id", ""),
            jetons_entree=int(usage.get("input_tokens") or 0),
            cout_usd=usage.get("cost"),
            latence_s=latence,
            brut=data,
        )

    def fermer(self) -> None:
        self._http.close()


__all__ = [
    "ClientDecision",
    "Decision",
    "ErreurDecision",
    "Reponse",
    "choix",
    "echelle",
    "noul",
]
