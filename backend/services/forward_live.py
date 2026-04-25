"""Captura trades reais (forward live) do MT5 e compara com um backtest.

Para validar se a performance real está seguindo o backtest (sanity check
típico em trading quant). Usa o pacote oficial MetaTrader5 pra baixar o
histórico de deals da conta ativa.

Fluxo:
  1. `fetch_live_trades(terminal_exe, symbol, from_dt, to_dt, magic=None)`
     → extrai trades fechados da conta via history_deals_get
  2. Compara com trades do Run histórico correspondente (mesmo símbolo,
     mesmo EA) usando as métricas padrão do analytics.
  3. Retorna tracking error, Sharpe diff, DD diff, etc.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from services import analytics


@dataclass
class LiveSnapshot:
    source: str                          # "live_mt5"
    terminal_exe: str
    symbol: str
    from_datetime: str
    to_datetime: str
    num_deals: int
    trades: list[dict[str, Any]]         # mesmo formato do report.deals_to_trades


@dataclass
class ForwardComparison:
    backtest_metrics: dict[str, Any]
    live_metrics: dict[str, Any]
    diff: dict[str, float]               # live - backtest em cada métrica-chave
    tracking: dict[str, float]           # ratios (live/backtest)
    num_trades_backtest: int
    num_trades_live: int
    interpretation: str


def fetch_live_trades(
    terminal_exe: str | Path,
    symbol: str,
    from_datetime: datetime,
    to_datetime: datetime,
    magic_number: int | None = None,
) -> LiveSnapshot:
    """Baixa trades fechados da conta logada no terminal MT5 informado.

    Filtra por símbolo; se `magic_number` for dado, filtra por ele também
    (útil pra isolar um EA específico de uma conta com vários EAs).
    """
    import MetaTrader5 as mt5

    terminal_exe = Path(terminal_exe)
    if not terminal_exe.exists():
        raise FileNotFoundError(f"terminal64.exe não encontrado: {terminal_exe}")

    if not mt5.initialize(path=str(terminal_exe)):
        raise RuntimeError(f"mt5.initialize falhou: {mt5.last_error()}")

    try:
        deals = mt5.history_deals_get(from_datetime, to_datetime, group=f"*{symbol}*")
        if deals is None:
            err = mt5.last_error()
            raise RuntimeError(f"history_deals_get retornou None: {err}")

        # Converte em trades no formato do analytics. Agrupamos deals por position_id
        # (entrada + saída = 1 trade).
        by_pos: dict[int, dict[str, Any]] = {}
        for d in deals:
            if magic_number is not None and int(d.magic) != magic_number:
                continue
            pid = int(d.position_id)
            entry = int(d.entry)  # 0=in, 1=out, 2=inout, 3=out_by
            slot = by_pos.setdefault(pid, {
                "position_id": pid, "symbol": d.symbol,
                "time_in": None, "time_out": None,
                "entry_price": 0.0, "exit_price": 0.0,
                "volume": 0.0, "side": None,
                "profit": 0.0, "swap": 0.0, "commission": 0.0,
            })
            ts = datetime.fromtimestamp(d.time).strftime("%Y-%m-%d %H:%M:%S")
            if entry == 0:  # IN
                slot["time_in"] = ts
                slot["entry_price"] = float(d.price)
                slot["volume"] = float(d.volume)
                slot["side"] = "buy" if int(d.type) == 0 else "sell"
            else:  # OUT / OUT_BY / INOUT
                slot["time_out"] = ts
                slot["exit_price"] = float(d.price)
                slot["profit"] += float(d.profit)
                slot["swap"] += float(d.swap)
                slot["commission"] += float(d.commission)

        # Converte no formato esperado pelo analytics
        trades = []
        for pid, s in by_pos.items():
            if s["time_in"] is None or s["time_out"] is None:
                continue  # posição ainda aberta ou incompleta
            dur = 0
            try:
                ti = datetime.strptime(s["time_in"], "%Y-%m-%d %H:%M:%S")
                to = datetime.strptime(s["time_out"], "%Y-%m-%d %H:%M:%S")
                dur = int((to - ti).total_seconds())
            except ValueError:
                pass
            trades.append({
                "time_in": s["time_in"], "time_out": s["time_out"],
                "side": s["side"], "volume": s["volume"],
                "entry_price": s["entry_price"], "exit_price": s["exit_price"],
                "profit": s["profit"] + s["swap"] + s["commission"],
                "balance": 0.0, "duration_sec": dur,
                "symbol": s["symbol"],
            })
        # Ordena por tempo
        trades.sort(key=lambda t: t["time_in"] or "")

        return LiveSnapshot(
            source="live_mt5",
            terminal_exe=str(terminal_exe),
            symbol=symbol,
            from_datetime=from_datetime.isoformat(),
            to_datetime=to_datetime.isoformat(),
            num_deals=len(deals),
            trades=trades,
        )
    finally:
        mt5.shutdown()


def compare_to_backtest(
    live_trades: list[dict[str, Any]],
    backtest_trades: list[dict[str, Any]],
    initial_equity: float = 10_000.0,
) -> ForwardComparison:
    """Compara métricas do live vs backtest. Retorna diff + interpretação."""
    if not live_trades:
        raise ValueError("Sem trades live — amplie o range de datas ou verifique magic_number")
    if not backtest_trades:
        raise ValueError("Sem trades no backtest de referência")

    live_full = analytics.full_analysis(live_trades, initial_equity)
    bt_full = analytics.full_analysis(backtest_trades, initial_equity)

    keys = ["net_profit", "win_rate", "sharpe_ratio", "sortino_ratio",
            "profit_factor", "max_drawdown_pct", "expectancy"]
    diff: dict[str, float] = {}
    tracking: dict[str, float] = {}
    for k in keys:
        live_v = float(live_full.get(k) or 0)
        bt_v = float(bt_full.get(k) or 0)
        diff[k] = live_v - bt_v
        if abs(bt_v) > 1e-9:
            tracking[k] = live_v / bt_v

    # Heurística de interpretação
    pf_ratio = tracking.get("profit_factor", 0)
    dd_ratio = (abs(live_full.get("max_drawdown_pct") or 0) /
                max(abs(bt_full.get("max_drawdown_pct") or 1), 1e-9))
    if pf_ratio >= 0.85 and dd_ratio <= 1.3:
        interpret = "OK: live está acompanhando o backtest dentro de tolerância razoável."
    elif pf_ratio >= 0.6 and dd_ratio <= 1.8:
        interpret = "ATENÇÃO: degradação moderada. Avalie spread/slippage/execution."
    else:
        interpret = (
            "DIVERGÊNCIA: live muito abaixo do backtest — suspeita forte de "
            "overfit, mudança de regime ou problema de execução."
        )

    return ForwardComparison(
        backtest_metrics={k: bt_full.get(k) for k in keys},
        live_metrics={k: live_full.get(k) for k in keys},
        diff=diff,
        tracking=tracking,
        num_trades_backtest=len(backtest_trades),
        num_trades_live=len(live_trades),
        interpretation=interpret,
    )


def snapshot_as_dict(s: LiveSnapshot) -> dict[str, Any]:
    return {
        "source": s.source,
        "terminal_exe": s.terminal_exe,
        "symbol": s.symbol,
        "from_datetime": s.from_datetime,
        "to_datetime": s.to_datetime,
        "num_deals": s.num_deals,
        "num_trades": len(s.trades),
        "trades_preview": s.trades[:5],
    }


def comparison_as_dict(c: ForwardComparison) -> dict[str, Any]:
    return {
        "backtest_metrics": c.backtest_metrics,
        "live_metrics": c.live_metrics,
        "diff": c.diff,
        "tracking": c.tracking,
        "num_trades_backtest": c.num_trades_backtest,
        "num_trades_live": c.num_trades_live,
        "interpretation": c.interpretation,
    }
