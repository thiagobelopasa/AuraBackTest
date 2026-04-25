"""Monte Carlo sobre lista de trades.

Duas técnicas clássicas implementadas:

1. **Shuffle (permutation)**: reembaralha a ORDEM dos trades N vezes.
   Preserva todos os trades originais; muda só o sequenciamento.
   Responde: "se esses mesmos trades caíssem em outra ordem, qual o DD esperado?"

2. **Bootstrap (resample with replacement)**: sorteia N trades de volta com
   reposição. Responde: "se o sistema rodasse mais tempo com a mesma
   distribuição, qual a distribuição de resultados possíveis?"

Saídas: percentis (P5, P50, P95) de net_profit e max_drawdown_pct + a trajetória
da curva de equity mediana + distribuição para plotagem no frontend.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class MonteCarloResult:
    mode: str                           # "shuffle" ou "bootstrap"
    runs: int
    net_profit_p5: float
    net_profit_p50: float
    net_profit_p95: float
    max_dd_pct_p5: float
    max_dd_pct_p50: float
    max_dd_pct_p95: float
    prob_profitable: float              # % runs com lucro > 0
    prob_dd_exceeds_original: float     # % runs com DD maior que o original
    # Histogramas (bins + counts) para o frontend plotar
    net_profit_hist: dict[str, list[float]]
    max_dd_hist: dict[str, list[float]]

    def to_dict(self) -> dict[str, Any]:
        d = self.__dict__.copy()
        return d


def _run_simulation(
    profits: np.ndarray,
    initial: float,
    runs: int,
    mode: str,
    rng: np.random.Generator,
    skip_pct: float = 0.1,
    noise_pct: float = 0.1,
) -> tuple[np.ndarray, np.ndarray]:
    """Executa N simulações e retorna (net_profits, max_dd_pcts).

    Modos:
        shuffle    - reembaralha ordem
        bootstrap  - reamostra com reposição
        skip       - remove aleatoriamente skip_pct dos trades (preserva ordem)
        noise      - aplica jitter ±noise_pct em cada lucro (simula slippage)
    """
    n = profits.size
    net_profits = np.empty(runs, dtype=np.float64)
    max_dd_pcts = np.empty(runs, dtype=np.float64)
    for i in range(runs):
        if mode == "shuffle":
            seq = rng.permutation(profits)
        elif mode == "bootstrap":
            idx = rng.integers(0, n, size=n)
            seq = profits[idx]
        elif mode == "skip":
            mask = rng.random(n) >= skip_pct
            seq = profits[mask] if mask.any() else profits
        elif mode == "noise":
            jitter = 1.0 + rng.uniform(-noise_pct, noise_pct, size=n)
            seq = profits * jitter
        else:
            raise ValueError(f"modo desconhecido: {mode}")
        values = initial + np.cumsum(seq)
        net_profits[i] = values[-1] - initial
        peaks = np.maximum.accumulate(np.concatenate([[initial], values]))
        trough_values = np.concatenate([[initial], values])
        dd_abs = peaks - trough_values
        dd_pct = np.where(peaks > 0, dd_abs / peaks, 0.0)
        max_dd_pcts[i] = float(np.max(dd_pct)) * 100
    return net_profits, max_dd_pcts


def _histogram(values: np.ndarray, bins: int = 30) -> dict[str, list[float]]:
    counts, edges = np.histogram(values, bins=bins)
    return {"edges": edges.tolist(), "counts": counts.tolist()}


def monte_carlo(
    trades: list[dict[str, Any]],
    initial_equity: float = 10_000.0,
    runs: int = 1000,
    mode: str = "shuffle",
    seed: int | None = None,
    skip_pct: float = 0.1,
    noise_pct: float = 0.1,
) -> MonteCarloResult:
    """Roda Monte Carlo sobre os trades e retorna distribuições.

    `mode`:
        'shuffle'   → reembaralha a ordem dos trades
        'bootstrap' → sorteia com reposição (amostra do mesmo tamanho)
    """
    if not trades:
        empty = np.zeros(1)
        return MonteCarloResult(
            mode=mode, runs=0, net_profit_p5=0.0, net_profit_p50=0.0,
            net_profit_p95=0.0, max_dd_pct_p5=0.0, max_dd_pct_p50=0.0,
            max_dd_pct_p95=0.0, prob_profitable=0.0,
            prob_dd_exceeds_original=0.0,
            net_profit_hist=_histogram(empty),
            max_dd_hist=_histogram(empty),
        )

    profits = np.array([float(t["profit"]) for t in trades], dtype=np.float64)
    rng = np.random.default_rng(seed)

    net_profits, max_dds = _run_simulation(
        profits, initial_equity, runs, mode, rng,
        skip_pct=skip_pct, noise_pct=noise_pct,
    )

    # DD original (sequência real)
    original_values = initial_equity + np.cumsum(profits)
    original_peaks = np.maximum.accumulate(
        np.concatenate([[initial_equity], original_values])
    )
    original_dd = original_peaks - np.concatenate([[initial_equity], original_values])
    original_dd_pct = float(np.max(np.where(original_peaks > 0, original_dd / original_peaks, 0.0))) * 100

    return MonteCarloResult(
        mode=mode,
        runs=runs,
        net_profit_p5=float(np.percentile(net_profits, 5)),
        net_profit_p50=float(np.percentile(net_profits, 50)),
        net_profit_p95=float(np.percentile(net_profits, 95)),
        max_dd_pct_p5=float(np.percentile(max_dds, 5)),
        max_dd_pct_p50=float(np.percentile(max_dds, 50)),
        max_dd_pct_p95=float(np.percentile(max_dds, 95)),
        prob_profitable=float(np.mean(net_profits > 0)),
        prob_dd_exceeds_original=float(np.mean(max_dds > original_dd_pct)),
        net_profit_hist=_histogram(net_profits),
        max_dd_hist=_histogram(max_dds),
    )
