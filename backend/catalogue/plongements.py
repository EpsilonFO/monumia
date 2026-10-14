"""Plongements (embeddings) des conditions et des faits : retrouver des voisins, jamais décider.

Un plongement place un texte dans un espace où deux formulations de la même
exigence tombent près l'une de l'autre, même sans un mot en commun (« communes
de moins de 2 000 habitants », « communes rurales »). C'est ce qui manquait à
la recherche lexicale des faits, qui ratait le bon fait une fois sur quatre
(`data/reviews/2026-10-10-faits-jev.md`).

Ce qu'il ne sait PAS faire, et qui interdit de lui confier une décision : la
négation et les nombres. « doit être classé » et « ne doit pas être classé »,
« moins de 2 000 » et « plus de 10 000 » sont voisins. Il propose des
candidats ; un juge qui lit les textes (Jev, un humain) tranche.

Le modèle est le rôle `plongement` du registre. Chaque vecteur est gardé par
empreinte du modèle et du texte EXACT envoyé (consigne comprise), dans une base
SQLite hors du dépôt : `~/.local/share/monumia/plongements.sqlite`, ou le
chemin de `MONUMIA_PLONGEMENTS`. Hors du dépôt parce que le run hebdomadaire
travaille dans une copie jetable qui n'emporte pas les caches, et qu'un vecteur
ne se recalcule pas chaque semaine ; hors de git parce que l'espace pèse
quelque 90 Mo et se reconstruit pour quelques centimes s'il se perd. Ce qui
DÉCIDE (les jugements de Jev) est, lui, suivi par git : cf. `coherence.py`.

Qwen3-Embedding est asymétrique : une REQUÊTE porte une consigne qui dit ce
qu'on cherche (`Instruct: …\\nQuery:…`), un DOCUMENT n'en porte pas. Pour
comparer des conditions entre elles, aucune n'en porte : avec une consigne, les
cosinus se tassent entre 0,86 et 0,94 et aucun seuil ne sépare plus rien
(mesuré le 2026-10-14, cf. `catalogue/coherence.py`).
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from aides_schema import FactDef
from catalogue import registre as registre_mod
from catalogue.openrouter import Client

BACKEND = Path(__file__).resolve().parents[1]
CACHE = Path(
    os.environ.get("MONUMIA_PLONGEMENTS")
    or Path.home() / ".local" / "share" / "monumia" / "plongements.sqlite"
)
ROLE = "plongement"
#: Textes par appel. Les conditions sont courtes ; au-delà, une panne fait
#: rejouer trop de travail.
LOT = 64
PARALLELISME = 4

#: Les consignes, au seul endroit où on les écrit : en changer une invalide le
#: cache des textes qui la portent, et change les voisins de toutes les mesures.
CONSIGNE_CONDITION_VERS_FAIT = (
    "Trouver la question du questionnaire qui permet de vérifier cette condition "
    "d'éligibilité d'une aide au patrimoine"
)
CONSIGNE_MOTS_VERS_FAIT = (
    "Trouver la question du questionnaire d'éligibilité aux aides au patrimoine qui "
    "porte sur ces mots-clés"
)
CONSIGNE_FAIT_VERS_FAIT = (
    "Trouver les questions du questionnaire qui demandent la même information au "
    "propriétaire du monument"
)


def avec_consigne(consigne: str, texte: str) -> str:
    """Le format de requête de Qwen3-Embedding."""
    return f"Instruct: {consigne}\nQuery:{texte}"


def texte_fait(cle: str, fait: FactDef) -> str:
    """Un fait tel qu'on le plonge : la question, son aide, ses réponses, sa clé.

    Du texte naturel, accents compris : la normalisation de la recherche
    lexicale (`_texte_indexe`) aide un comptage de mots, pas un modèle de langue.
    """
    morceaux = [" ".join(fait.question.split())]
    if fait.help:
        morceaux.append(" ".join(fait.help.split()))
    if fait.options:
        morceaux.append("Réponses : " + " ; ".join(o.label for o in fait.options))
    morceaux.append(f"Clé : {cle.replace('_', ' ')}")
    return "\n".join(morceaux)


def _empreinte(modele: str, texte: str) -> str:
    return hashlib.sha256(f"{modele}\0{texte}".encode()).hexdigest()


class Plongeur:
    """Des vecteurs normalisés, pris dans le cache ou demandés au modèle du registre."""

    def __init__(
        self,
        client: Client | None = None,
        *,
        cache: Path = CACHE,
        registre: registre_mod.Registre | None = None,
    ) -> None:
        self._registre = registre or registre_mod.charger()
        self.modele = self._registre.modele(ROLE)
        self._client = client
        cache.parent.mkdir(parents=True, exist_ok=True)
        self._base = sqlite3.connect(cache, check_same_thread=False)
        self._base.execute(
            "create table if not exists vecteurs (cle text primary key, vecteur blob not null)"
        )
        self._verrou = threading.Lock()
        self.cout_usd = 0.0
        self.appels = 0

    def _client_paresseux(self) -> Client:
        # Un cache plein ne demande pas de clé : une mesure rejouée tourne hors ligne.
        if self._client is None:
            self._client = Client()
        return self._client

    def vecteurs(self, textes: Sequence[str]) -> np.ndarray:
        """Une ligne normalisée (float32) par texte, dans l'ordre. Lève `Panne` si un lot échoue."""
        cles = [_empreinte(self.modele.nom, t) for t in textes]
        connus = self._lire(set(cles))
        manquants = list(
            dict.fromkeys(t for t, c in zip(textes, cles, strict=True) if c not in connus)
        )
        if manquants:
            lots = [manquants[i : i + LOT] for i in range(0, len(manquants), LOT)]
            with ThreadPoolExecutor(PARALLELISME) as pool:
                for lot, vecteurs in zip(lots, pool.map(self._demander, lots), strict=True):
                    for texte, v in zip(lot, vecteurs, strict=True):
                        connus[_empreinte(self.modele.nom, texte)] = v
        matrice = np.stack([connus[c] for c in cles]) if cles else np.zeros((0, 1), np.float32)
        normes = np.linalg.norm(matrice, axis=1, keepdims=True)
        return matrice / np.where(normes == 0, 1, normes)

    def _demander(self, lot: list[str]) -> list[np.ndarray]:
        reponse = self._client_paresseux().plonger(
            self.modele.nom,
            lot,
            acceptes=self.modele.acceptes,
            delai_s=self.modele.delai_s,
            role=ROLE,
        )
        vecteurs = [np.asarray(v, dtype=np.float32) for v in reponse.vecteurs]
        with self._verrou:
            self.appels += 1
            self.cout_usd += reponse.cout_usd or 0.0
            self._base.executemany(
                "insert or replace into vecteurs values (?, ?)",
                [
                    (_empreinte(self.modele.nom, t), v.astype(np.float16).tobytes())
                    for t, v in zip(lot, vecteurs, strict=True)
                ],
            )
            self._base.commit()
        return vecteurs

    def _lire(self, cles: set[str]) -> dict[str, np.ndarray]:
        trouves: dict[str, np.ndarray] = {}
        liste = list(cles)
        with self._verrou:
            for i in range(0, len(liste), 500):
                morceau = liste[i : i + 500]
                lignes = self._base.execute(
                    f"select cle, vecteur from vecteurs where cle in ({','.join('?' * len(morceau))})",
                    morceau,
                ).fetchall()
                for cle, blob in lignes:
                    trouves[cle] = np.frombuffer(blob, dtype=np.float16).astype(np.float32)
        return trouves

    def fermer(self) -> None:
        self._base.close()
        if self._client is not None:
            self._client.fermer()


def plus_proches(requetes: np.ndarray, corpus: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """Pour chaque requête, les rangs des `k` lignes du corpus les plus proches et leur cosinus.

    Les vecteurs sont normalisés : le produit scalaire est le cosinus. Rangs et
    scores sont triés du plus proche au plus lointain.
    """
    k = min(k, corpus.shape[0])
    scores = requetes @ corpus.T
    rangs = np.argpartition(-scores, k - 1, axis=1)[:, :k]
    partiels = np.take_along_axis(scores, rangs, axis=1)
    ordre = np.argsort(-partiels, axis=1)
    return np.take_along_axis(rangs, ordre, axis=1), np.take_along_axis(partiels, ordre, axis=1)
