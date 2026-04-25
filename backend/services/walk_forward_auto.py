"""Walk-Forward Analysis end-to-end — orquestrador que roda MT5 em cada fold.

Para cada fold gerado por `walk_forward.split_folds`:
  1. Otimização MT5 no período IS (mt5_runner + optimizer.parse_optimization_xml)
  2. Pega top-N passes pelo critério escolhido
  3. Para cada um, backtest no período OOS e coleta métricas
  4. Agrega num scorecard com stability/consistency/degradation

É pesado (otimização do MT5 leva minutos a horas por fold). O endpoint
expõe a execução sequencial — roda em thread de fundo e reporta progresso
via endpoint separado de polling.
"""
from __future__ import annotations

import threading
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from models.schemas import (
    ModelingQuality,
    OptimizationCriterion,
    ParameterRange,
)
from services import (
    analytics,
    mt5_report,
    mt5_runner,
    optimizer,
    storage,
    walk_forward,
)


@dataclass
class WFAAutoJob:
    job_id: str
    folds: list[dict[str, Any]]
    is_results: list[dict[str, Any]] = field(default_factory=list)
    oos_results: list[dict[str, Any]] = field(default_factory=list)
    status: str = "pending"           # pending | running | done | error
    progress: str = ""
    error: str | None = None
    # Scorecard final
    stability_score: float | None = None
    consistency: float | None = None
    degradation: float | None = None


# Singleton de jobs rodando — em memória (single-user)
_jobs: dict[str, WFAAutoJob] = {}
_jobs_lock = threading.Lock()


def get_job(job_id: str) -> WFAAutoJob | None:
    with _jobs_lock:
        return _jobs.get(job_id)


def list_jobs() -> list[WFAAutoJob]:
    with _jobs_lock:
        return list(_jobs.values())


def _run_job(
    job: WFAAutoJob,
    terminal_exe: Path,
    data_folder: Path,
    ea_relative_path: str,
    ea_inputs_defaults: dict[str, Any],
    ranges: list[ParameterRange],
    symbol: str,
    period: str,
    modeling: ModelingQuality,
    criterion: OptimizationCriterion,
    deposit: float,
    top_n: int,
    score_key: str,
) -> None:
    job.status = "running"
    env = mt5_runner.MT5Environment(terminal_exe=terminal_exe, data_folder=data_folder)

    try:
        for fold_idx, fold in enumerate(job.folds):
            job.progress = f"Fold {fold_idx+1}/{len(job.folds)} — otimizando IS"
            is_from = date.fromisoformat(fold["is_start"])
            is_to = date.fromisoformat(fold["is_end"])
            oos_from = date.fromisoformat(fold["oos_start"])
            oos_to = date.fromisoformat(fold["oos_end"])

            # 1) Otimização IS
            res_is = mt5_runner.prepare_and_run(
                env=env, ea_relative_path=ea_relative_path,
                ea_inputs_defaults=ea_inputs_defaults, ranges=ranges,
                symbol=symbol, period=period,
                from_date=is_from, to_date=is_to,
                modeling=modeling, optimization=1, criterion=criterion,
                deposit=deposit, leverage=100, currency="USD",
                timeout_seconds=7200,
            )
            if not res_is.report_path:
                raise RuntimeError(f"Fold {fold_idx+1}: otimização IS sem XML")
            # Localiza o XML de otimização (normalmente .xml ao lado do HTM)
            xml_candidates = list(Path(res_is.report_path).parent.glob("*Optim*.xml"))
            if not xml_candidates:
                raise RuntimeError(f"Fold {fold_idx+1}: XML de otimização não encontrado")
            passes = optimizer.parse_optimization_xml(xml_candidates[0], criterion=score_key)
            if not passes:
                raise RuntimeError(f"Fold {fold_idx+1}: XML sem passes válidos")

            top = sorted(
                passes,
                key=lambda p: (p.metrics.get(score_key) or -1e18),
                reverse=True,
            )[:top_n]

            # 2) Para cada top param, backtest no OOS
            fold_oos = []
            for i, p in enumerate(top):
                job.progress = (
                    f"Fold {fold_idx+1}/{len(job.folds)} — "
                    f"OOS pass {i+1}/{len(top)}"
                )
                merged_inputs = {**ea_inputs_defaults, **p.parameters}
                res_oos = mt5_runner.prepare_and_run(
                    env=env, ea_relative_path=ea_relative_path,
                    ea_inputs_defaults=merged_inputs, ranges=[],
                    symbol=symbol, period=period,
                    from_date=oos_from, to_date=oos_to,
                    modeling=modeling, optimization=0, criterion=criterion,
                    deposit=deposit, leverage=100, currency="USD",
                    timeout_seconds=3600,
                )
                if not res_oos.report_path:
                    fold_oos.append({"pass_idx": p.pass_idx, "error": "sem report"})
                    continue
                rp = Path(res_oos.report_path)
                parsed = mt5_report.parse_report_htm(rp)
                deals = mt5_report.extract_deals_htm(rp)
                trades = mt5_report.deals_to_trades(deals)

                # Salva como run (kind='wfa_oos')
                run_id = uuid.uuid4().hex[:12]
                storage.save_run(
                    run_id=run_id, kind="wfa_oos", ea_path=ea_relative_path,
                    symbol=symbol, timeframe=period,
                    from_date=oos_from.isoformat(), to_date=oos_to.isoformat(),
                    deposit=deposit, report_path=str(rp),
                    parameters=merged_inputs, metrics=parsed.get("metrics") or {},
                    label=f"WFA fold#{fold_idx+1} OOS pass#{p.pass_idx}",
                )
                storage.save_trades(run_id, trades)
                try:
                    full = analytics.full_analysis(trades, deposit)
                    storage.save_analysis(run_id, deposit, full)
                except Exception:  # noqa: BLE001
                    pass

                fold_oos.append({
                    "pass_idx": p.pass_idx,
                    "parameters": p.parameters,
                    "is_metric": p.metrics.get(score_key),
                    "oos_metrics": parsed.get("metrics") or {},
                    "run_id": run_id,
                })

            # Agrega metric do fold (média das top-N)
            is_scores = [float(p.metrics.get(score_key) or 0) for p in top]
            oos_scores = [
                float((r.get("oos_metrics") or {}).get(score_key) or 0)
                for r in fold_oos if "oos_metrics" in r
            ]
            job.is_results.append({
                "fold": fold_idx + 1,
                "score_key": score_key,
                "mean": float(np.mean(is_scores)) if is_scores else 0.0,
                "top_n": len(is_scores),
            })
            job.oos_results.append({
                "fold": fold_idx + 1,
                "score_key": score_key,
                "mean": float(np.mean(oos_scores)) if oos_scores else 0.0,
                "top_n": len(oos_scores),
                "details": fold_oos,
            })

        # Scorecard final
        is_means = [r["mean"] for r in job.is_results]
        oos_means = [r["mean"] for r in job.oos_results]
        mean_is = float(np.mean(is_means)) if is_means else 0.0
        mean_oos = float(np.mean(oos_means)) if oos_means else 0.0
        job.stability_score = (mean_oos / mean_is) if abs(mean_is) > 1e-9 else 0.0
        job.consistency = (
            float(np.mean([1.0 if v > 0 else 0.0 for v in oos_means]))
            if oos_means else 0.0
        )
        job.degradation = (
            (mean_is - mean_oos) / mean_is if abs(mean_is) > 1e-9 else 0.0
        )
        job.progress = f"Concluído: {len(job.folds)} folds"
        job.status = "done"

    except Exception as e:  # noqa: BLE001
        job.status = "error"
        job.error = f"{type(e).__name__}: {e}"
        print(f"[wfa_auto] {traceback.format_exc()}")


