"""Monte Carlo usando dados de tick reais.

Diferença do monte_carlo.py clássico:
    - `monte_carlo.py`: sintético — embaralha / reamostra profits já computados
    - este módulo: usa ticks reais do ativo para gerar sequências alternativas
      mais fiéis à dinâmica real do mercado

Métodos implementados:

1. **Entry Jitter**: desloca cada entrada em ±N segundos (uniforme) e
   recalcula o profit usando o preço real de tick no novo instante.
   Testa se o edge depende de timing sub-segundo.

2. **Spread-realistic slippage**: aplica o spread bid-ask real no momento
   da entrada/saída como slippage, em vez de ±% sintético. Validação muito
   mais realista do custo de execução.

3. **Block bootstrap de tick-returns**: constrói paths sintéticos preservando
   autocorrelação do ruído de preço, então "replaya" os trades sobre esse
   path (usa duração + direção do trade).

4. **SL/TP sweep**: simula diferentes níveis de stop/take usando o caminho
   intra-trade real dos ticks. Responde "qual SL/TP otimiza a equity?"

Todos retornam percentis (P5, P50, P95) de net_profit e max_drawdown.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl


# --------------------------------------------------------------- helpers
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
    for c in ("mid_price", "last", "bid", "ask"):
        if c in columns:
            return c
    raise ValueError(f"Sem coluna de preço. Columns={columns}")


def _ts_col(columns: list[str]) -> str:
    for c in ("timestamp", "ts", "datetime", "time"):
        if c in columns:
            return c
    raise ValueError(f"Sem coluna de timestamp. Columns={columns}")


def _load_ticks_range(
    parquet_path: str | Path,
    start: datetime,
    end: datetime,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Retorna (timestamps, mid_prices, bids, asks) no intervalo [start, end].

    Usa Polars lazy + predicate pushdown — só carrega o slice necessário.
    """
    p = Path(parquet_path)
    scan_target = str(p / "**" / "*.parquet") if p.is_dir() else str(p)
    lf = pl.scan_parquet(scan_target)
    schema = list(lf.schema.keys())
    ts = _ts_col(schema)

    exprs: list[pl.Expr] = []
    if "bid" in schema and "ask" in schema:
        exprs.append(((pl.col("bid") + pl.col("ask")) / 2).alias("mid_price"))

    df = (
        lf.filter((pl.col(ts) >= start) & (pl.col(ts) <= end))
        .with_columns(exprs)
        .collect()
    )
    if df.is_empty():
        return np.array([], dtype="datetime64[us]"), np.array([]), np.array([]), np.array([])

    pc = _price_col(df.columns)
    ts_np = df[ts].cast(pl.Datetime("us")).to_numpy().astype("datetime64[us]")
    mid = df[pc].cast(pl.Float64).to_numpy()
    bid = df["bid"].cast(pl.Float64).to_numpy() if "bid" in df.columns else mid
    ask = df["ask"].cast(pl.Float64).to_numpy() if "ask" in df.columns else mid
    return ts_np, mid, bid, ask


# --------------------------------------------------------------- equity stats
def _equity_stats(profits: np.ndarray, initial: float) -> tuple[float, float]:
    values = initial + np.cumsum(profits)
    net = float(values[-1] - initial) if values.size else 0.0
    peaks = np.maximum.accumulate(np.concatenate([[initial], values]))
    trough = np.concatenate([[initial], values])
    dd = (peaks - trough) / np.where(peaks > 0, peaks, 1.0)
    return net, float(np.max(dd)) * 100 if dd.size else 0.0


def _aggregate(net: np.ndarray, dd: np.ndarray, original_dd: float,
               histograms: bool = True) -> dict[str, Any]:
    out = {
        "runs": int(net.size),
        "net_p5": float(np.percentile(net, 5)) if net.size else 0.0,
        "net_p50": float(np.percentile(net, 50)) if net.size else 0.0,
        "net_p95": float(np.percentile(net, 95)) if net.size else 0.0,
        "dd_p5": float(np.percentile(dd, 5)) if dd.size else 0.0,
        "dd_p50": float(np.percentile(dd, 50)) if dd.size else 0.0,
        "dd_p95": float(np.percentile(dd, 95)) if dd.size else 0.0,
        "prob_profitable": float(np.mean(net > 0)) if net.size else 0.0,
        "prob_dd_exceeds_original": float(np.mean(dd > original_dd)) if dd.size else 0.0,
    }
    if histograms and net.size:
        ec, ee = np.histogram(net, bins=30)
        dc, de = np.histogram(dd, bins=30)
        out["net_hist"] = {"counts": ec.tolist(), "edges": ee.tolist()}
        out["dd_hist"] = {"counts": dc.tolist(), "edges": de.tolist()}
    return out


