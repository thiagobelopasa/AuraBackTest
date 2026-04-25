"""Probability of Backtest Overfitting (PBO) via CSCV.

Referência: Bailey, Borwein, López de Prado, Zhu (2017) — "The Probability of
Backtest Overfitting".

Entrada: matriz M de retornos (N_pontos × N_candidatos) onde cada coluna é a
série de retornos por candidato (pass/estratégia).

Procedimento CSCV (Combinatorially Symmetric Cross-Validation):
  1. Divide as N_pontos em S subconjuntos contíguos (pares, S par, tipicamente 16)
  2. Para cada combinação C(S, S/2) de subconjuntos como "IS" (in-sample):
     - OOS = complemento
     - rank_is = candidato com melhor métrica em IS
     - rank_oos = rank relativo desse candidato em OOS
     - Registra logit(rank_oos / (1 - rank_oos))
  3. PBO = fração de combinações onde rank_oos é mediana/inferior (ou seja,
     o vencedor em IS vira perdedor em OOS).

Saída:
  - pbo: probabilidade estimada (0..1; quanto menor, melhor; <0.5 = bom)
  - logit_distribution: valores pra plot
  - n_combinations: C(S, S/2)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations
from typing import Any

import numpy as np


@dataclass
class PBOResult:
    pbo: float                       # probability of backtest overfitting ∈ [0, 1]
    n_combinations: int              # C(S, S/2)
    n_candidates: int                # colunas de M
    n_points_per_subset: int         # pontos em cada subset
    subsets: int                     # S
    logits: list[float]              # distribuição de logits pra histograma
    mean_oos_rank: float             # média dos ranks OOS
    performance_degradation: float   # slope IS vs OOS (β < 0 = overfit)
    interpretation: str


def _sharpe_like(series: np.ndarray) -> np.ndarray:
    """Métrica por candidato: Sharpe simples (média / desvio).

    Cada coluna de `series` (shape N×K) vira um escalar (K valores).
    """
    mu = series.mean(axis=0)
    sd = series.std(axis=0, ddof=1)
    sd = np.where(sd == 0, np.nan, sd)
    return mu / sd


def compute_pbo(
    returns_matrix: np.ndarray | list[list[float]],
    subsets: int = 16,
    metric_fn=_sharpe_like,
) -> PBOResult:
    """Calcula PBO via CSCV.

    Args:
        returns_matrix: matriz N_pontos × N_candidatos (cada linha = um
            período; cada coluna = um candidato).
        subsets: S, precisa ser par. Default 16 (C(16,8) = 12,870 combos).
        metric_fn: função que recebe submatriz e devolve vetor de métricas
            por candidato. Default: Sharpe-like (média/desvio).
    """
    M = np.asarray(returns_matrix, dtype=np.float64)
    if M.ndim != 2:
        raise ValueError("returns_matrix precisa ser 2D (N_points × N_candidates)")
    n_points, n_candidates = M.shape
    if n_candidates < 2:
        raise ValueError(f"Precisa de ≥2 candidatos, recebido {n_candidates}")
    if subsets % 2 != 0:
        raise ValueError(f"`subsets` precisa ser par, recebido {subsets}")
    if n_points < subsets:
        raise ValueError(f"Poucos pontos ({n_points}) para {subsets} subsets")

    # Particiona em S subsets contíguos de tamanho aprox. igual
    subset_idx = np.array_split(np.arange(n_points), subsets)
    all_subsets = set(range(subsets))

    half = subsets // 2
    logits: list[float] = []
    oos_ranks: list[float] = []
    is_metrics: list[float] = []
    oos_metrics: list[float] = []

    for is_subsets in combinations(range(subsets), half):
        oos_subsets = tuple(all_subsets - set(is_subsets))
        is_rows = np.concatenate([subset_idx[i] for i in is_subsets])
        oos_rows = np.concatenate([subset_idx[i] for i in oos_subsets])

        # Métrica por candidato em IS e OOS
        is_perf = metric_fn(M[is_rows, :])
        oos_perf = metric_fn(M[oos_rows, :])
        if not np.any(np.isfinite(is_perf)):
            continue

        # Best candidate em IS
        best_k = int(np.nanargmax(is_perf))

        # Rank relativo do best_k em OOS (0 = pior, 1 = melhor)
        # Fração de candidatos com OOS pior que o best_k
        oos_val = oos_perf[best_k]
        if not np.isfinite(oos_val):
            continue
        valid = oos_perf[np.isfinite(oos_perf)]
        if len(valid) < 2:
            continue
        # Rank percentil (1.0 = topo, 0.0 = base)
        rank = float(np.mean(valid < oos_val))
        # Clampa em (eps, 1-eps) pra evitar divisão por zero no logit
        eps = 1e-6
        rank_c = max(eps, min(1 - eps, rank))
        logit = math.log(rank_c / (1 - rank_c))

        logits.append(logit)
        oos_ranks.append(rank)
        is_metrics.append(float(is_perf[best_k]))
        oos_metrics.append(float(oos_val))

    n_combos = len(logits)
    if n_combos == 0:
        raise RuntimeError("Nenhuma combinação CSCV válida. Dados muito ruidosos?")

    # PBO = fração de combos onde rank OOS < 0.5 (abaixo da mediana)
    pbo = float(np.mean(np.array(oos_ranks) < 0.5))

    # Performance degradation: regressão IS vs OOS
    is_arr = np.array(is_metrics)
    oos_arr = np.array(oos_metrics)
    if is_arr.std() > 0:
        slope = float(np.cov(is_arr, oos_arr)[0, 1] / is_arr.var())
    else:
        slope = 0.0

    if pbo < 0.25:
        interpretation = (
            "Robusto: baixa probabilidade de overfit. Os vencedores em IS "
            "continuam bem em OOS na maioria das combinações."
        )
    elif pbo < 0.5:
        interpretation = (
            "Moderado: alguns sinais de overfit, mas a maioria dos candidatos "
            "segura performance em OOS."
        )
    elif pbo < 0.75:
        interpretation = (
            "Alto risco de overfit: mais da metade das combinações CSCV mostra "
            "o vencedor IS virando abaixo da mediana em OOS."
        )
    else:
        interpretation = (
            "OVERFIT SEVERO: quase nunca o vencedor IS mantém rank em OOS. "
            "Os resultados da otimização são provavelmente ruído."
        )

    return PBOResult(
        pbo=pbo,
        n_combinations=n_combos,
        n_candidates=n_candidates,
        n_points_per_subset=len(subset_idx[0]),
        subsets=subsets,
        logits=logits,
        mean_oos_rank=float(np.mean(oos_ranks)),
        performance_degradation=slope,
        interpretation=interpretation,
    )


def equity_curves_to_returns_matrix(
    equity_curves: list[list[float]],
    min_points: int = 32,
) -> np.ndarray:
    """Converte lista de equity curves (uma por candidato) em matriz de retornos.

    Cada equity curve pode ter tamanhos diferentes; alinhamos todos ao
    comprimento do menor (>= min_points). Retornos = diff/equity[i-1].
    """
    lengths = [len(eq) for eq in equity_curves if eq and len(eq) >= 2]
    if not lengths:
        raise ValueError("Nenhuma equity curve válida")
    n = min(lengths)
    if n < min_points:
        raise ValueError(
            f"Equity curves muito curtas (min={n}); precisa ≥{min_points} pontos"
        )
    # Alinha todas ao tamanho n (trunca à esquerda — pega os n últimos)
    aligned = []
    for eq in equity_curves:
        if not eq or len(eq) < 2:
            continue
        arr = np.asarray(eq[-n:], dtype=np.float64)
        prev = arr[:-1]
        # Evita divisão por zero
        safe_prev = np.where(np.abs(prev) < 1e-12, np.nan, prev)
        rets = np.diff(arr) / safe_prev
        aligned.append(rets)
    if len(aligned) < 2:
        raise ValueError("Precisa de ≥2 equity curves válidas")
    return np.column_stack(aligned)


def as_dict(r: PBOResult) -> dict[str, Any]:
    return {
        "pbo": r.pbo,
        "n_combinations": r.n_combinations,
        "n_candidates": r.n_candidates,
        "n_points_per_subset": r.n_points_per_subset,
        "subsets": r.subsets,
        "logits": r.logits,
        "mean_oos_rank": r.mean_oos_rank,
        "performance_degradation": r.performance_degradation,
        "interpretation": r.interpretation,
    }