def start_wfa_job(
    terminal_exe: str | Path,
    data_folder: str | Path,
    ea_relative_path: str,
    ea_inputs_defaults: dict[str, Any],
    ranges: list[ParameterRange],
    symbol: str,
    period: str,
    start_date: date,
    end_date: date,
    folds: int,
    oos_pct: float,
    anchored: bool,
    modeling: ModelingQuality = ModelingQuality.REAL_TICKS,
    criterion: OptimizationCriterion = OptimizationCriterion.COMPLEX,
    deposit: float = 10_000.0,
    top_n: int = 3,
    score_key: str = "profit_factor",
) -> WFAAutoJob:
    """Cria um job WFA e inicia em thread de fundo. Retorna o job_id pra polling."""
    fold_defs = walk_forward.split_folds(
        start=start_date, end=end_date,
        folds=folds, oos_pct=oos_pct, anchored=anchored,
    )
    fold_dicts = [{
        "idx": f.idx,
        "is_start": f.is_start.isoformat(), "is_end": f.is_end.isoformat(),
        "oos_start": f.oos_start.isoformat(), "oos_end": f.oos_end.isoformat(),
    } for f in fold_defs]

    job = WFAAutoJob(job_id=uuid.uuid4().hex[:12], folds=fold_dicts)
    with _jobs_lock:
        _jobs[job.job_id] = job

    t = threading.Thread(
        target=_run_job,
        args=(job, Path(terminal_exe), Path(data_folder), ea_relative_path,
              ea_inputs_defaults, ranges, symbol, period, modeling, criterion,
              deposit, top_n, score_key),
        daemon=True,
    )
    t.start()
    return job


def job_as_dict(j: WFAAutoJob) -> dict[str, Any]:
    return {
        "job_id": j.job_id,
        "folds": j.folds,
        "is_results": j.is_results,
        "oos_results": j.oos_results,
        "status": j.status,
        "progress": j.progress,
        "error": j.error,
        "stability_score": j.stability_score,
        "consistency": j.consistency,
        "degradation": j.degradation,
    }
