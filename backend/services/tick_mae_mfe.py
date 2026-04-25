"""Calcula MAE/MFE reais usando dados de tick (Parquet gerado pelo tick_converter).

MAE = Maximum Adverse Excursion  — quanto o preço foi contra o trade antes de fechar.
MFE = Maximum Favorable Excursion — quanto o preço foi a favor antes de fechar.

Usa Polars lazy: filtra apenas o intervalo de datas dos trades, não carrega o
arquivo inteiro na RAM — funciona para datasets de múltiplos GB.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl


def _parse_dt(s: Any) -> datetime | None:
    if not isinstance(s, str):
        return None
    for fmt in ("%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _price_col(columns: list[str]) -> str:
    """Detecta a melhor coluna de preço disponível."""
    for candidate in ("mid_price", "last", "bid", "ask"):
        if candidate in columns:
            return candidate
    raise ValueError(f"Nenhuma coluna de preço encontrada. Colunas: {columns}")


def _ts_col(columns: list[str]) -> str:
    """Detecta a coluna de timestamp."""
    for candidate in ("timestamp", "ts", "datetime", "time"):
        if candidate in columns:
            return candidate
    raise ValueError(f"Nenhuma coluna de timestamp. Colunas: {columns}")


def compute_mae_mfe(
    trades: list[dict[str, Any]],
    parquet_path: str,
    buffer_seconds: int = 60,
) -> list[dict[str, Any]]:
    """Para cada trade, filtra ticks em [time_in, time_out] e calcula MAE/MFE.

    Retorna a mesma lista de trades enriquecida com:
      mae_price      — excursão adversa em pontos de preço
      mfe_price      — excursão favorável em pontos de preço
      mae_dollars    — MAE convertido para moeda da conta
      mfe_dollars    — MFE convertido
      efficiency     — profit / mfe_dollars  (0-1, quanto do MFE foi capturado)
      entry_eff      — 1 - mae_dollars / mfe_dollars  (qualidade da entrada)
      r_multiple_real — profit / mae_dollars
      tick_count     — número de ticks no intervalo do trade
    """
    if not trades:
        return []

    parquet_path = Path(parquet_path)
    if not parquet_path.exists():
        raise FileNotFoundError(f"Parquet não encontrado: {parquet_path}")

    # Se for diretório (partitioned), usa glob
    scan_target = str(parquet_path / "**" / "*.parquet") if parquet_path.is_dir() else str(parquet_path)

    # Parse de datas de todos os trades
    parsed_times: list[tuple[datetime, datetime] | None] = []
    for t in trades:
        dt_in = _parse_dt(t.get("time_in"))
        dt_out = _parse_dt(t.get("time_out"))
        parsed_times.append((dt_in, dt_out) if dt_in and dt_out else None)

    valid = [(i, p) for i, p in enumerate(parsed_times) if p is not None]
    if not valid:
        return [_enrich_empty(t) for t in trades]

    # Range total (+ buffer)
    buf = timedelta(seconds=buffer_seconds)
    range_start = min(p[0] for _, p in valid) - buf
    range_end = max(p[1] for _, p in valid) + buf

    # Carrega somente o intervalo relevante (Polars lazy + predicate pushdown)
    lf = pl.scan_parquet(scan_target)
    schema_cols = list(lf.schema.keys())
    ts_col = _ts_col(schema_cols)

    # Adiciona coluna mid_price se bid+ask disponíveis
    exprs: list[pl.Expr] = []
    if "bid" in schema_cols and "ask" in schema_cols:
        exprs.append(((pl.col("bid") + pl.col("ask")) / 2).alias("mid_price"))

    filtered = (
        lf
        .filter((pl.col(ts_col) >= range_start) & (pl.col(ts_col) <= range_end))
        .with_columns(exprs)
        .collect()
    )

    if filtered.is_empty():
        return [_enrich_empty(t) for t in trades]

    price_col = _price_col(filtered.columns)
    ts_series = filtered[ts_col].cast(pl.Datetime("us")).to_numpy().astype("datetime64[us]")
    price_series = filtered[price_col].cast(pl.Float64).to_numpy()

    results: list[dict[str, Any]] = []
    for i, t in enumerate(trades):
        dt = parsed_times[i]
        if dt is None:
            results.append(_enrich_empty(t))
            continue

        dt_in, dt_out = dt
        entry_price = float(t.get("entry_price") or 0.0)
        exit_price = float(t.get("exit_price") or 0.0)
        profit = float(t.get("profit") or 0.0)
        side = str(t.get("side", "buy")).lower()
        is_long = side in ("buy", "long")

        if entry_price == 0.0:
            results.append(_enrich_empty(t))
            continue

        # Máscara de ticks do trade
        t_in_np = np.datetime64(dt_in.replace(tzinfo=None), "us")
        t_out_np = np.datetime64(dt_out.replace(tzinfo=None), "us")
        mask = (ts_series >= t_in_np) & (ts_series <= t_out_np)
        tick_count = int(mask.sum())

        if tick_count == 0:
            results.append(_enrich_empty(t))
            continue

        prices = price_series[mask]
        min_p = float(np.min(prices))
        max_p = float(np.max(prices))

        if is_long:
            mae_price = max(0.0, entry_price - min_p)
            mfe_price = max(0.0, max_p - entry_price)
            delta_price = exit_price - entry_price
        else:
            mae_price = max(0.0, max_p - entry_price)
            mfe_price = max(0.0, entry_price - min_p)
            delta_price = entry_price - exit_price

        # Multiplier: converte pontos → moeda da conta
        # profit = delta_price * multiplier  (válido para qualquer instrumento)
        if abs(delta_price) > 1e-10:
            multiplier = profit / delta_price
        elif abs(mfe_price) > 1e-10:
            multiplier = abs(profit) / mfe_price
        else:
            multiplier = 0.0

        abs_mult = abs(multiplier)
        mae_dollars = mae_price * abs_mult
        mfe_dollars = mfe_price * abs_mult

        efficiency = profit / mfe_dollars if mfe_dollars > 1e-10 else None
        entry_eff = 1.0 - mae_dollars / mfe_dollars if mfe_dollars > 1e-10 else None
        r_real = profit / mae_dollars if mae_dollars > 1e-10 else None

        results.append({
            **t,
            "mae_price": mae_price,
            "mfe_price": mfe_price,
            "mae_dollars": mae_dollars,
            "mfe_dollars": mfe_dollars,
            "efficiency": float(efficiency) if efficiency is not None else None,
            "entry_efficiency": float(entry_eff) if entry_eff is not None else None,
            "r_multiple_real": float(r_real) if r_real is not None else None,
            "tick_count": tick_count,
            "has_real_mae_mfe": True,
        })

    return results


def _enrich_empty(t: dict[str, Any]) -> dict[str, Any]:
    return {**t, "mae_price": None, "mfe_price": None, "mae_dollars": None,
            "mfe_dollars": None, "efficiency": None, "entry_efficiency": None,
            "r_multiple_real": None, "tick_count": 0, "has_real_mae_mfe": False}


def aggregate_mae_mfe_stats(enriched: list[dict[str, Any]]) -> dict[str, Any]:
    """Estatísticas agregadas dos MAE/MFE calculados."""
    valid = [t for t in enriched if t.get("has_real_mae_mfe")]
    if not valid:
        return {}

    maes = np.array([t["mae_dollars"] for t in valid], dtype=np.float64)
    mfes = np.array([t["mfe_dollars"] for t in valid], dtype=np.float64)
    effs = np.array([t["efficiency"] for t in valid if t["efficiency"] is not None], dtype=np.float64)
    entry_effs = np.array([t["entry_efficiency"] for t in valid if t["entry_efficiency"] is not None], dtype=np.float64)

    avg_mfe = float(mfes.mean()) if mfes.size else 0.0
    avg_mae = float(maes.mean()) if maes.size else 0.0
    edge_ratio = avg_mfe / avg_mae if avg_mae > 1e-10 else 0.0

    return {
        "n_trades_with_ticks": len(valid),
        "avg_mae_dollars": avg_mae,
        "avg_mfe_dollars": avg_mfe,
        "edge_ratio": edge_ratio,            # > 1.0 = MFE > MAE = bom
        "avg_efficiency": float(effs.mean()) if effs.size else None,
        "avg_entry_efficiency": float(entry_effs.mean()) if entry_effs.size else None,
        "pct_mfe_captured": float(effs.mean()) if effs.size else None,
        "optimal_tp_estimate": float(np.percentile(mfes, 75)) if mfes.size else None,
        "optimal_sl_estimate": float(np.percentile(maes, 75)) if maes.size else None,
    }