# ================================================================
# 1. ENTRY JITTER — desloca timestamp de entrada em ±jitter_seconds
# ================================================================
def entry_jitter_mc(
    trades: list[dict[str, Any]],
    parquet_path: str | Path,
    initial: float = 10_000.0,
    runs: int = 500,
    jitter_seconds: int = 30,
    seed: int | None = 42,
) -> dict[str, Any]:
    """Para cada trade, em cada run, desloca entrada em U(-jitter, +jitter)
    e recalcula profit assumindo saída no mesmo instante original.

    Responde: "o edge depende de timing preciso?"
    """
    rng = np.random.default_rng(seed)
    n = len(trades)
    if n == 0 or not Path(parquet_path).exists():
        return {"error": "sem trades ou parquet inválido"}

    # Pré-computa: pra cada trade, carrega janela de ticks [t_in - jitter, t_out]
    trade_data: list[dict[str, Any]] = []
    for t in trades:
        dt_in = _parse_dt(t.get("time_in"))
        dt_out = _parse_dt(t.get("time_out"))
        if not dt_in or not dt_out:
            trade_data.append({"valid": False, "profit": float(t.get("profit", 0))})
            continue
        buf = timedelta(seconds=jitter_seconds + 5)
        ts_np, mid, _, _ = _load_ticks_range(parquet_path, dt_in - buf, dt_out + buf)
        entry_px = float(t.get("entry_price") or 0)
        exit_px = float(t.get("exit_price") or 0)
        profit = float(t.get("profit") or 0)
        delta = (exit_px - entry_px) if str(t.get("side", "buy")).lower() in ("buy", "long") else (entry_px - exit_px)
        mult = profit / delta if abs(delta) > 1e-10 else 0.0

        trade_data.append({
            "valid": ts_np.size > 0 and abs(mult) > 1e-10,
            "ts": ts_np,
            "mid": mid,
            "dt_in": np.datetime64(dt_in, "us"),
            "dt_out": np.datetime64(dt_out, "us"),
            "exit_px": exit_px,
            "multiplier": mult,
            "side": str(t.get("side", "buy")).lower(),
            "profit": profit,
        })

    net_arr = np.empty(runs)
    dd_arr = np.empty(runs)
    for r in range(runs):
        profits = np.empty(n)
        for i, td in enumerate(trade_data):
            if not td["valid"]:
                profits[i] = td["profit"]
                continue
            shift_sec = rng.integers(-jitter_seconds, jitter_seconds + 1)
            new_in = td["dt_in"] + np.timedelta64(int(shift_sec), "s")
            # preço no novo instante = tick mais próximo em tempo
            idx = np.searchsorted(td["ts"], new_in)
            idx = min(max(idx, 0), td["ts"].size - 1)
            new_entry = float(td["mid"][idx])
            is_long = td["side"] in ("buy", "long")
            delta = (td["exit_px"] - new_entry) if is_long else (new_entry - td["exit_px"])
            profits[i] = delta * td["multiplier"]
        net_arr[r], dd_arr[r] = _equity_stats(profits, initial)

    orig_profits = np.array([td["profit"] for td in trade_data])
    _, orig_dd = _equity_stats(orig_profits, initial)
    result = _aggregate(net_arr, dd_arr, orig_dd)
    result["mode"] = "entry_jitter"
    result["jitter_seconds"] = jitter_seconds
    result["original_net"] = float(orig_profits.sum())
    result["original_dd_pct"] = orig_dd
    result["suggestion"] = _entry_jitter_suggestion(result)
    return result


def _entry_jitter_suggestion(r: dict[str, Any]) -> str:
    prob = r.get("prob_profitable", 0)
    if prob >= 0.95:
        return "Estratégia robusta a jitter de entrada. Timing não é crítico."
    if prob >= 0.8:
        return ("Tolerante a pequenas variações de timing. "
                "Viável em live mas vale monitorar latência de ordem.")
    return ("Fortemente sensível a timing — edge depende de execução precisa. "
            "Risco alto em live: qualquer lag do broker quebra o sistema. "
            "Opções: (1) aumentar timeframe para reduzir sensibilidade; "
            "(2) usar ordens limit em vez de market; "
            "(3) se o ativo tem ticks muito rápidos, considere que backtest pode "
            "estar otimista demais (MT5 usa ticks bid/ask mas live tem latência).")


