"""Portfólio: combina trades de N runs e aplica análise + robustez no agregado.

Útil pra avaliar uma cesta de estratégias. Calcula também correlação entre
as equity curves individuais (diversificação real).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services import analytics, robustness, storage


router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class PortfolioRequest(BaseModel):
    run_ids: list[str] = Field(min_length=1)
    initial_equity: float = 10_000.0
    runs: int = 2000
    n_trials: int = 1
    var_sr_trials: float = 0.0


class WeightOptRequest(BaseModel):
    run_ids: list[str] = Field(min_length=1)
    initial_equity: float = 10_000.0
    max_dd_pct: float = 20.0  # teto de DD do portfólio (%)
    n_samples: int = 4000  # amostras Dirichlet
    seed: int = 42


def _parse_time(t: Any) -> datetime | None:
    if isinstance(t, datetime):
        return t
    if isinstance(t, str):
        try:
            return datetime.fromisoformat(t)
        except ValueError:
            return None
    return None


def _equity_curve_by_trade(trades: list[dict], initial: float) -> list[tuple[datetime, float]]:
    out = []
    eq = initial
    for t in sorted(trades, key=lambda x: _parse_time(x.get("time_out")) or datetime.min):
        tm = _parse_time(t.get("time_out"))
        if tm is None:
            continue
        eq += float(t["profit"])
        out.append((tm, eq))
    return out


def _resample_daily(curve: list[tuple[datetime, float]]) -> dict[str, float]:
    """Último equity por dia."""
    out: dict[str, float] = {}
    for tm, eq in curve:
        out[tm.strftime("%Y-%m-%d")] = eq
    return out


def _correlation_matrix(curves: dict[str, dict[str, float]]) -> dict[str, Any]:
    """Correlação entre retornos diários das curvas."""
    ids = list(curves.keys())
    all_dates = sorted({d for c in curves.values() for d in c})
    if len(all_dates) < 2:
        return {"run_ids": ids, "matrix": [[1.0] * len(ids)] * len(ids)}

    # Forward-fill por curva e calcula retornos diários
    series: dict[str, np.ndarray] = {}
    for rid, c in curves.items():
        vals = []
        last = None
        for d in all_dates:
            if d in c:
                last = c[d]
            vals.append(last if last is not None else 0.0)
        arr = np.array(vals, dtype=float)
        rets = np.diff(arr) / np.where(arr[:-1] != 0, arr[:-1], 1.0)
        series[rid] = rets

    mat = []
    for a in ids:
        row = []
        for b in ids:
            if a == b:
                row.append(1.0)
            else:
                sa, sb = series[a], series[b]
                if sa.std() == 0 or sb.std() == 0:
                    row.append(0.0)
                else:
                    row.append(float(np.corrcoef(sa, sb)[0, 1]))
        mat.append(row)
    return {"run_ids": ids, "matrix": mat}


@router.post("/aggregate")
def aggregate_portfolio(req: PortfolioRequest) -> dict[str, Any]:
    storage.init_db()
    all_trades: list[dict[str, Any]] = []
    per_run_curves: dict[str, dict[str, float]] = {}
    per_run_info: list[dict[str, Any]] = []

    for rid in req.run_ids:
        trades = storage.load_trades(rid)
        if not trades:
            raise HTTPException(404, f"Run sem trades: {rid}")
        all_trades.extend(trades)
        curve = _equity_curve_by_trade(trades, req.initial_equity)
        per_run_curves[rid] = _resample_daily(curve)
        run = storage.get_run(rid)
        per_run_info.append({
            "run_id": rid,
            "symbol": run.get("symbol") if run else None,
            "trades": len(trades),
            "net_profit": sum(float(t["profit"]) for t in trades),
        })

    # Ordena trades agregados por timestamp
    all_trades.sort(key=lambda t: _parse_time(t.get("time_out")) or datetime.min)

    analysis = analytics.full_analysis(all_trades, initial_equity=req.initial_equity)
    suite = robustness.run_suite(
        all_trades, initial=req.initial_equity,
        runs=req.runs, n_trials=req.n_trials, var_sr_trials=req.var_sr_trials,
    )
    corr = _correlation_matrix(per_run_curves)

    return {
        "run_count": len(req.run_ids),
        "total_trades": len(all_trades),
        "per_run": per_run_info,
        "analysis": analysis,
        "suite": suite,
        "correlation": corr,
    }


def _metrics_for_weighted(
    trades_by_run: dict[str, list[dict]],
    weights: dict[str, float],
    initial: float,
) -> dict[str, float]:
    """Aplica pesos aos profits (scale por trade) e devolve net_profit + max_dd_pct."""
    combined: list[tuple[datetime, float]] = []
    for rid, trades in trades_by_run.items():
        w = weights.get(rid, 0.0)
        if w <= 0:
            continue
        for t in trades:
            tm = _parse_time(t.get("time_out"))
            if tm is None:
                continue
            combined.append((tm, float(t["profit"]) * w))
    if not combined:
        return {"net_profit": 0.0, "max_dd_pct": 100.0}
    combined.sort(key=lambda x: x[0])
    eq = initial
    peak = initial
    max_dd_pct = 0.0
    for _, pnl in combined:
        eq += pnl
        if eq > peak:
            peak = eq
        if peak > 0:
            dd = (peak - eq) / peak * 100.0
            if dd > max_dd_pct:
                max_dd_pct = dd
    return {"net_profit": eq - initial, "max_dd_pct": max_dd_pct}


@router.post("/optimize-weights")
def optimize_weights(req: WeightOptRequest) -> dict[str, Any]:
    """Busca pesos (somam 1) que maximizam net_profit sujeito a max_dd_pct <= alvo.

    Estratégia: amostragem Dirichlet uniforme + avaliação direta. Simples,
    estável e paralelizável mentalmente. Retorna best, baseline (equal weights)
    e top candidatos para inspeção.
    """
    storage.init_db()
    trades_by_run: dict[str, list[dict]] = {}
    for rid in req.run_ids:
        trades = storage.load_trades(rid)
        if not trades:
            raise HTTPException(404, f"Run sem trades: {rid}")
        trades_by_run[rid] = trades

    n = len(req.run_ids)
    rng = np.random.default_rng(req.seed)

    # Baseline equal-weight
    equal_w = {rid: 1.0 / n for rid in req.run_ids}
    equal_m = _metrics_for_weighted(trades_by_run, equal_w, req.initial_equity)

    # Amostragem Dirichlet (alpha=1 -> uniforme no simplex)
    samples = rng.dirichlet(np.ones(n), size=req.n_samples)

    evaluated = []
    for w in samples:
        wd = {rid: float(w[i]) for i, rid in enumerate(req.run_ids)}
        m = _metrics_for_weighted(trades_by_run, wd, req.initial_equity)
        evaluated.append({**m, "weights": wd})

    feasible = [e for e in evaluated if e["max_dd_pct"] <= req.max_dd_pct]
    if feasible:
        best = max(feasible, key=lambda e: e["net_profit"])
        best["feasible"] = True
    else:
        # Sem ninguém dentro do teto — devolve o de menor DD
        best = min(evaluated, key=lambda e: e["max_dd_pct"])
        best["feasible"] = False

    top = sorted(feasible or evaluated,
                 key=lambda e: e["net_profit"], reverse=True)[:10]

    return {
        "run_ids": req.run_ids,
        "max_dd_target_pct": req.max_dd_pct,
        "n_samples": req.n_samples,
        "baseline_equal": {**equal_m, "weights": equal_w},
        "best": best,
        "top": top,
    }
