"""Tests do cálculo PBO (Bailey & López de Prado)."""
from __future__ import annotations

import numpy as np

from services.pbo import compute_pbo, equity_curves_to_returns_matrix


def test_pbo_random_data_sanity():
    """Retornos puramente aleatórios: PBO deve estar num range plausível
    e os metadados devem bater. Não testamos um range apertado porque depende
    muito de tamanho da amostra / número de subsets.
    """
    np.random.seed(42)
    M = np.random.randn(200, 30) * 0.01
    r = compute_pbo(M, subsets=8)
    assert 0.0 <= r.pbo <= 1.0
    assert r.n_combinations > 0
    assert r.n_candidates == 30
    assert len(r.logits) == r.n_combinations


def test_pbo_with_real_skill_is_low():
    """Se UM candidato realmente tem skill (média positiva), PBO deve ser baixo."""
    np.random.seed(7)
    M = np.random.randn(200, 30) * 0.01
    # Candidato 0 tem média positiva em todo o histórico
    M[:, 0] += 0.005
    r = compute_pbo(M, subsets=8)
    # Skill verdadeira gera PBO menor (não é garantido 0, mas é menor que random puro)
    assert r.pbo < 0.5


def test_pbo_rejects_odd_subsets():
    import pytest
    M = np.random.randn(50, 10)
    with pytest.raises(ValueError, match="par"):
        compute_pbo(M, subsets=7)


def test_equity_curves_to_returns_matrix_shape():
    # 3 candidatos com equity curves de 100 pontos
    eq_curves = [list(1000 + np.cumsum(np.random.randn(100))) for _ in range(3)]
    M = equity_curves_to_returns_matrix(eq_curves, min_points=50)
    assert M.shape[1] == 3
    assert M.shape[0] == 99  # diff de 100 pontos
