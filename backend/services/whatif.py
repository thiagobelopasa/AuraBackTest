"""What-If Analysis: simula exclusão de horas/dias e recalcula métricas."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from services import analytics


def _parse_dt(s: Any) -> datetime | None:
    if not isinstance(s, str):
        return None
    for fmt in ("%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


_STRIP_KEYS = {"equity_curve", "drawdown_curve", "mae_mfe", "time_breakdown",
               "direction", "risk_of_ruin", "stagnation"}


def _key_metrics(m: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in m.items() if k not in _STRIP_KEYS}


def apply_whatif(
    trades: list[dict[str, Any]],
    initial_equity: float = 10_000.0,
    excluded_hours: list[int] | None = None,
    excluded_weekdays: list[int] | None = None,
) -> dict[str, Any]:
    """Filtra trades abertos em horas/dias excluídos e recalcula full_analysis."""
    excluded_hours = set(excluded_hours or [])
    excluded_weekdays = set(excluded_weekdays or [])

    filtered: list[dict[str, Any]] = []
    excluded_count = 0
    for t in trades:
        dt = _parse_dt(t.get("time_in") or t.get("time_out"))
        if dt is not None and (dt.hour in excluded_hours or dt.weekday() in excluded_weekdays):
            excluded_count += 1
        else:
            filtered.append(t)

    original = _key_metrics(analytics.full_analysis(trades, initial_equity))
    whatif = _key_metrics(analytics.full_analysis(filtered, initial_equity))
    return {
        "original": original,
        "whatif": whatif,
        "excluded_trades": excluded_count,
        "remaining_trades": len(filtered),
    }
