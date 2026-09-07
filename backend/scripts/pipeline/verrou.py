"""Écriture concurrente sûre : verrou de fichier, écriture atomique, ajout.

Le pipeline ingère plusieurs aides en parallèle et trois fichiers sont
PARTAGÉS entre les workers : `data/facts_pending.yaml` (chaque ingestion peut y
proposer un fait), `data/prospection/file-attente.yaml` (chaque worker y écrit
son statut), et les fiches d'état de la prospection.

Ce n'est pas une précaution théorique : le 2026-09-04, deux ingestions HDF
lancées en parallèle ont chacune lu `facts_pending.yaml`, ajouté leur fait, et
réécrit le fichier entier — la seconde a écrasé la première, et les quatre
faits perdus ont dû être reconstruits de mémoire (l'en-tête du fichier en porte
encore la trace). D'où la règle : on ne réécrit jamais un fichier partagé sans
tenir son verrou, et un ajout relit TOUJOURS le fichier sous le verrou.
"""

from __future__ import annotations

import fcntl
import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

# Sondage court : le verrou ne protège que quelques millisecondes d'écriture,
# attendre plus longtemps que ça rendrait la contention visible pour rien.
_PAS_SONDAGE_S = 0.02


class VerrouIndisponible(TimeoutError):
    """Le verrou n'a pas pu être pris dans le délai imparti."""


@contextmanager
def verrou_fichier(chemin: Path, timeout_s: float = 30.0) -> Iterator[None]:
    """Verrou exclusif sur `<chemin>.lock`, le temps du bloc `with`.

    Le verrou porte sur un fichier VOISIN et non sur le fichier lui-même :
    l'écriture atomique remplace l'inode du fichier cible (`os.replace`), et un
    verrou posé sur l'ancien inode ne protégerait plus rien après le premier
    passage.

    `flock` est associé à l'*open file description*, pas au processus : deux
    threads qui ouvrent chacun leur descripteur se bloquent bien l'un l'autre,
    ce qui est exactement ce qu'il faut pour un pool de workers.
    """
    lock_path = chemin.with_name(chemin.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    limite = time.monotonic() + timeout_s
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= limite:
                    raise VerrouIndisponible(
                        f"verrou non obtenu en {timeout_s:g} s sur {lock_path}"
                    ) from None
                time.sleep(_PAS_SONDAGE_S)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def ecrire_atomique(chemin: Path, contenu: str) -> None:
    """Écrit `contenu` dans `chemin` sans jamais laisser de fichier tronqué.

    Un `write_text` interrompu (SIGINT, disque plein) laisse un YAML à moitié
    écrit, que le prochain chargement refusera de parser — et c'est la file
    d'attente ou l'ontologie des faits qui serait perdue.
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)
    tmp = chemin.with_name(f".{chemin.name}.tmp{os.getpid()}")
    tmp.write_text(contenu, encoding="utf-8")
    os.replace(tmp, chemin)


def ajouter_sous_verrou(
    chemin: Path, bloc: str, *, valider: Callable[[str], None], timeout_s: float = 30.0
) -> None:
    """Ajoute `bloc` à la fin de `chemin`, sous verrou, après validation.

    `valider` reçoit le texte COMPLET du fichier tel qu'il serait écrit, pas le
    seul bloc ajouté : c'est la seule façon de refuser une entrée qui, prise
    isolément, est valide mais entre en collision avec ce que le fichier
    contient déjà (une clé de fait en doublon, par exemple). Une exception
    levée par `valider` laisse le fichier strictement intact.
    """
    with verrou_fichier(chemin, timeout_s):
        courant = chemin.read_text(encoding="utf-8") if chemin.exists() else ""
        if courant and not courant.endswith("\n"):
            courant += "\n"
        complet = courant + bloc if bloc.endswith("\n") else courant + bloc + "\n"
        valider(complet)
        ecrire_atomique(chemin, complet)


__all__ = [
    "VerrouIndisponible",
    "ajouter_sous_verrou",
    "ecrire_atomique",
    "verrou_fichier",
]
