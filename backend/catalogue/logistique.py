"""Régression logistique pondérée, en Python pur.

Elle combine des probabilités de Jev et des jugements de LLM en une seule
probabilité, que des seuils découpent ensuite en trois zones (agir, confirmer,
renvoyer à un humain). Une vingtaine de variables et quelques centaines de cas :
la méthode de Newton avec une pénalité L2 converge en une dizaine
d'itérations, sans numpy ni scikit-learn.

Chaque cas peut porter un poids, l'inverse de sa probabilité d'inclusion quand
le jeu vient d'un tirage stratifié. Les poids sont ramenés à une moyenne de 1,
pour que la pénalité garde le même sens quel que soit le tirage.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Modele:
    """Un modèle ajusté : standardisation des variables, puis coefficients."""

    moyennes: tuple[float, ...]
    ecarts: tuple[float, ...]
    # L'ordonnée à l'origine en tête, puis un coefficient par variable standardisée.
    coefficients: tuple[float, ...]

    def proba(self, x: Sequence[float]) -> float:
        z = self.coefficients[0]
        for c, v, m, e in zip(self.coefficients[1:], x, self.moyennes, self.ecarts, strict=True):
            z += c * (v - m) / e
        return sigmoide(z)


def sigmoide(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


def ajuster(
    x: Sequence[Sequence[float]],
    y: Sequence[int],
    poids: Sequence[float] | None = None,
    *,
    l2: float = 1.0,
    iterations: int = 100,
    tolerance: float = 1e-9,
) -> Modele:
    """Ajuste P(y = 1 | x). `y` vaut 0 ou 1 ; `poids` vaut 1 partout par défaut."""
    n = len(x)
    if n == 0 or n != len(y):
        raise ValueError("x et y doivent avoir la même longueur, non nulle")
    d = len(x[0])
    w = [1.0] * n if poids is None else [float(p) for p in poids]
    total = sum(w)
    w = [p * n / total for p in w]

    moyennes = [sum(w[i] * x[i][j] for i in range(n)) / n for j in range(d)]
    ecarts = []
    for j in range(d):
        variance = sum(w[i] * (x[i][j] - moyennes[j]) ** 2 for i in range(n)) / n
        ecarts.append(math.sqrt(variance) if variance > 1e-12 else 1.0)
    z = [[1.0] + [(x[i][j] - moyennes[j]) / ecarts[j] for j in range(d)] for i in range(n)]

    beta = [0.0] * (d + 1)
    for _ in range(iterations):
        gradient = [0.0] * (d + 1)
        hessienne = [[0.0] * (d + 1) for _ in range(d + 1)]
        for i in range(n):
            p = sigmoide(sum(b * v for b, v in zip(beta, z[i], strict=True)))
            residu = w[i] * (y[i] - p)
            courbure = w[i] * p * (1.0 - p)
            for a in range(d + 1):
                gradient[a] += residu * z[i][a]
                za = courbure * z[i][a]
                for b in range(a, d + 1):
                    hessienne[a][b] += za * z[i][b]
        for a in range(d + 1):
            for b in range(a):
                hessienne[a][b] = hessienne[b][a]
        # La pénalité épargne l'ordonnée à l'origine.
        for a in range(1, d + 1):
            gradient[a] -= l2 * beta[a]
            hessienne[a][a] += l2
        pas = resoudre(hessienne, gradient)
        beta = [b + p for b, p in zip(beta, pas, strict=True)]
        if max(abs(p) for p in pas) < tolerance:
            break
    return Modele(tuple(moyennes), tuple(ecarts), tuple(beta))


def resoudre(a: Sequence[Sequence[float]], b: Sequence[float]) -> list[float]:
    """Résout a · x = b par élimination de Gauss avec pivot partiel."""
    n = len(b)
    m = [list(ligne) + [b[i]] for i, ligne in enumerate(a)]
    for colonne in range(n):
        pivot = max(range(colonne, n), key=lambda i: abs(m[i][colonne]))
        if abs(m[pivot][colonne]) < 1e-15:
            raise ValueError("système singulier")
        m[colonne], m[pivot] = m[pivot], m[colonne]
        for i in range(colonne + 1, n):
            facteur = m[i][colonne] / m[colonne][colonne]
            if facteur:
                for j in range(colonne, n + 1):
                    m[i][j] -= facteur * m[colonne][j]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (m[i][n] - sum(m[i][j] * x[j] for j in range(i + 1, n))) / m[i][i]
    return x


def auc(scores: Sequence[float], y: Sequence[int], poids: Sequence[float] | None = None) -> float:
    """Aire sous la courbe ROC, pondérée : P(score d'un positif > score d'un négatif)."""
    w = [1.0] * len(y) if poids is None else list(poids)
    positifs = [(s, p) for s, v, p in zip(scores, y, w, strict=True) if v == 1]
    negatifs = [(s, p) for s, v, p in zip(scores, y, w, strict=True) if v == 0]
    total = sum(p for _, p in positifs) * sum(p for _, p in negatifs)
    if total == 0:
        return float("nan")
    gagne = 0.0
    for s, p in positifs:
        for t, q in negatifs:
            if s > t:
                gagne += p * q
            elif s == t:
                gagne += 0.5 * p * q
    return gagne / total
