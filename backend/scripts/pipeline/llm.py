"""Résolution du modèle par rôle, et comptage du coût.

Le pipeline fait appel à cinq modèles pour cinq métiers différents, qui n'ont
ni le même volume ni la même exigence : trier trois cents URL au kilo ne
demande pas le modèle qui typera une condition d'éligibilité. D'où un ROLE par
métier, et un modèle réglable par rôle sans toucher au code :

    LLM_MODEL_INGESTION=glm-flash
    LLM_MODEL_VERIFICATION=ds-pro
    LLM_MODEL_TRI=ds-flash

C'est providall qui lit ces variables (`Client(role=…)`) : la résolution
`argument > LLM_MODEL_<ROLE> > LLM_MODEL` est la sienne, on ne la redouble pas.

Le comptage, lui, est explicite : chaque appelant passe sa `Response` au
`Compteur`. Rien ne transite par le hook `on_response` de providall, dont les
exceptions sont avalées — un plafond de budget posé là ne s'appliquerait
jamais, et personne ne le verrait.
"""

from __future__ import annotations

import threading
from dataclasses import replace as _remplacer
from pathlib import Path
from typing import Any

import providall
from providall import Client, ModelSpec, Resolution, Response, Usage
from providall.config import resolve as _resolve

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

# Les cinq métiers. `decouverte` sert à trouver la rubrique « aides » d'un site
# inconnu, `tri` à classer des URL en lot, `lecture` à qualifier une fiche,
# `ingestion` à écrire le YAML, `verification` à le réfuter.
ROLES: tuple[str, ...] = ("tri", "lecture", "decouverte", "ingestion", "verification")


def charger_env(directory: Path = BACKEND_DIR) -> list[Path]:
    """Charge `.env` puis `.env.local` de `backend/`. Appelé par les CLI."""
    return providall.load_env(directory)


def resolution_pour(role: str, modele: str | None = None) -> Resolution:
    """Le modèle retenu pour ce rôle, ET la raison — affichée par `--dry-run`."""
    _verifier_role(role)
    return _resolve(modele, role=role)


def client_pour(role: str, modele: str | None = None, **kw: Any) -> Client:
    """Client providall pour un rôle. `modele` explicite l'emporte sur l'environnement."""
    _verifier_role(role)
    return Client(modele, role=role, label=role, **kw)


def _verifier_role(role: str) -> None:
    if role not in ROLES:
        raise ValueError(f"rôle inconnu : {role!r} — connus : {', '.join(ROLES)}")


# --------------------------------------------------------------------------
# Tarifs
# --------------------------------------------------------------------------


def parse_tarif(valeur: str) -> tuple[float, float]:
    """« 0.07,0.25 » → (entrée, sortie), en dollars par million de jetons."""
    morceaux = [m.strip() for m in valeur.split(",")]
    if len(morceaux) != 2:
        raise ValueError(f"tarif attendu sous la forme « entrée,sortie », reçu : {valeur!r}")
    entree, sortie = (float(m) for m in morceaux)
    return entree, sortie


def enregistrer_tarif(alias: str, price_in: float, price_out: float) -> ModelSpec:
    """Pose le tarif d'un modèle que le registre providall ne connaît pas encore.

    Sans tarif, `Response.cost_usd` vaut None — providall refuse d'inventer un
    zéro, et il a raison : un 0,00 $ additionné dans un benchmark fausse la
    comparaison sans que personne ne le voie. Mais un budget exprimé en dollars
    ne fonctionne pas non plus. Cette échappatoire permet de renseigner le
    tarif depuis la ligne de commande le temps que le registre soit corrigé en
    amont ; `dataclasses.replace` plutôt que `providall.spec()` pour ne pas
    perdre au passage les surcharges de capacités du modèle.
    """
    base = providall.resolve_spec(alias)
    corrige = _remplacer(
        base,
        price_in=price_in,
        price_out=price_out,
        price_cache_read=price_in / 10,
    )
    providall.register_model(corrige, replace=True)
    return corrige


# --------------------------------------------------------------------------
# Compteur
# --------------------------------------------------------------------------


class Compteur:
    """Cumul des jetons et du coût, sûr entre threads.

    `cout_inconnu` est le drapeau qui compte : dès qu'un appel n'a pas de
    tarif, le total en dollars est SOUS-ESTIMÉ et ne peut plus servir de
    plafond. L'appelant bascule alors sur le budget en jetons d'entrée.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._usage = Usage()
        self._cout = 0.0
        self._cout_inconnu = False
        self._appels = 0
        self._par_etiquette: dict[str, tuple[int, float]] = {}

    def ajouter(self, response: Response, etiquette: str = "") -> None:
        with self._lock:
            self._usage = self._usage + response.usage
            self._appels += 1
            if response.cost_usd is None:
                self._cout_inconnu = True
            else:
                self._cout += response.cost_usd
            n, cumul = self._par_etiquette.get(etiquette, (0, 0.0))
            self._par_etiquette[etiquette] = (n + 1, cumul + (response.cost_usd or 0.0))

    @property
    def usage(self) -> Usage:
        with self._lock:
            return self._usage

    @property
    def cout_usd(self) -> float:
        """Coût cumulé des appels TARIFÉS. À lire avec `cout_inconnu`."""
        with self._lock:
            return self._cout

    @property
    def cout_inconnu(self) -> bool:
        with self._lock:
            return self._cout_inconnu

    @property
    def appels(self) -> int:
        with self._lock:
            return self._appels

    @property
    def tokens_in(self) -> int:
        """Tout le côté entrée, cache compris — c'est lui qu'on plafonne.

        `Usage.input_tokens` exclut les jetons lus en cache ; s'en tenir à lui
        ferait passer une conversation de 90 k jetons pour une de 3 k dès que
        le cache de préfixe mord, et le plafond ne se déclencherait jamais.
        """
        u = self.usage
        return u.input_tokens + u.cache_read_tokens + u.cache_write_tokens

    @property
    def tokens_out(self) -> int:
        return self.usage.output_tokens

    def fusionner(self, autre: Compteur, etiquette: str = "") -> None:
        """Absorbe le cumul d'un autre compteur, en un seul geste.

        Les workers comptent chacun dans leur `Compteur` local, puis versent
        leur total au compteur global à la FIN. Y ajouter chaque appel en
        direct depuis plusieurs threads ferait dépendre le budget total de
        l'ordonnancement, et donc d'un run à l'autre.
        """
        with self._lock:
            self._usage = self._usage + autre.usage
            self._appels += autre.appels
            self._cout_inconnu = self._cout_inconnu or autre.cout_inconnu
            self._cout += autre.cout_usd
            n, cumul = self._par_etiquette.get(etiquette, (0, 0.0))
            self._par_etiquette[etiquette] = (n + autre.appels, cumul + autre.cout_usd)

    def par_etiquette(self) -> dict[str, tuple[int, float]]:
        with self._lock:
            return dict(self._par_etiquette)

    def resume(self) -> str:
        cout = "coût inconnu (tarif absent du registre)" if self.cout_inconnu else ""
        chiffre = f"${self.cout_usd:.4f}"
        return (
            f"{self.appels} appel(s), {self.tokens_in:,} jetons entrée / "
            f"{self.tokens_out:,} sortie, {chiffre}{' — ' + cout if cout else ''}"
        ).replace(",", " ")


__all__ = [
    "BACKEND_DIR",
    "ROLES",
    "Compteur",
    "charger_env",
    "client_pour",
    "enregistrer_tarif",
    "parse_tarif",
    "resolution_pour",
]
