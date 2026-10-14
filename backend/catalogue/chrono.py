"""Les durées d'un run, étape par étape : où passe le temps.

Une étape cumule ses durées et compte ses passages ; plusieurs fils peuvent
mesurer en même temps (les ré-extractions en vol). Le rapport les rend de la
plus longue à la plus courte. Une étape « horloge » est un temps mur (début à
fin d'un ensemble qui tourne en parallèle), les autres sont des sommes.
"""

from __future__ import annotations

import threading
import time
from collections import Counter
from collections.abc import Iterator, Mapping
from contextlib import contextmanager


def duree_lisible(s: float) -> str:
    """« 3 h 05 », « 12 min 04 s », « 7,4 s »."""
    if s >= 3600:
        return f"{int(s // 3600)} h {int(s % 3600 // 60):02d}"
    if s >= 60:
        return f"{int(s // 60)} min {int(s % 60):02d} s"
    return f"{s:.1f} s".replace(".", ",")


class Chrono:
    def __init__(self) -> None:
        self.durees: dict[str, float] = {}
        self.passages: Counter[str] = Counter()
        self._verrou = threading.Lock()

    def ajouter(self, etape: str, secondes: float, passages: int = 1) -> None:
        with self._verrou:
            self.durees[etape] = self.durees.get(etape, 0.0) + secondes
            self.passages[etape] += passages

    def fusionner(self, prefixe: str, durees: Mapping[str, float]) -> None:
        """Les durées d'un sous-processus (l'agent d'une ré-extraction), sous un préfixe."""
        for k, v in durees.items():
            self.ajouter(f"{prefixe}{k}", float(v))

    @contextmanager
    def mesurer(self, etape: str) -> Iterator[None]:
        debut = time.perf_counter()
        try:
            yield
        finally:
            self.ajouter(etape, time.perf_counter() - debut)

    def lignes(self) -> list[str]:
        """Une ligne par étape, de la plus longue à la plus courte."""
        sortie = []
        for etape, s in sorted(self.durees.items(), key=lambda x: -x[1]):
            n = self.passages[etape]
            moyenne = f" ({n} fois, {duree_lisible(s / n)} en moyenne)" if n > 1 else ""
            sortie.append(f"- {etape} : {duree_lisible(s)}{moyenne}")
        return sortie
