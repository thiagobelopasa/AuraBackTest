"""Money Management Simulator: compara fixed lots vs % risk vs fixed $ risk."""
from __future__ import annotations

from typing import Any

import numpy as np

from services import analytics

_STRIP_KEYS = {"equity_curve", "drawdown_curve", "mae_mfe", "time_breakdown",
               "direction", "risk_of_ruin", "stagnation"}


def simulate_mm(
    trades: list[dict[str, Any]],
    initial_equity: float,
    mm_type: str,
    param: float,
) -> dict[str, Any]:
    """
    Recalcula equity com regra de MM e retorna equity_curve + métricas-chave.

    mm_type:
      "fixed_lots"       — param = lotes fixos (escala profit pelo ratio param/avg_vol)
      "risk_pct"         — param = fração do equity por trade (ex: 0.02 = 2%)
      "fixed_risk_money" — param = valor $ arriscado por trade
    """
    if not trades:
        return {"metrics": {}, "equity_curve": []}

    vols = [float(t.get("volume", 1.0) or 1.0) for t in trades]
    avg_vol = float(np.mean(vols)) if vols else 1.0

    scaled: list[dict[str, Any]] = []
    equity = initial_equity

    for t in trades:
        profit = float(t.get("profit", 0.0))
        trade_risk = abs(profit) if profit < 0 else (abs(profit) * 0.5 or 1e-9)

        if mm_type == "fixed_lots":
            scale = param / avg_vol if avg_vol else 1.0
        elif mm_type == "risk_pct":
            desired = equity * param
            scale = desired / trade_risk if trade_risk else 1.0
        elif mm_type == "fixed_risk_money":
            scale = param / trade_risk if trade_risk else 1.0
        else:
            scale = 1.0

        new_profit = profit * scale
        equity += new_profit
        scaled.append({**t, "profit": new_profit, "balance": equity})

    full = analytics.full_analysis(scaled, initial_equity)
    metrics = {k: v for k, v in full.items() if k not in _STRIP_KEYS}
    return {"metrics": metrics, "equity_curve": full.get("equity_curve", [])}


def run_scenarios(
    trades: list[dict[str, Any]],
    initial_equity: float,
    scenarios: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    results = []
    for s in scenarios:
        r = simulate_mm(trades, initial_equity, s["mm_type"], float(s["param"]))
        results.append({"name": s.get("name", s["mm_type"]), **r})
    return results