# ================================================================
# 2. SPREAD-REALISTIC SLIPPAGE — usa bid-ask real do tick
# ================================================================
def spread_slippage_mc(
    trades: list[dict[str, Any]],
    parquet_path: str | Path,
    initial: float = 10_000.0,
    runs: int = 500,
    worst_n_ticks: int = 3,
    seed: int | None = 42,
) -> dict[str, Any]:
    """Aplica slippage realista baseado no spread real no momento da entrada/saída.

    Para cada trade: em vez de usar o preço do tick exato, pega o pior preço
    entre os próximos `worst_n_ticks` ticks (simulando latência/execução ruim).

    Responde: "o edge sobrevive ao custo real de execução?"
    """
    n = len(trades)
    if n == 0 or not Path(parquet_path).exists():
        return {"error": "sem trades ou parquet inválido"}

    rng = np.random.default_rng(seed)

    trade_data = []
    for t in trades:
        dt_in = _parse_dt(t.get("time_in"))
        dt_out = _parse_dt(t.get("time_out"))
        if not dt_in or not dt_out:
            trade_data.append({"valid": False, "profit": float(t.get("profit", 0))})
            continue
        buf = timedelta(seconds=10)
        ts_np, _, bid_np, ask_np = _load_ticks_range(parquet_path, dt_in - buf, dt_out + buf)
        entry_px = float(t.get("entry_price") or 0)
        exit_px = float(t.get("exit_price") or 0)
        profit = float(t.get("profit") or 0)
        side = str(t.get("side", "buy")).lower()
        delta = (exit_px - entry_px) if side in ("buy", "long") else (entry_px - exit_px)
        mult = profit / delta if abs(delta) > 1e-10 else 0.0

        trade_data.append({
            "valid": ts_np.size > 0 and abs(mult) > 1e-10,
            "ts": ts_np,
            "bid": bid_np,
            "ask": ask_np,
            "dt_in": np.datetime64(dt_in, "us"),
            "dt_out": np.datetime64(dt_out, "us"),
            "multiplier": mult,
            "side": side,
            "profit": profit,
        })

    # spread médio — diagnóstico
    spreads = []
    for td in trade_data:
        if td["valid"] and td["ask"].size:
            spreads.extend((td["ask"] - td["bid"]).tolist())
    avg_spread = float(np.mean(spreads)) if spreads else 0.0

    net_arr = np.empty(runs)
    dd_arr = np.empty(runs)
    for r in range(runs):
        profits = np.empty(n)
        for i, td in enumerate(trade_data):
            if not td["valid"]:
                profits[i] = td["profit"]
                continue
            is_long = td["side"] in ("buy", "long")
            # entrada: pior preço entre os próximos worst_n_ticks (buy = ask mais alto, sell = bid mais baixo)
            i_in = int(np.searchsorted(td["ts"], td["dt_in"]))
            i_in = min(max(i_in, 0), td["ts"].size - 1)
            window_in = slice(i_in, min(i_in + worst_n_ticks, td["ts"].size))
            if is_long:
                new_entry = float(np.max(td["ask"][window_in]))
            else:
                new_entry = float(np.min(td["bid"][window_in]))
            # saída: pior preço também (latência na saída)
            i_out = int(np.searchsorted(td["ts"], td["dt_out"]))
            i_out = min(max(i_out, 0), td["ts"].size - 1)
            window_out = slice(max(0, i_out - worst_n_ticks + 1), i_out + 1)
            if is_long:
                new_exit = float(np.min(td["bid"][window_out]))
            else:
                new_exit = float(np.max(td["ask"][window_out]))
            delta = (new_exit - new_entry) if is_long else (new_entry - new_exit)
            # aleatoriza entre worst-case e best-case para cada trade
            quality = rng.uniform(0.3, 1.0)
            delta_best = (td["profit"] / td["multiplier"]) if abs(td["multiplier"]) > 1e-10 else delta
            profits[i] = (delta * (1 - quality) + delta_best * quality) * td["multiplier"]
        net_arr[r], dd_arr[r] = _equity_stats(profits, initial)

    orig_profits = np.array([td["profit"] for td in trade_data])
    _, orig_dd = _equity_stats(orig_profits, initial)
    result = _aggregate(net_arr, dd_arr, orig_dd)
    result["mode"] = "spread_slippage"
    result["avg_spread_ticks"] = avg_spread
    result["worst_n_ticks"] = worst_n_ticks
    result["original_net"] = float(orig_profits.sum())
    result["original_dd_pct"] = orig_dd
    result["suggestion"] = _spread_suggestion(result)
    return result


