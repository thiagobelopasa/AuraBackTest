"""Endpoints de análise: full_analysis, Monte Carlo, Walk-Forward, histórico."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from services import (
    analytics,
    equity_control as ec,
    mm_simulator as mms,
    monte_carlo as mc,
    mt5_env,
    mt5_processes,
    mt5_report,
    mt5_ticks_auto,
    robustness,
    stat_tests,
    storage,
    tick_mae_mfe,
    tick_monte_carlo as tmc,
    walk_forward as wfa,
    whatif,
)


router = APIRouter(prefix="/analysis", tags=["analysis"])


# -------------------------------------------------------------- ingest report
class IngestReportRequest(BaseModel):
    run_id: str = Field(description="ID único do run (ex: do /mt5/run-single)")
    report_path: str
    ea_path: str | None = None
    symbol: str | None = None
    timeframe: str | None = None
    from_date: date | None = None
    to_date: date | None = None
    deposit: float = 10_000.0
    parameters: dict[str, Any] = {}
    label: str | None = Field(
        default=None,
        description="Nome amigável pra identificar o robô (ex: 'Big-Small v2 - agressivo')",
    )


class IngestReportResponse(BaseModel):
    run_id: str
    num_trades: int
    metrics: dict[str, Any]


@router.post("/ingest", response_model=IngestReportResponse)
def ingest_report(req: IngestReportRequest) -> IngestReportResponse:
    """Parseia um report HTM, extrai trades, persiste e retorna análise completa."""
    path = Path(req.report_path)
    if not path.exists():
        raise HTTPException(404, f"Report não encontrado: {path}")

    parsed = mt5_report.parse_report_htm(path)
    deals = mt5_report.extract_deals_htm(path)
    trades = mt5_report.deals_to_trades(deals)

    deposit = req.deposit
    if deposit == 10_000.0:
        parsed_deposit = parsed["metrics"].get("initial_deposit")
        if parsed_deposit:
            deposit = float(parsed_deposit)

    analysis = analytics.full_analysis(trades, initial_equity=deposit)

    storage.init_db()
    storage.save_run(
        run_id=req.run_id,
        kind="single",
        ea_path=req.ea_path,
        symbol=req.symbol,
        timeframe=req.timeframe,
        from_date=req.from_date.isoformat() if req.from_date else None,
        to_date=req.to_date.isoformat() if req.to_date else None,
        deposit=deposit,
        report_path=str(path),
        parameters=req.parameters,
        metrics=parsed["metrics"],
        label=req.label,
    )
    storage.save_trades(req.run_id, trades)
    storage.save_analysis(req.run_id, deposit, analysis)

    return IngestReportResponse(
        run_id=req.run_id,
        num_trades=len(trades),
        metrics=analysis,
    )


# --------------------------------------------------------------- upload HTM
@router.post("/ingest-upload", response_model=IngestReportResponse)
async def ingest_upload(
    file: UploadFile = File(...),
    symbol: str | None = Form(None),
    timeframe: str | None = Form(None),
    deposit: float = Form(10_000.0),
    label: str | None = Form(None),
) -> IngestReportResponse:
    """Upload de .htm exportado do MT5 (ou do próprio app). Salva em disco,
    parseia, extrai trades e persiste no SQLite. Retorna run_id para abrir
    na aba Análise."""
    content = await file.read()
    if not content:
        raise HTTPException(400, "Arquivo vazio")

    uploads_dir = Path(__file__).resolve().parents[1] / "data" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex[:8]
    suffix = Path(file.filename or "report.htm").suffix or ".htm"
    saved_path = uploads_dir / f"{run_id}{suffix}"
    saved_path.write_bytes(content)

    parsed = mt5_report.parse_report_htm(saved_path)
    deals = mt5_report.extract_deals_htm(saved_path)
    trades = mt5_report.deals_to_trades(deals)
    if not trades:
        raise HTTPException(400, "Nenhum trade encontrado no HTM. Confira se é um report com tabela de deals.")

    if deposit == 10_000.0:
        parsed_deposit = parsed["metrics"].get("initial_deposit")
        if parsed_deposit:
            deposit = float(parsed_deposit)

    analysis = analytics.full_analysis(trades, initial_equity=deposit)

    storage.init_db()
    storage.save_run(
        run_id=run_id, kind="single", ea_path=None,
        symbol=symbol, timeframe=timeframe,
        from_date=None, to_date=None,
        deposit=deposit, report_path=str(saved_path),
        parameters={}, metrics=parsed["metrics"],
        label=label,
    )
    storage.save_trades(run_id, trades)
    storage.save_analysis(run_id, deposit, analysis)

    return IngestReportResponse(run_id=run_id, num_trades=len(trades), metrics=analysis)


# --------------------------------------------------------------- analyze only
class AnalyzeRequest(BaseModel):
    run_id: str
    initial_equity: float = 10_000.0


@router.post("/analyze")
def analyze(req: AnalyzeRequest) -> dict[str, Any]:
    """Recalcula full_analysis para um run já ingestado. Usa trades do SQLite."""
    storage.init_db()
    trades = storage.load_trades(req.run_id)
    if not trades:
        raise HTTPException(404, f"Nenhum trade para run_id={req.run_id}")
    result = analytics.full_analysis(trades, req.initial_equity)
    storage.save_analysis(req.run_id, req.initial_equity, result)
    return result


# ------------------------------------------------------------------ Monte Carlo
class MonteCarloRequest(BaseModel):
    run_id: str
    initial_equity: float = 10_000.0
    runs: int = Field(default=1000, ge=100, le=100_000)
    mode: Literal["shuffle", "bootstrap", "skip", "noise"] = "shuffle"
    seed: int | None = None
    skip_pct: float = Field(default=0.1, ge=0.01, le=0.5)
    noise_pct: float = Field(default=0.1, ge=0.01, le=1.0)


@router.post("/monte-carlo")
def run_monte_carlo(req: MonteCarloRequest) -> dict[str, Any]:
    storage.init_db()
    trades = storage.load_trades(req.run_id)
    if not trades:
        raise HTTPException(404, f"Nenhum trade para run_id={req.run_id}")
    result = mc.monte_carlo(
        trades, initial_equity=req.initial_equity,
        runs=req.runs, mode=req.mode, seed=req.seed,
        skip_pct=req.skip_pct, noise_pct=req.noise_pct,
    ).to_dict()
    storage.save_monte_carlo(req.run_id, req.mode, req.runs, req.seed, result)
    return result


# -------------------------------------------------------------- Robustness suite
class RobustnessSuiteRequest(BaseModel):
    run_id: str
    initial_equity: float = 10_000.0
    runs: int = Field(default=2000, ge=100, le=20_000)
    seed: int | None = 42
    block_size: int = Field(default=5, ge=2, le=50)
    skip_pct: float = Field(default=0.2, ge=0.01, le=0.5)
    noise_pct: float = Field(default=0.25, ge=0.01, le=1.0)
    n_trials: int = Field(default=1, ge=1, description="Quantos candidatos foram testados na otimização (ex: 3663)")
    var_sr_trials: float = Field(default=0.0, ge=0.0, description="Variância do Sharpe entre os candidatos — se 0, DSR não é calculado")


@router.post("/robustness-suite")
def robustness_suite(req: RobustnessSuiteRequest) -> dict[str, Any]:
    storage.init_db()
    trades = storage.load_trades(req.run_id)
    if not trades:
        raise HTTPException(404, f"Nenhum trade para run_id={req.run_id}")
    return robustness.run_suite(
        trades,
        initial=req.initial_equity,
        runs=req.runs,
        seed=req.seed,
        block_size=req.block_size,
        skip_pct=req.skip_pct,
        noise_pct=req.noise_pct,
        n_trials=req.n_trials,
        var_sr_trials=req.var_sr_trials,
    )


# -------------------------------------------------------------- Walk-Forward
class WFASplitRequest(BaseModel):
    start: date
    end: date
    folds: int = Field(default=5, ge=1, le=50)
    oos_pct: float = Field(default=0.25, gt=0, lt=1)
    anchored: bool = False


@router.post("/wfa/split")
def wfa_split(req: WFASplitRequest) -> list[dict[str, Any]]:
    """Só retorna os folds calculados — útil pro frontend exibir o plano de WFA
    antes de rodar a otimização fold-a-fold."""
    folds = wfa.split_folds(
        req.start, req.end, req.folds, oos_pct=req.oos_pct, anchored=req.anchored
    )
    return [
        {
            "idx": f.idx,
            "is_start": f.is_start.isoformat(),
            "is_end": f.is_end.isoformat(),
            "oos_start": f.oos_start.isoformat(),
            "oos_end": f.oos_end.isoformat(),
        }
        for f in folds
    ]


class WFAScoreRequest(BaseModel):
    is_metrics: list[dict[str, Any]]
    oos_metrics: list[dict[str, Any]]
    score_field: str = "net_profit"


@router.post("/wfa/score")
def wfa_score(req: WFAScoreRequest) -> dict[str, Any]:
    """Calcula estabilidade / consistência / degradação a partir das métricas
    de cada fold — o orquestrador full-WFA (roda MT5 N vezes) vem em optimization."""
    res = wfa.compute_wfa_score(req.is_metrics, req.oos_metrics, req.score_field)
    return {
        "stability_score": res.stability_score,
        "consistency": res.consistency,
        "degradation": res.degradation,
        "is_metrics": res.is_metrics,
        "oos_metrics": res.oos_metrics,
    }


# ----------------------------------------------------------------- Histórico
@router.get("/runs")
def list_runs(limit: int = 50, kind: str | None = None) -> list[dict[str, Any]]:
    storage.init_db()
    return storage.list_runs(limit=limit, kind=kind)


@router.get("/runs/{run_id}")
def get_run_detail(run_id: str) -> dict[str, Any]:
    storage.init_db()
    run = storage.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run não encontrado: {run_id}")
    trades = storage.load_trades(run_id)
    analysis = storage.load_analysis(run_id)
    mcs = storage.list_monte_carlo(run_id)
    return {
        "run": run,
        "trades_count": len(trades),
        "analysis": analysis["result"] if analysis else None,
        "monte_carlo_runs": mcs,
    }


@router.get("/runs/{run_id}/trades")
def get_run_trades(run_id: str) -> list[dict[str, Any]]:
    storage.init_db()
    return storage.load_trades(run_id)


class UpdateLabelRequest(BaseModel):
    label: str


@router.patch("/runs/{run_id}/label")
def patch_run_label(run_id: str, req: UpdateLabelRequest) -> dict[str, Any]:
    storage.init_db()
    ok = storage.update_run_label(run_id, req.label.strip())
    if not ok:
        raise HTTPException(404, f"Run não encontrado: {run_id}")
    return {"run_id": run_id, "label": req.label.strip()}


class FavoriteRequest(BaseModel):
    favorite: bool


@router.patch("/runs/{run_id}/favorite")
def patch_run_favorite(run_id: str, req: FavoriteRequest) -> dict[str, Any]:
    storage.init_db()
    ok = storage.set_run_favorite(run_id, req.favorite)
    if not ok:
        raise HTTPException(404, f"Run não encontrado: {run_id}")
    return {"run_id": run_id, "favorite": req.favorite}


# ---------------------------------------------------------- Forward live vs backtest
class ForwardCompareRequest(BaseModel):
    run_id: str                         # Run de backtest pra comparar
    terminal_exe: str                   # terminal64.exe da conta live
    symbol: str
    from_datetime: datetime
    to_datetime: datetime
    magic_number: int | None = None     # filtra por magic (isola o EA)
    initial_equity: float = 10_000.0


class WFAAutoStartRequest(BaseModel):
    terminal_exe: str
    data_folder: str
    ea_relative_path: str
    ea_inputs_defaults: dict[str, Any]
    ranges: list[dict[str, Any]] = Field(default_factory=list)
    symbol: str
    period: str = "M1"
    start_date: date
    end_date: date
    folds: int = 4
    oos_pct: float = 0.25
    anchored: bool = False
    deposit: float = 10_000.0
    top_n: int = 3
    score_key: str = "profit_factor"


@router.post("/wfa-auto/start")
def wfa_auto_start(req: WFAAutoStartRequest) -> dict[str, Any]:
    """Dispara WFA end-to-end em background. Retorna job_id pra polling."""
    from services import walk_forward_auto
    from models.schemas import ParameterRange

    ranges = [ParameterRange(**r) for r in req.ranges] if req.ranges else []
    job = walk_forward_auto.start_wfa_job(
        terminal_exe=req.terminal_exe, data_folder=req.data_folder,
        ea_relative_path=req.ea_relative_path,
        ea_inputs_defaults=req.ea_inputs_defaults, ranges=ranges,
        symbol=req.symbol, period=req.period,
        start_date=req.start_date, end_date=req.end_date,
        folds=req.folds, oos_pct=req.oos_pct, anchored=req.anchored,
        deposit=req.deposit, top_n=req.top_n, score_key=req.score_key,
    )
    return walk_forward_auto.job_as_dict(job)


@router.get("/wfa-auto/job/{job_id}")
def wfa_auto_job(job_id: str) -> dict[str, Any]:
    from services import walk_forward_auto

    job = walk_forward_auto.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job não encontrado: {job_id}")
    return walk_forward_auto.job_as_dict(job)


@router.get("/wfa-auto/jobs")
def wfa_auto_jobs() -> list[dict[str, Any]]:
    from services import walk_forward_auto
    return [walk_forward_auto.job_as_dict(j) for j in walk_forward_auto.list_jobs()]


@router.post("/forward-compare")
def forward_compare(req: ForwardCompareRequest) -> dict[str, Any]:
    """Baixa trades reais do MT5 e compara com o backtest `run_id`."""
    from services import forward_live

    storage.init_db()
    run = storage.get_run(req.run_id)
    if not run:
        raise HTTPException(404, f"Run não encontrado: {req.run_id}")
    backtest_trades = storage.load_trades(req.run_id)
    if not backtest_trades:
        raise HTTPException(400, f"Run {req.run_id} sem trades salvos")

    try:
        snap = forward_live.fetch_live_trades(
            terminal_exe=req.terminal_exe,
            symbol=req.symbol,
            from_datetime=req.from_datetime,
            to_datetime=req.to_datetime,
            magic_number=req.magic_number,
        )
    except (FileNotFoundError, RuntimeError) as e:
        raise HTTPException(400, str(e)) from e

    try:
        cmp = forward_live.compare_to_backtest(
            snap.trades, backtest_trades, initial_equity=req.initial_equity,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    return {
        "live": forward_live.snapshot_as_dict(snap),
        "comparison": forward_live.comparison_as_dict(cmp),
    }


# ----------------------------------------------------------------- Fetch Ticks (auto)
class FetchTicksRequest(BaseModel):
    terminal_exe: str | None = None  # opcional — auto-detecta se omitido


def _resolve_terminal_exe(terminal_exe: str | None) -> str:
    """Retorna o caminho do terminal MT5 a usar, auto-detectando se necessário."""
    if terminal_exe:
        return terminal_exe
    # 1. Prefere terminal em execução (mais provável de ter o histórico carregado)
    running = mt5_processes.detect_running_mt5()
    if running:
        return running[0].terminal_exe
    # 2. Fallback: primeira instalação detectada no sistema
    installs = mt5_env.detect_installations()
    if installs:
        return str(installs[0].terminal_exe)
    raise HTTPException(
        400,
        "Nenhum terminal MT5 encontrado. Abra o MT5 e tente novamente, "
        "ou informe o caminho do terminal manualmente.",
    )


@router.post("/runs/{run_id}/fetch-ticks")
def fetch_run_ticks(run_id: str, req: FetchTicksRequest = FetchTicksRequest()) -> dict:
    """Baixa ticks do MT5 automaticamente usando os metadados do run (símbolo + datas).

    `terminal_exe` é opcional — se omitido, detecta o MT5 em execução ou a
    primeira instalação encontrada no sistema.
    """
    storage.init_db()
    run = storage.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run não encontrado: {run_id}")

    symbol = run.get("symbol")
    from_date = run.get("from_date")
    to_date = run.get("to_date")

    if not symbol:
        raise HTTPException(400, "Run não possui símbolo — informe symbol ao ingestar o report.")
    if not from_date or not to_date:
        raise HTTPException(
            400,
            "Run não possui datas (from_date / to_date). "
            "Re-ingestate o report passando os campos de data.",
        )

    try:
        from_dt = datetime.fromisoformat(from_date)
        to_dt = datetime.fromisoformat(to_date)
    except ValueError:
        raise HTTPException(400, f"Datas inválidas no run: {from_date!r} / {to_date!r}")

    terminal = _resolve_terminal_exe(req.terminal_exe)

    try:
        result = mt5_ticks_auto.fetch_ticks(
            terminal_exe=terminal,
            symbol=symbol,
            from_datetime=from_dt,
            to_datetime=to_dt,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(400, str(e)) from e

    storage.update_run_ticks_path(run_id, result.output_path)

    return {
        "run_id": run_id,
        "parquet_path": result.output_path,
        "rows": result.rows,
        "elapsed_seconds": result.elapsed_seconds,
        "symbol": result.symbol,
        "from_datetime": result.from_datetime,
        "to_datetime": result.to_datetime,
    }


# ----------------------------------------------------------------- What-If
class WhatIfRequest(BaseModel):
    excluded_hours: list[int] = Field(default_factory=list)
    excluded_weekdays: list[int] = Field(default_factory=list)
    initial_equity: float = 10_000.0


@router.post("/runs/{run_id}/whatif")
def run_whatif(run_id: str, req: WhatIfRequest) -> dict[str, Any]:
    storage.init_db()
    trades = storage.load_trades(run_id)
    if not trades:
        raise HTTPException(404, f"Nenhum trade para run_id={run_id}")
    run = storage.get_run(run_id)
    initial = req.initial_equity or (run.get("deposit") if run else 10_000.0) or 10_000.0
    return whatif.apply_whatif(trades, initial, req.excluded_hours, req.excluded_weekdays)


# ----------------------------------------------------------------- MM Simulator
class MMScenario(BaseModel):
    name: str
    mm_type: str  # "fixed_lots" | "risk_pct" | "fixed_risk_money"
    param: float


class MMSimRequest(BaseModel):
    scenarios: list[MMScenario]
    initial_equity: float = 10_000.0


@router.post("/runs/{run_id}/mm-simulate")
def mm_simulate(run_id: str, req: MMSimRequest) -> dict[str, Any]:
    storage.init_db()
    trades = storage.load_trades(run_id)
    if not trades:
        raise HTTPException(404, f"Nenhum trade para run_id={run_id}")
    run = storage.get_run(run_id)
    initial = req.initial_equity or (run.get("deposit") if run else 10_000.0) or 10_000.0
    results = mms.run_scenarios(trades, initial, [s.model_dump() for s in req.scenarios])
    return {"scenarios": results}


# ----------------------------------------------------------------- Equity Control
class EquityControlRequest(BaseModel):
    stop_after_consec_losses: int | None = None
    stop_after_dd_pct: float | None = None
    restart_after_days: int | None = None
    initial_equity: float = 10_000.0


@router.post("/runs/{run_id}/equity-control")
def equity_control(run_id: str, req: EquityControlRequest) -> dict[str, Any]:
    storage.init_db()
    trades = storage.load_trades(run_id)
    if not trades:
        raise HTTPException(404, f"Nenhum trade para run_id={run_id}")
    run = storage.get_run(run_id)
    initial = req.initial_equity or (run.get("deposit") if run else 10_000.0) or 10_000.0
    return ec.apply_equity_control(
        trades, initial,
        stop_after_consec_losses=req.stop_after_consec_losses,
        stop_after_dd_pct=req.stop_after_dd_pct,
        restart_after_days=req.restart_after_days,
    )


# ----------------------------------------------------------------- Stat Validation
@router.get("/runs/{run_id}/stat-validation")
def get_stat_validation(run_id: str) -> dict[str, Any]:
    """Bateria de testes estatísticos (t-stat, Ljung-Box, Runs, Outlier, Tail Ratio, JB)."""
    storage.init_db()
    trades = storage.load_trades(run_id)
    if not trades:
        raise HTTPException(404, f"Nenhum trade para run_id={run_id}")
    run = storage.get_run(run_id)
    initial = (run.get("deposit") if run else None) or 10_000.0
    return stat_tests.run_stat_validation(trades, initial)


# ----------------------------------------------------------------- MAE/MFE from ticks
class MaeMfeTicksRequest(BaseModel):
    parquet_path: str | None = None   # se omitido, usa ticks_parquet_path do run
    buffer_seconds: int = 60


@router.post("/runs/{run_id}/mae-mfe-ticks")
def mae_mfe_from_ticks(run_id: str, req: MaeMfeTicksRequest) -> dict[str, Any]:
    """Calcula MAE/MFE reais a partir de arquivo Parquet de ticks.

    Se `parquet_path` não for informado, usa o caminho salvo no run
    (preenchido automaticamente por /runs/{run_id}/fetch-ticks).
    """
    storage.init_db()
    trades = storage.load_trades(run_id)
    if not trades:
        raise HTTPException(404, f"Nenhum trade para run_id={run_id}")

    parquet_path = req.parquet_path
    if not parquet_path:
        run = storage.get_run(run_id)
        parquet_path = run.get("ticks_parquet_path") if run else None
    if not parquet_path:
        raise HTTPException(
            400,
            "Nenhum arquivo de ticks disponível. "
            "Use POST /runs/{run_id}/fetch-ticks para baixar do MT5 automaticamente.",
        )

    try:
        enriched = tick_mae_mfe.compute_mae_mfe(trades, parquet_path, req.buffer_seconds)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Erro ao processar ticks: {e}")
    stats = tick_mae_mfe.aggregate_mae_mfe_stats(enriched)
    return {"trades": enriched, "stats": stats}


# ----------------------------------------------------------------- Tick Monte Carlo
class TickMonteCarloRequest(BaseModel):
    parquet_path: str | None = None   # se omitido, usa ticks_parquet_path do run
    runs: int = Field(default=500, ge=50, le=5000)
    jitter_seconds: int = Field(default=30, ge=1, le=3600)
    worst_n_ticks: int = Field(default=3, ge=1, le=50)
    block_ticks: int = Field(default=100, ge=10, le=5000)
    seed: int | None = 42
    initial_equity: float = 10_000.0


@router.post("/runs/{run_id}/tick-monte-carlo")
def tick_monte_carlo(run_id: str, req: TickMonteCarloRequest) -> dict[str, Any]:
    """Monte Carlo usando dados de tick reais: entry jitter, spread slippage,
    block bootstrap de tick-returns. Complementa o MC sintético.

    Se `parquet_path` não for informado, usa o caminho salvo no run
    (preenchido automaticamente por /runs/{run_id}/fetch-ticks).
    """
    storage.init_db()
    trades = storage.load_trades(run_id)
    if not trades:
        raise HTTPException(404, f"Nenhum trade para run_id={run_id}")
    run = storage.get_run(run_id)
    initial = req.initial_equity or (run.get("deposit") if run else 10_000.0) or 10_000.0

    parquet_path = req.parquet_path
    if not parquet_path:
        parquet_path = run.get("ticks_parquet_path") if run else None
    if not parquet_path:
        raise HTTPException(
            400,
            "Nenhum arquivo de ticks disponível. "
            "Use POST /runs/{run_id}/fetch-ticks para baixar do MT5 automaticamente.",
        )

    try:
        return tmc.run_all_tick_mc(
            trades,
            parquet_path=parquet_path,
            initial=initial,
            runs=req.runs,
            jitter_seconds=req.jitter_seconds,
            worst_n_ticks=req.worst_n_ticks,
            block_ticks=req.block_ticks,
            seed=req.seed,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Erro no tick MC: {e}")


# ----------------------------------------------------------------- Time Breakdown
@router.get("/runs/{run_id}/time-breakdown")
def get_time_breakdown(run_id: str) -> dict[str, Any]:
    """Retorna breakdown temporal; usa cache do full_analysis se disponível."""
    storage.init_db()
    analysis = storage.load_analysis(run_id)
    if analysis and analysis.get("result", {}).get("time_breakdown"):
        return analysis["result"]["time_breakdown"]
    trades = storage.load_trades(run_id)
    if not trades:
        raise HTTPException(404, f"Nenhum trade para run_id={run_id}")
    return analytics.time_breakdown(trades)


@router.delete("/runs/{run_id}")
def delete_run(run_id: str) -> dict[str, Any]:
    storage.init_db()
    ok = storage.delete_run(run_id)
    if not ok:
        raise HTTPException(404, f"Run não encontrado: {run_id}")
    return {"deleted": run_id}
