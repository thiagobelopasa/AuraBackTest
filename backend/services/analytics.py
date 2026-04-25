"""Métricas de performance estilo QuantAnalyzer, calculadas a partir da lista de trades.

Input: lista de dicts `{time_in, time_out, side, volume, entry_price, exit_price,
profit, balance, duration_sec}` — formato produzido por `mt5_report.deals_to_trades`.

Todas as funções são puras (sem I/O). Não dependem de polars nem pandas —
numpy só para vetorização quando compensar.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np


# ------------------------------------------------------------ Curva de equity
@dataclass
class EquityCurve:
    """Série de pontos da curva de equity a partir de uma lista de trades."""
    values: np.ndarray          # equity após cada trade (shape N+1, começa em initial)
    peaks: np.ndarray           # pico corrente até aquele ponto
    drawdown_abs: np.ndarray    # DD absoluto (peak - value)
    drawdown_pct: np.ndarray    # DD em % do peak
    returns: np.ndarray         # retorno por trade (profit / equity anterior)


def build_equity_curve(trades: list[dict[str, Any]], initial: float) -> EquityCurve:
    profits = np.array([float(t.get("profit", 0.0)) for t in trades], dtype=np.float64)
    values = np.concatenate([[initial], initial + np.cumsum(profits)])
    peaks = np.maximum.accumulate(values)
    dd_abs = peaks - values
    dd_pct = np.where(peaks > 0, dd_abs / peaks, 0.0)
    # retornos por trade (profit relativo à equity anterior)
    prev = values[:-1]
    returns = np.where(prev > 0, profits / prev, 0.0)
    return EquityCurve(
        values=values, peaks=peaks, drawdown_abs=dd_abs,
        drawdown_pct=dd_pct, returns=returns,
    )


# ---------------------------------------------------------------- Drawdown
def max_drawdown(eq: EquityCurve) -> tuple[float, float, int, int]:
    """Retorna (dd_abs_max, dd_pct_max, peak_idx, trough_idx)."""
    if eq.drawdown_abs.size == 0:
        return 0.0, 0.0, 0, 0
    trough = int(np.argmax(eq.drawdown_abs))
    dd_abs = float(eq.drawdown_abs[trough])
    dd_pct = float(eq.drawdown_pct[trough])
    peak = int(np.argmax(eq.values[: trough + 1]))
    return dd_abs, dd_pct, peak, trough


def ulcer_index(eq: EquityCurve) -> float:
    """Ulcer Index: RMS do drawdown em % — penaliza profundidade E duração do DD."""
    if eq.drawdown_pct.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(eq.drawdown_pct * 100))))


# ---------------------------------------------------------- Razões clássicas
def sharpe_ratio(returns: np.ndarray, risk_free_rate: float = 0.0) -> float:
    """Sharpe por trade (não anualizado). Anualização precisa da frequência."""
    if returns.size < 2:
        return 0.0
    excess = returns - risk_free_rate
    std = float(np.std(excess, ddof=1))
    if std == 0:
        return 0.0
    return float(np.mean(excess) / std)


def sortino_ratio(returns: np.ndarray, risk_free_rate: float = 0.0) -> float:
    """Sortino: usa só desvio dos retornos negativos (downside deviation)."""
    if returns.size < 2:
        return 0.0
    excess = returns - risk_free_rate
    downside = excess[excess < 0]
    if downside.size == 0:
        return float("inf") if np.mean(excess) > 0 else 0.0
    dd = float(np.sqrt(np.mean(np.square(downside))))
    if dd == 0:
        return 0.0
    return float(np.mean(excess) / dd)


def calmar_ratio(net_profit: float, max_dd_pct: float, years: float) -> float:
    """Calmar: retorno anualizado / max drawdown %."""
    if max_dd_pct == 0 or years <= 0:
        return 0.0
    cagr = (1 + net_profit / 100) ** (1 / years) - 1 if years > 0 else 0.0
    return float(cagr / max_dd_pct) if max_dd_pct else 0.0


def sterling_ratio(annual_return_pct: float, avg_max_dd_pct: float) -> float:
    """Sterling: retorno anual / (avg max DD - 10%). Variante do Calmar."""
    denom = abs(avg_max_dd_pct) + 10.0
    return float(annual_return_pct / denom) if denom else 0.0


# --------------------------------------------------------------------- SQN
def system_quality_number(returns: np.ndarray) -> float:
    """SQN de Van Tharp: (média/desvio) * sqrt(n), limitado a 100 trades.

    Escala de referência:
        < 1.6   : sistema fraco
        1.6-1.9 : médio
        2.0-2.4 : bom
        2.5-2.9 : excelente
        3.0-5.0 : superior
        > 7.0   : santo graal (ou overfit)
    """
    if returns.size < 2:
        return 0.0
    std = float(np.std(returns, ddof=1))
    if std == 0:
        return 0.0
    n = min(returns.size, 100)
    return float(np.mean(returns) / std * math.sqrt(n))


# --------------------------------------------------------- Qualidade da curva
def k_ratio(equity: np.ndarray) -> float:
    """K-Ratio: mede linearidade da log-equity. Maior = equity mais "suave".

    Calculado como slope/standard error da regressão linear de log(equity).
    """
    if equity.size < 3:
        return 0.0
    y = np.log(np.maximum(equity, 1e-9))
    x = np.arange(y.size, dtype=np.float64)
    n = y.size
    slope, intercept = np.polyfit(x, y, 1)
    y_hat = slope * x + intercept
    residuals = y - y_hat
    ss_res = float(np.sum(residuals ** 2))
    x_mean = float(np.mean(x))
    ss_x = float(np.sum((x - x_mean) ** 2))
    if ss_x == 0 or ss_res == 0:
        return 0.0
    se_slope = math.sqrt(ss_res / (n - 2) / ss_x)
    if se_slope == 0:
        return 0.0
    return float(slope / se_slope / math.sqrt(n))


# ----------------------------------------------------------- Métricas básicas
def basic_trade_stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {
            "total": 0, "wins": 0, "losses": 0, "break_even": 0,
            "win_rate": 0.0, "profit_factor": 0.0, "expectancy": 0.0,
            "payoff_ratio": 0.0,
            "gross_profit": 0.0, "gross_loss": 0.0, "net_profit": 0.0,
            "avg_win": 0.0, "avg_loss": 0.0,
            "largest_win": 0.0, "largest_loss": 0.0,
            "consec_wins_max": 0, "consec_losses_max": 0,
        }
    profits = np.array([float(t["profit"]) for t in trades], dtype=np.float64)
    wins = profits[profits > 0]
    losses = profits[profits < 0]
    total = int(profits.size)
    gross_profit = float(wins.sum())
    gross_loss = float(losses.sum())  # negativo
    net_profit = gross_profit + gross_loss

    # Sequências consecutivas
    consec_wins, consec_losses, cw, cl = 0, 0, 0, 0
    for p in profits:
        if p > 0:
            cw += 1; cl = 0
            consec_wins = max(consec_wins, cw)
        elif p < 0:
            cl += 1; cw = 0
            consec_losses = max(consec_losses, cl)
        else:
            cw = cl = 0

    win_rate = wins.size / total if total else 0.0
    avg_win = float(wins.mean()) if wins.size else 0.0
    avg_loss = float(losses.mean()) if losses.size else 0.0
    profit_factor = (gross_profit / abs(gross_loss)) if gross_loss != 0 else (
        float("inf") if gross_profit > 0 else 0.0
    )
    expectancy = float(profits.mean()) if total else 0.0
    payoff = abs(avg_win / avg_loss) if avg_loss else 0.0

    return {
        "total": total,
        "wins": int(wins.size),
        "losses": int(losses.size),
        "break_even": int((profits == 0).sum()),
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "payoff_ratio": payoff,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "net_profit": net_profit,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "largest_win": float(wins.max()) if wins.size else 0.0,
        "largest_loss": float(losses.min()) if losses.size else 0.0,
        "consec_wins_max": consec_wins,
        "consec_losses_max": consec_losses,
    }


# -------------------------------------------------------- Duração / tempo
def _parse_dt(s: Any) -> datetime | None:
    if not isinstance(s, str):
        return None
    for fmt in ("%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def time_stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Estatísticas temporais: período total, duração média, trades/dia, etc."""
    if not trades:
        return {}
    t_in = [_parse_dt(t.get("time_in")) for t in trades]
    t_out = [_parse_dt(t.get("time_out")) for t in trades]
    t_in = [t for t in t_in if t]
    t_out = [t for t in t_out if t]
    if not t_in or not t_out:
        return {}
    start = min(t_in)
    end = max(t_out)
    total_days = max((end - start).days, 1)
    durations = [t.get("duration_sec") for t in trades if t.get("duration_sec") is not None]
    return {
        "first_trade": start.isoformat(),
        "last_trade": end.isoformat(),
        "period_days": total_days,
        "period_years": total_days / 365.25,
        "trades_per_day": len(trades) / total_days,
        "avg_duration_sec": float(np.mean(durations)) if durations else 0.0,
        "median_duration_sec": float(np.median(durations)) if durations else 0.0,
    }


