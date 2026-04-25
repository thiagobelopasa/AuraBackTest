"""Equity Control: aplica regras de stop/restart retroativamente."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from services import analytics

_STRIP_KEYS = {"equity_curve", "drawdown_curve", "mae_mfe", "time_breakdown",
               "direction", "risk_of_ruin", "stagnation"}


def _parse_dt(s: Any) -> datetime | None:
    if not isinstance(s, str):
        return None
    for fmt in ("%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def apply_equity_control(
    trades: list[dict[str, Any]],
    initial_equity: float = 10_000.0,
    stop_after_consec_losses: int | None = None,
    stop_after_dd_pct: float | None = None,
    restart_after_days: int | None = None,
) -> dict[str, Any]:
    """
    Percorre trades em ordem.
    Quando condição de stop é atingida, marca trades seguintes como skipped
    até condição de restart.
    """
    if not trades:
        return {"controlled_equity": [], "original_equity": [],
                "skipped_trades": 0, "metrics_controlled": {}, "metrics_original": {}}

    original_full = analytics.full_analysis(trades, initial_equity)
    original_equity = original_full.get("equity_curve", [])

    equity = initial_equity
    peak_equity = initial_equity
    consec_losses = 0
    stopped = False
    stopped_date: datetime | None = None
    skipped = 0
    active_trades: list[dict[str, Any]] = []

    for t in trades:
        dt = _parse_dt(t.get("time_out") or t.get("time_in"))
        profit = float(t.get("profit", 0.0))

        if stopped and restart_after_days is not None and dt and stopped_date:
            if (dt - stopped_date).days >= restart_after_days:
                stopped = False
                consec_losses = 0

        if stopped:
            skipped += 1
            continue

        equity += profit
        active_trades.append(t)

        if profit > 0:
            consec_losses = 0
            peak_equity = max(peak_equity, equity)
        elif profit < 0:
            consec_losses += 1

        trigger = False
        if stop_after_consec_losses and consec_losses >= stop_after_consec_losses:
            trigger = True
        if stop_after_dd_pct and peak_equity > 0:
            if (peak_equity - equity) / peak_equity >= stop_after_dd_pct:
                trigger = True

        if trigger:
            stopped = True
            stopped_date = dt

    ctrl_full = analytics.full_analysis(active_trades, initial_equity)
    return {
        "controlled_equity": ctrl_full.get("equity_curve", []),
        "original_equity": original_equity,
        "skipped_trades": skipped,
        "metrics_controlled": {k: v for k, v in ctrl_full.items() if k not in _STRIP_KEYS},
        "metrics_original": {k: v for k, v in original_full.items() if k not in _STRIP_KEYS},
    }