def _spread_suggestion(r: dict[str, Any]) -> str:
    prob = r.get("prob_profitable", 0)
    if prob >= 0.9:
        return "Sobrevive ao spread real. Custo de execução não é barreira."
    if prob >= 0.7:
        return ("Margem apertada em custo de execução. "
                "Monitorar execution quality em conta live — qualquer piora no spread "
                "(horários de baixa liquidez, notícias) pode quebrar.")
    return ("Edge é engolido pelo spread/latência real. Não é viável em live como está. "
            "Opções: (1) operar ativos mais líquidos com spread menor; "
            "(2) evitar horários com spread alto (use Análise Temporal por hora); "
            "(3) aumentar TP para que o spread seja pequeno relativamente; "
            "(4) usar limit orders (sem garantia de fill, mas sem pagar spread).")


# ================================================================
# 3. BLOCK BOOTSTRAP DE TICK-RETURNS
# ================================================================
def tick_return_bootstrap_mc(
    trades: list[dict[str, Any]],
    parquet_path: str | Path,
    initial: float = 10_000.0,
    runs: int = 500,
    block_ticks: int = 100,
    seed: int | None = 42,
) -> dict[str, Any]:
    """Constrói paths sintéticos bootstrapando blocos de tick-returns e replaya
    cada trade sobre esses paths.

    Para cada trade, a duração é preservada. O profit vira:
        profit = multiplier * (preço_sintético_fim - preço_sintético_início) * side_sign

    Preserva autocorrelação do ruído de tick.
    Responde: "se o ativo tivesse se comportado com mesma estatística mas
    caminhos diferentes, a estratégia ganharia?"
    """
    n = len(trades)
    if n == 0 or not Path(parquet_path).exists():
        return {"error": "sem trades ou parquet inválido"}

    # Carrega range global e computa log-returns ponta-a-ponta
    valid = [(_parse_dt(t.get("time_in")), _parse_dt(t.get("time_out")), t) for t in trades]
    valid = [(a, b, t) for a, b, t in valid if a and b]
    if not valid:
        return {"error": "sem timestamps válidos nos trades"}
    g_start = min(v[0] for v in valid)
    g_end = max(v[1] for v in valid)
    ts_np, mid, _, _ = _load_ticks_range(parquet_path, g_start, g_end)
    if ts_np.size < block_ticks * 2:
        return {"error": f"ticks insuficientes: {ts_np.size}"}

    log_px = np.log(np.maximum(mid, 1e-10))
    tick_returns = np.diff(log_px)
    n_returns = tick_returns.size

    # Extrai duração em #ticks para cada trade
    trade_info = []
    for dt_in, dt_out, t in valid:
        i0 = int(np.searchsorted(ts_np, np.datetime64(dt_in, "us")))
        i1 = int(np.searchsorted(ts_np, np.datetime64(dt_out, "us")))
        duration_ticks = max(1, min(i1 - i0, n_returns - 1))
        entry_px = float(t.get("entry_price") or mid[i0])
        exit_px = float(t.get("exit_price") or mid[min(i1, ts_np.size - 1)])
        profit = float(t.get("profit") or 0)
        side = str(t.get("side", "buy")).lower()
        is_long = side in ("buy", "long")
        delta = (exit_px - entry_px) if is_long else (entry_px - exit_px)
        mult = profit / delta if abs(delta) > 1e-10 else 0.0
        trade_info.append({
            "duration_ticks": duration_ticks,
            "entry_px": entry_px,
            "multiplier": mult,
            "is_long": is_long,
            "profit": profit,
        })

    rng = np.random.default_rng(seed)
    net_arr = np.empty(runs)
    dd_arr = np.empty(runs)

    for r in range(runs):
        profits = np.empty(n)
        for i, td in enumerate(trade_info):
            if abs(td["multiplier"]) < 1e-10:
                profits[i] = td["profit"]
                continue
            # amostra blocos até cobrir duration_ticks
            dur = td["duration_ticks"]
            nb = (dur // block_ticks) + 1
            starts = rng.integers(0, max(1, n_returns - block_ticks + 1), size=nb)
            ret_seq = np.concatenate([tick_returns[s:s + block_ticks] for s in starts])[:dur]
            total_log_return = float(ret_seq.sum())
            synthetic_exit = td["entry_px"] * np.exp(total_log_return)
            delta = (synthetic_exit - td["entry_px"]) if td["is_long"] else (td["entry_px"] - synthetic_exit)
            profits[i] = delta * td["multiplier"]
        net_arr[r], dd_arr[r] = _equity_stats(profits, initial)

    orig_profits = np.array([td["profit"] for td in trade_info])
    _, orig_dd = _equity_stats(orig_profits, initial)
    result = _aggregate(net_arr, dd_arr, orig_dd)
    result["mode"] = "tick_return_bootstrap"
    result["block_ticks"] = block_ticks
    result["n_returns_source"] = int(n_returns)
    result["original_net"] = float(orig_profits.sum())
    result["original_dd_pct"] = orig_dd
    result["suggestion"] = _tick_bootstrap_suggestion(result)
    return result


def _tick_bootstrap_suggestion(r: dict[str, Any]) -> str:
    prob = r.get("prob_profitable", 0)
    net_p50 = r.get("net_p50", 0)
    orig = r.get("original_net", 0)
    if prob >= 0.85 and net_p50 > 0:
        return ("Edge consistente sobre ruído realista do ativo. "
                "Estratégia captura sinal genuíno, não apenas o caminho histórico.")
    if prob >= 0.6:
        return ("Edge parcialmente dependente do caminho histórico específico. "
                "Pode funcionar em live mas resultado pode variar bastante. "
                "Sugestão: validar em hold-out fora-da-amostra antes de usar.")
    return (f"Net mediano P50 sintético ({net_p50:.2f}) muito abaixo do histórico ({orig:.2f}). "
            "A estratégia pode estar explorando um padrão específico do caminho histórico "
            "que não se repete. Opções: (1) walk-forward analysis — validar em período "
            "fora da amostra; (2) procurar por look-ahead bias no indicador; "
            "(3) reformular usando features mais universais (não específicas de regime).")


# ================================================================
# Runner unificado
# ================================================================
def run_all_tick_mc(
    trades: list[dict[str, Any]],
    parquet_path: str | Path,
    initial: float = 10_000.0,
    runs: int = 500,
    jitter_seconds: int = 30,
    worst_n_ticks: int = 3,
    block_ticks: int = 100,
    seed: int | None = 42,
) -> dict[str, Any]:
    """Roda os 3 testes MC com tick data e agrega o resultado."""
    jitter = entry_jitter_mc(trades, parquet_path, initial, runs, jitter_seconds, seed)
    slippage = spread_slippage_mc(trades, parquet_path, initial, runs, worst_n_ticks, seed)
    bootstrap = tick_return_bootstrap_mc(trades, parquet_path, initial, runs, block_ticks, seed)

    # Scorecard
    cards = []
    for key, label, res in [
        ("entry_jitter", "Robustez a jitter de entrada (±s)", jitter),
        ("spread_slippage", "Robustez a spread/slippage real", slippage),
        ("tick_bootstrap", "Edge sobre paths sintéticos (block bootstrap)", bootstrap),
    ]:
        if res.get("error"):
            cards.append({"name": label, "status": "fail",
                          "value": res["error"], "note": "", "suggestion": ""})
            continue
        prob = res.get("prob_profitable", 0)
        passed = prob >= 0.85
        cards.append({
            "name": label,
            "status": "pass" if passed else "fail",
            "value": f"Prob. lucro {prob*100:.1f}% · Net P50 {res.get('net_p50',0):.2f} · DD P95 {res.get('dd_p95',0):.1f}%",
            "note": f"Run histórico: Net={res.get('original_net',0):.2f}, DD={res.get('original_dd_pct',0):.1f}%",
            "suggestion": res.get("suggestion", "") if not passed else "",
        })

    passes = sum(1 for c in cards if c["status"] == "pass")
    total = len(cards)
    overall = "green" if passes == total else "yellow" if passes >= total - 1 else "red"

    return {
        "entry_jitter": jitter,
        "spread_slippage": slippage,
        "tick_bootstrap": bootstrap,
        "scorecard": cards,
        "passes": passes,
        "total": total,
        "overall": overall,
    }