# ------------------------------------------------- Breakdown temporal
def time_breakdown(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """P/L agrupado por hora, dia da semana, mês e ano."""
    if not trades:
        return {"by_hour": [], "by_weekday": [], "by_month": [], "by_year": []}

    WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    hour_buckets: dict[int, list[float]] = {h: [] for h in range(24)}
    weekday_buckets: dict[int, list[float]] = {d: [] for d in range(7)}
    month_buckets: dict[int, list[float]] = {m: [] for m in range(1, 13)}
    year_trades: dict[int, list[dict]] = {}

    for t in trades:
        dt = _parse_dt(t.get("time_out"))
        if dt is None:
            continue
        p = float(t.get("profit", 0.0))
        hour_buckets[dt.hour].append(p)
        weekday_buckets[dt.weekday()].append(p)
        month_buckets[dt.month].append(p)
        year_trades.setdefault(dt.year, []).append(t)

    def _stats(profits: list[float]) -> dict[str, Any]:
        if not profits:
            return {"net_profit": 0.0, "trades": 0, "win_rate": 0.0}
        arr = np.array(profits, dtype=np.float64)
        wins = int((arr > 0).sum())
        return {"net_profit": float(arr.sum()), "trades": len(profits), "win_rate": wins / len(profits)}

    by_hour = [{"hour": h, **_stats(hour_buckets[h])} for h in range(24)]
    by_weekday = [
        {"weekday": WEEKDAY_NAMES[d], "weekday_num": d, **_stats(weekday_buckets[d])}
        for d in range(7)
    ]
    by_month = [
        {"month": MONTH_NAMES[m - 1], "month_num": m, **_stats(month_buckets[m])}
        for m in range(1, 13)
    ]

    by_year: list[dict[str, Any]] = []
    for y in sorted(year_trades):
        yt = year_trades[y]
        s = _stats([float(t.get("profit", 0.0)) for t in yt])
        eq_y = build_equity_curve(yt, 10_000.0)
        _, dd_pct_y, _, _ = max_drawdown(eq_y)
        n = len(yt)
        sr_annual = sharpe_ratio(eq_y.returns) * math.sqrt(max(n, 1))
        by_year.append({"year": y, **s, "max_dd_pct": dd_pct_y * 100, "sharpe_annual": sr_annual})

    return {"by_hour": by_hour, "by_weekday": by_weekday, "by_month": by_month, "by_year": by_year}


# ---------------------------------------------------- MAE / MFE proxy
def mae_mfe_data(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Scatter: profit vs duração, por lado. MAE/MFE estimados por proxy."""
    if not trades:
        return []
    losses = [float(t.get("profit", 0.0)) for t in trades if float(t.get("profit", 0.0)) < 0]
    avg_loss = abs(sum(losses) / len(losses)) if losses else 1.0

    result = []
    for i, t in enumerate(trades):
        profit = float(t.get("profit", 0.0))
        duration = float(t.get("duration_sec") or 0.0)
        raw_side = str(t.get("side", "buy")).lower()
        side = "sell" if raw_side in ("sell", "short") else "buy"
        result.append({
            "trade_num": i + 1,
            "profit": profit,
            "duration_sec": duration,
            "side": side,
            "is_win": profit > 0,
            "r_multiple": profit / avg_loss if avg_loss else 0.0,
        })
    return result


# ----------------------------------------------- Breakdown por direção
def direction_stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Métricas separadas long (buy) vs short (sell)."""
    long_trades = [t for t in trades if str(t.get("side", "")).lower() in ("buy", "long")]
    short_trades = [t for t in trades if str(t.get("side", "")).lower() in ("sell", "short")]

    def _dir(ts: list[dict]) -> dict[str, Any]:
        if not ts:
            return {"trades": 0, "net_profit": 0.0, "win_rate": 0.0,
                    "avg_win": 0.0, "avg_loss": 0.0, "profit_factor": 0.0}
        arr = np.array([float(t["profit"]) for t in ts], dtype=np.float64)
        wins = arr[arr > 0]
        losses = arr[arr < 0]
        gp = float(wins.sum()) if wins.size else 0.0
        gl = float(losses.sum()) if losses.size else 0.0
        pf = (gp / abs(gl)) if gl != 0 else (float("inf") if gp > 0 else 0.0)
        return {
            "trades": len(ts),
            "net_profit": float(arr.sum()),
            "win_rate": wins.size / len(ts),
            "avg_win": float(wins.mean()) if wins.size else 0.0,
            "avg_loss": float(losses.mean()) if losses.size else 0.0,
            "profit_factor": pf,
        }

    return {"long": _dir(long_trades), "short": _dir(short_trades)}


# ----------------------------------------------- Risk of Ruin
def risk_of_ruin_table(win_rate: float, payoff_ratio: float) -> list[dict[str, Any]]:
    """RoR clássico para diferentes % de risco por trade."""
    RISK_LEVELS = [0.005, 0.01, 0.02, 0.03, 0.05, 0.10]
    edge = win_rate * payoff_ratio - (1.0 - win_rate)
    out = []
    for r in RISK_LEVELS:
        if edge <= 0:
            ror = 1.0
        else:
            ratio = (1.0 - edge) / (1.0 + edge)
            if ratio <= 0:
                ror = 0.0
            elif ratio >= 1:
                ror = 1.0
            else:
                ror = float(ratio ** (1.0 / r))
        out.append({
            "risk_pct": r,
            "risk_pct_label": f"{r * 100:.1f}%",
            "ruin_probability": min(1.0, max(0.0, ror)),
        })
    return out


# ----------------------------------------------- Estagnação
def stagnation_stats(eq: EquityCurve, trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Períodos em que a equity fica abaixo do pico anterior."""
    if eq.values.size < 2:
        return {"max_stagnation_days": 0, "avg_stagnation_days": 0.0,
                "stagnation_pct_of_period": 0.0, "stagnation_periods": []}

    below = eq.values < eq.peaks
    trade_dates = [_parse_dt(t.get("time_out")) for t in trades]

    def _idx_date(eq_idx: int) -> datetime | None:
        ti = eq_idx - 1
        return trade_dates[ti] if 0 <= ti < len(trade_dates) else None

    periods: list[dict[str, Any]] = []
    in_stag = False
    start_idx = 0
    for i, bp in enumerate(below.tolist()):
        if bp and not in_stag:
            in_stag = True
            start_idx = i
        elif not bp and in_stag:
            in_stag = False
            d0, d1 = _idx_date(start_idx), _idx_date(i - 1)
            days = max(0, (d1 - d0).days) if d0 and d1 else 0
            periods.append({"start_idx": start_idx, "end_idx": i - 1, "days": days})
    if in_stag:
        n = len(below) - 1
        d0, d1 = _idx_date(start_idx), _idx_date(n)
        days = max(0, (d1 - d0).days) if d0 and d1 else 0
        periods.append({"start_idx": start_idx, "end_idx": n, "days": days})

    stag_count = int(below.sum())
    total = len(below)
    day_vals = [p["days"] for p in periods]
    return {
        "max_stagnation_days": max(day_vals) if day_vals else 0,
        "avg_stagnation_days": float(np.mean(day_vals)) if day_vals else 0.0,
        "stagnation_pct_of_period": stag_count / total if total else 0.0,
        "stagnation_periods": periods,
    }


# --------------------------------------------------- Agregador top-level
def full_analysis(trades: list[dict[str, Any]], initial_equity: float = 10_000.0) -> dict[str, Any]:
    """Aplica TODAS as métricas e retorna um dicionário plano pronto para o frontend."""
    if not trades:
        return {"trades": 0, "initial_equity": initial_equity}

    eq = build_equity_curve(trades, initial_equity)
    dd_abs, dd_pct, peak_idx, trough_idx = max_drawdown(eq)
    stats = basic_trade_stats(trades)
    time = time_stats(trades)
    years = time.get("period_years", 0.0) or 0.0
    annual_return_pct = (
        ((eq.values[-1] / initial_equity) ** (1 / years) - 1) * 100
        if years > 0 else 0.0
    )

    return {
        # Summary
        "initial_equity": initial_equity,
        "final_equity": float(eq.values[-1]),
        "net_profit": stats["net_profit"],
        "net_profit_pct": (eq.values[-1] - initial_equity) / initial_equity * 100,
        "annual_return_pct": annual_return_pct,
        # Trades
        **stats,
        # Tempo
        **time,
        # Risco
        "max_drawdown_abs": dd_abs,
        "max_drawdown_pct": dd_pct * 100,
        "max_dd_peak_trade": peak_idx,
        "max_dd_trough_trade": trough_idx,
        "ulcer_index": ulcer_index(eq),
        # Qualidade
        "sharpe_ratio": sharpe_ratio(eq.returns),
        "sortino_ratio": sortino_ratio(eq.returns),
        "calmar_ratio": calmar_ratio(
            (eq.values[-1] - initial_equity) / initial_equity * 100, dd_pct * 100, years
        ),
        "sterling_ratio": sterling_ratio(annual_return_pct, dd_pct * 100),
        "sqn": system_quality_number(eq.returns),
        "k_ratio": k_ratio(eq.values),
        "recovery_factor": (stats["net_profit"] / dd_abs) if dd_abs else 0.0,
        # Curva (para frontend plotar)
        "equity_curve": eq.values.tolist(),
        "drawdown_curve": (eq.drawdown_pct * 100).tolist(),
        # Breakdown temporal (Fase 1)
        "time_breakdown": time_breakdown(trades),
        # MAE/MFE proxy scatter (Fase 2)
        "mae_mfe": mae_mfe_data(trades),
        # Long vs Short (Fase 3)
        "direction": direction_stats(trades),
        # Risk of Ruin (Fase 4)
        "risk_of_ruin": risk_of_ruin_table(stats["win_rate"], stats["payoff_ratio"]),
        # Estagnação (Fase 8)
        "stagnation": stagnation_stats(eq, trades),
    }
