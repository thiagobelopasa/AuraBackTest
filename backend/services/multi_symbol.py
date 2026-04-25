"""Orquestra execução do mesmo EA em múltiplos símbolos.

Dado um EA + lista de (symbol, period, from_date, to_date), executa cada
backtest sequencialmente via `mt5_runner.prepare_and_run` e coleta os
resultados. Para cada backtest bem-sucedido, faz ingest HTM → run salvo
no banco → pronto pra análise individual.

Execução é sequencial porque cada instância do MT5 Strategy Tester trava
a GUI do terminal. Paralelo requer múltiplos terminais ou agentes remotos —
fica pra iteração futura.
"""
from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

from models.schemas import ModelingQuality, OptimizationCriterion, ParameterRange
from services import mt5_report, mt5_runner, storage


@dataclass
class SymbolJob:
    symbol: str
    period: str = "M1"
    from_date: date | str = "2024-01-01"
    to_date: date | str = "2024-01-31"


@dataclass
class MultiSymbolResult:
    symbol: str
    run_id: str | None
    ok: bool
    error: str | None
    elapsed_seconds: float
    metrics: dict[str, Any] = field(default_factory=dict)


def run_multi_symbol(
    terminal_exe: str | Path,
    data_folder: str | Path,
    ea_relative_path: str,
    ea_inputs_defaults: dict[str, Any],
    jobs: list[SymbolJob],
    deposit: float = 10_000.0,
    leverage: int = 100,
    currency: str = "USD",
    modeling: ModelingQuality = ModelingQuality.REAL_TICKS,
    criterion: OptimizationCriterion = OptimizationCriterion.COMPLEX,
    label_prefix: str = "multi",
    progress: Callable[[int, int, str], None] | None = None,
) -> list[MultiSymbolResult]:
    """Roda o mesmo EA em múltiplos símbolos. Salva cada resultado como Run
    tradicional (kind='multi_symbol') pra aparecer no Histórico e análise.

    progress: callback(done, total, symbol) chamado antes de cada job.
    """
    env = mt5_runner.MT5Environment(
        terminal_exe=Path(terminal_exe), data_folder=Path(data_folder),
    )
    results: list[MultiSymbolResult] = []
    for i, job in enumerate(jobs):
        if progress:
            try: progress(i, len(jobs), job.symbol)
            except Exception: pass  # noqa: BLE001
        from_date = job.from_date if isinstance(job.from_date, date) else date.fromisoformat(str(job.from_date))
        to_date = job.to_date if isinstance(job.to_date, date) else date.fromisoformat(str(job.to_date))
        import time
        start = time.time()
        try:
            res = mt5_runner.prepare_and_run(
                env=env,
                ea_relative_path=ea_relative_path,
                ea_inputs_defaults=ea_inputs_defaults,
                ranges=[],
                symbol=job.symbol,
                period=job.period,
                from_date=from_date,
                to_date=to_date,
                modeling=modeling,
                optimization=0,
                criterion=criterion,
                deposit=deposit,
                leverage=leverage,
                currency=currency,
                timeout_seconds=3600,
            )
            elapsed = time.time() - start
            if not res.report_path:
                results.append(MultiSymbolResult(
                    symbol=job.symbol, run_id=None, ok=False,
                    error="Sem report HTM produzido", elapsed_seconds=elapsed,
                ))
                continue

            # Ingest HTM → cria Run no banco
            import uuid
            run_id = uuid.uuid4().hex[:12]
            report_path = Path(res.report_path)
            parsed = mt5_report.parse_report_htm(report_path)
            deals = mt5_report.extract_deals_htm(report_path)
            trades = mt5_report.deals_to_trades(deals)

            storage.save_run(
                run_id=run_id, kind="multi_symbol",
                ea_path=ea_relative_path,
                symbol=job.symbol, timeframe=job.period,
                from_date=from_date.isoformat(), to_date=to_date.isoformat(),
                deposit=deposit, report_path=str(report_path),
                parameters=ea_inputs_defaults, metrics=parsed.get("metrics") or {},
                label=f"{label_prefix} — {job.symbol}",
            )
            storage.save_trades(run_id, trades)
            # Analysis completo (pra abrir direto na aba Análise)
            try:
                from services import analytics
                full = analytics.full_analysis(trades, deposit)
                storage.save_analysis(run_id, deposit, full)
            except Exception:  # noqa: BLE001
                pass  # analytics opcional, o run já está salvo

            results.append(MultiSymbolResult(
                symbol=job.symbol, run_id=run_id, ok=True, error=None,
                elapsed_seconds=elapsed, metrics=parsed.get("metrics") or {},
            ))
        except Exception as e:  # noqa: BLE001
            elapsed = time.time() - start
            results.append(MultiSymbolResult(
                symbol=job.symbol, run_id=None, ok=False,
                error=f"{type(e).__name__}: {e}",
                elapsed_seconds=elapsed,
            ))
            print(f"[multi_symbol] erro em {job.symbol}: {traceback.format_exc()}")

    return results


def as_dict(r: MultiSymbolResult) -> dict[str, Any]:
    return {
        "symbol": r.symbol,
        "run_id": r.run_id,
        "ok": r.ok,
        "error": r.error,
        "elapsed_seconds": round(r.elapsed_seconds, 2),
        "metrics": r.metrics,
    }
