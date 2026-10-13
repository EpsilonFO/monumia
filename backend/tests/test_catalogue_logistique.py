"""La régression logistique du paquet `catalogue` : ajustement, poids, AUC."""

from __future__ import annotations

import math
import random

import pytest

from catalogue.logistique import ajuster, auc, resoudre, sigmoide


def test_resoudre_un_systeme_lineaire():
    x = resoudre([[2.0, 1.0], [1.0, 3.0]], [3.0, 5.0])
    assert x == pytest.approx([0.8, 1.4])


def test_resoudre_refuse_un_systeme_singulier():
    with pytest.raises(ValueError):
        resoudre([[1.0, 2.0], [2.0, 4.0]], [1.0, 2.0])


def test_sigmoide_reste_finie_aux_extremes():
    assert sigmoide(1000.0) == pytest.approx(1.0)
    assert sigmoide(-1000.0) == pytest.approx(0.0)
    assert sigmoide(0.0) == 0.5


def test_ajuster_retrouve_la_pente_d_un_modele_connu():
    rng = random.Random(1)
    x, y = [], []
    for _ in range(4000):
        v = rng.gauss(0.0, 1.0)
        x.append([v])
        y.append(1 if rng.random() < sigmoide(0.5 + 2.0 * v) else 0)
    modele = ajuster(x, y, l2=0.0)
    # Coefficient sur la variable standardisée : 2,0 fois l'écart-type observé.
    pente = modele.coefficients[1] / modele.ecarts[0]
    assert pente == pytest.approx(2.0, rel=0.1)
    assert modele.proba([0.0]) == pytest.approx(sigmoide(0.5), abs=0.03)


def test_ajuster_reste_fini_sur_des_donnees_separees():
    x = [[float(i)] for i in range(20)]
    y = [0] * 10 + [1] * 10
    modele = ajuster(x, y, l2=1.0)
    assert all(math.isfinite(c) for c in modele.coefficients)
    assert modele.proba([0.0]) < 0.5 < modele.proba([19.0])


def test_un_poids_double_vaut_un_cas_duplique():
    x = [[0.0], [1.0], [2.0], [3.0], [1.5]]
    y = [0, 0, 1, 1, 1]
    duplique = ajuster(x + [[1.5]], y + [1], l2=0.5)
    pondere = ajuster(x, y, [1.0, 1.0, 1.0, 1.0, 2.0], l2=0.5 * 5 / 6)
    assert pondere.proba([1.2]) == pytest.approx(duplique.proba([1.2]), abs=1e-6)


def test_auc():
    assert auc([0.1, 0.4, 0.35, 0.8], [0, 0, 1, 1]) == pytest.approx(0.75)
    assert auc([0.2, 0.2], [0, 1]) == pytest.approx(0.5)
    assert math.isnan(auc([0.1, 0.2], [1, 1]))
