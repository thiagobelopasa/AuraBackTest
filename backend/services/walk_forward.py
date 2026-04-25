"""Walk-Forward Analysis: teste de robustez/overfitting via folds IS/OOS.

Ideia: dividir o período total em N janelas sequenciais. Para cada janela:
    - In-Sample (IS):  otimiza os parâmetros do EA
    - Out-of-Sample (OOS): roda os parâmetros vencedores em dados não vistos

Um sistema robusto tem **performance OOS ≈ performance IS**. Se a OOS despenca,
os parâmetros estão ajustados demais ao passado (overfit).

Este módulo só implementa a LÓGICA DE SPLIT e AGREGAÇÃO. A execução de cada
fold (otimização IS + backtest OOS no MT5) vem de mt5_runner + optimizer.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import numpy as np


@dataclass
class WFAFold:
    """Uma janela da Walk-Forward Analysis."""
    idx: int
    is_start: date
    is_end: date
    oos_start: date
    oos_end: date


@dataclass
class WFAResult:
    folds: list[WFAFold]
    is_metrics: list[dict[str, Any]]   # métrica por fold no IS
    oos_metrics: list[dict[str, Any]]  # métrica por fold no OOS
    stability_score: float             # OOS_mean / IS_mean — próximo de 1 = robusto
    consistency: float                 # % de folds com OOS positivo
    degradation: float                 # (IS_mean - OOS_mean) / IS_mean


def split_folds(
    start: date,
    end: date,
    folds: int,
    oos_pct: float = 0.25,
    anchored: bool = False,
) -> list[WFAFold]:
    """Divide o período em `folds` janelas sequenciais.

    `anchored=True` → IS sempre começa em `start` (cresce); OOS desliza.
    `anchored=False` (default) → rolling window, tamanho IS fixo.
    `oos_pct` → fração de cada janela que vira OOS (ex: 0.25 = 25% OOS, 75% IS).
    """
    if folds < 1:
        raise ValueError("folds deve ser >= 1")
    if not (0 < oos_pct < 1):
        raise ValueError("oos_pct deve estar em (0, 1)")

    total_days = (end - start).days
    if total_days <= 0:
        raise ValueError("end deve ser posterior a start")

    # Cada fold ocupa total/folds dias; desse bloco, oos_pct é OOS.
    fold_days = total_days / folds
    oos_days = fold_days * oos_pct
    is_days = fold_days - oos_days

    result: list[WFAFold] = []
    for i in range(folds):
        fold_start = start + timedelta(days=int(round(i * fold_days)))
        fold_end = start + timedelta(days=int(round((i + 1) * fold_days)))
        if anchored:
            is_start = start
        else:
            is_start = fold_start
        oos_start = fold_end - timedelta(days=int(round(oos_days)))
        oos_end = fold_end
        is_end = oos_start
        result.append(
            WFAFold(
                idx=i,
                is_start=is_start,
                is_end=is_end,
                oos_start=oos_start,
                oos_end=oos_end,
            )
        )
    return result


def compute_wfa_score(
    is_metrics: list[dict[str, Any]],
    oos_metrics: list[dict[str, Any]],
    score_field: str = "net_profit",
) -> WFAResult:
    """Agrega métricas dos folds e computa scores de robustez.

    `score_field`: qual métrica usar ('net_profit', 'profit_factor', 'sharpe_ratio').
    """
    is_scores = np.array([m.get(score_field, 0.0) for m in is_metrics], dtype=np.float64)
    oos_scores = np.array([m.get(score_field, 0.0) for m in oos_metrics], dtype=np.float64)

    is_mean = float(is_scores.mean()) if is_scores.size else 0.0
    oos_mean = float(oos_scores.mean()) if oos_scores.size else 0.0

    stability = (oos_mean / is_mean) if is_mean != 0 else 0.0
    degradation = ((is_mean - oos_mean) / is_mean) if is_mean != 0 else 0.0
    consistency = float(np.mean(oos_scores > 0)) if oos_scores.size else 0.0

    return WFAResult(
        folds=[],  # preenchido pelo orquestrador
        is_metrics=is_metrics,
        oos_metrics=oos_metrics,
        stability_score=stability,
        consistency=consistency,
        degradation=degradation,
    )
