"""Proportions et intervalles de confiance des mesures.

Wilson à 95 % pour une proportion simple. Pour un tirage stratifié, chaque cas
pèse l'inverse de sa probabilité d'inclusion ; l'intervalle se calcule alors sur
l'effectif efficace de Kish, (somme des poids)² / somme des poids², ce qui
reste une approximation : elle est dite dans les rapports.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

Z95 = 1.959963984540054


@dataclass(frozen=True)
class Proportion:
    """Une proportion, son intervalle, et ce sur quoi elle porte."""

    p: float
    bas: float
    haut: float
    numerateur: float
    denominateur: float
    effectif: float

    def texte(self, pondere: bool = False) -> str:
        """« k/n = p % [bas ; haut] », virgule décimale, comme dans les rapports."""
        if self.denominateur == 0:
            return "0/0"
        if pondere:
            tete = f"{fr(100 * self.p, 1)} % pondéré (effectif {fr(self.effectif, 0)})"
        else:
            tete = f"{int(self.numerateur)}/{int(self.denominateur)} = {fr(100 * self.p, 1)} %"
        return f"{tete} [{fr(100 * self.bas, 1)} ; {fr(100 * self.haut, 1)}]"


def fr(x: float, decimales: int) -> str:
    """Un nombre à la française : virgule décimale."""
    return f"{x:.{decimales}f}".replace(".", ",")


def _bornes(p: float, n: float, z: float = Z95) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    marge = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - marge), min(1.0, centre + marge)


def wilson(k: int, n: int) -> Proportion:
    """Proportion k/n avec son intervalle de Wilson à 95 %."""
    if n == 0:
        return Proportion(0.0, 0.0, 1.0, 0, 0, 0)
    p = k / n
    bas, haut = _bornes(p, n)
    return Proportion(p, bas, haut, k, n, n)


def ponderee(cas: Iterable[tuple[bool, float]]) -> Proportion:
    """Proportion pondérée : chaque cas est (vrai ou faux, poids)."""
    poids = [(bool(x), float(w)) for x, w in cas if w > 0]
    total = sum(w for _, w in poids)
    if total == 0:
        return Proportion(0.0, 0.0, 1.0, 0, 0, 0)
    vrais = sum(w for x, w in poids if x)
    effectif = total * total / sum(w * w for _, w in poids)
    p = vrais / total
    bas, haut = _bornes(p, effectif)
    return Proportion(p, bas, haut, vrais, total, effectif)
