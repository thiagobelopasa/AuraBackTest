"""Endpoints para integração com o MetaTrader 5."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from models.schemas import (
    ModelingQuality,
    OptimizationCriterion,
    ParameterRange,
)
from services import mt5_env, mt5_processes, mt5_report, mt5_runner, multi_symbol


router = APIRouter(prefix="/mt5", tags=["mt5"])


class InstallationInfo(BaseModel):
    label: str
    terminal_exe: str
    data_folder: str


@router.get("/installations", response_model=list[InstallationInfo])
def list_installations() -> list[InstallationInfo]:
    """Lista instalações MT5 detectadas no sistema (com label amigável)."""
    return [
        InstallationInfo(
            label=i.label,
            terminal_exe=str(i.terminal_exe),
            data_folder=str(i.data_folder),
        )
        for i in mt5_env.detect_installations()
    ]


class RunningMT5Response(BaseModel):
    running: list[dict[str, Any]]    # lista de MT5s atualmente rodando
    active: dict[str, Any] | None    # único ativo se só há um rodando


@router.get("/running", response_model=RunningMT5Response)
def list_running_mt5() -> RunningMT5Response:
    """Lista MT5s atualmente em execução. Se só um, retorna como 'active'.

    Frontend usa isso pra auto-selecionar MT5 sem o usuário precisar escolher
    quando há apenas uma instância rodando (caso comum).
    """
    running = mt5_processes.detect_running_mt5()
    return RunningMT5Response(
        running=[mt5_processes.as_dict(r) for r in running],
        active=mt5_processes.as_dict(running[0]) if len(running) == 1 else None,
    )


class ExpertInfo(BaseModel):
    relative_path: str           # ex: 'RPAlgo/Big-Small'
    absolute_path: str
    extension: str
    size_bytes: int
    has_source: bool


@router.get("/experts", response_model=list[ExpertInfo])
def list_experts(data_folder: str, include_compiled: bool = True) -> list[ExpertInfo]:
    """Lista todos os EAs (.mq5 e/ou .ex5) da pasta MQL5/Experts de uma instalação."""
    folder = Path(data_folder)
    if not folder.exists():
        raise HTTPException(404, f"data_folder não encontrado: {folder}")
    return [
        ExpertInfo(
            relative_path=e.relative_path,
            absolute_path=str(e.absolute_path),
            extension=e.extension,
            size_bytes=e.size_bytes,
            has_source=e.has_source,
        )
        for e in mt5_env.list_experts(folder, include_compiled=include_compiled)
    ]


class RunSingleRequest(BaseModel):
    terminal_exe: str
    data_folder: str
    ea_relative_path: str = Field(
        description="Caminho relativo a MQL5/Experts sem extensão, ex: 'RPAlgo/Big-Small'"
    )
    ea_inputs_defaults: dict[str, Any]
    ranges: list[ParameterRange] = []
    symbol: str
    period: str = "M1"
    from_date: date
    to_date: date
    modeling: ModelingQuality = ModelingQuality.REAL_TICKS
    criterion: OptimizationCriterion = OptimizationCriterion.COMPLEX
    deposit: float = 10_000.0
    leverage: int = 100
    currency: str = "USD"
    timeout_seconds: int = Field(default=3600, ge=60, le=86400)


class RunSingleResponse(BaseModel):
    run_id: str
    set_file: str
    ini_file: str
    return_code: int
    elapsed_seconds: float
    report_path: str | None
    stdout_tail: str
    stderr_tail: str


@router.post("/run-single", response_model=RunSingleResponse)
def run_single(req: RunSingleRequest) -> RunSingleResponse:
    """Executa UM backtest no MT5. Bloqueia até o terminal encerrar.

    Abre o terminal MT5 na tela durante a execução (modo GUI é o default
    do Strategy Tester). Para operação headless, precisamos de MT5 Portable.
    """
    terminal_exe = Path(req.terminal_exe)
    data_folder = Path(req.data_folder)
    if not terminal_exe.exists():
        raise HTTPException(404, f"terminal64.exe não encontrado: {terminal_exe}")
    if not data_folder.exists():
        raise HTTPException(404, f"data folder não encontrado: {data_folder}")

    env = mt5_runner.MT5Environment(
        terminal_exe=terminal_exe, data_folder=data_folder
    )
    result = mt5_runner.prepare_and_run(
        env=env,
        ea_relative_path=req.ea_relative_path,
        ea_inputs_defaults=req.ea_inputs_defaults,
        ranges=req.ranges,
        symbol=req.symbol,
        period=req.period,
        from_date=req.from_date,
        to_date=req.to_date,
        modeling=req.modeling,
        optimization=0,
        criterion=req.criterion,
        deposit=req.deposit,
        leverage=req.leverage,
        currency=req.currency,
        timeout_seconds=req.timeout_seconds,
    )
    return RunSingleResponse(
        run_id=result.run_id,
        set_file=str(result.set_file),
        ini_file=str(result.ini_file),
        return_code=result.return_code,
        elapsed_seconds=result.elapsed_seconds,
        report_path=str(result.report_path) if result.report_path else None,
        stdout_tail=result.stdout_tail,
        stderr_tail=result.stderr_tail,
    )


class ParseReportRequest(BaseModel):
    report_path: str


@router.post("/report/parse")
def parse_report(req: ParseReportRequest) -> dict[str, Any]:
    """Parsea um relatório HTM gerado pelo Strategy Tester do MT5."""
    path = Path(req.report_path)
    if not path.exists():
        raise HTTPException(404, f"Report não encontrado: {path}")
    parsed = mt5_report.parse_report_htm(path)
    deals = mt5_report.extract_deals_htm(path)
    return {
        "path": str(path),
        "metrics": parsed["metrics"],
        "num_deals": len(deals),
        "deals_preview": deals[:5],
        "raw_labels": list(parsed["raw"].keys())[:30],
    }


class MultiSymbolJobSpec(BaseModel):
    symbol: str
    period: str = "M1"
    from_date: date
    to_date: date


class MultiSymbolRequest(BaseModel):
    terminal_exe: str
    data_folder: str
    ea_relative_path: str
    ea_inputs_defaults: dict[str, Any]
    jobs: list[MultiSymbolJobSpec]
    deposit: float = 10_000.0
    leverage: int = 100
    currency: str = "USD"
    label_prefix: str = "multi"


@router.post("/multi-symbol")
def run_multi_symbol_endpoint(req: MultiSymbolRequest) -> list[dict[str, Any]]:
    """Executa o mesmo EA em múltiplos (símbolo, período, data range).

    Retorna lista com {symbol, run_id, ok, metrics} — cada item bem-sucedido
    aparece no Histórico como run normal, pronto pra análise com MC/MAE etc.
    ATENÇÃO: sequencial, cada backtest pode levar minutos — o endpoint bloqueia
    até terminar todos.
    """
    if not req.jobs:
        raise HTTPException(400, "Passe pelo menos 1 job")
    terminal = Path(req.terminal_exe)
    data_folder = Path(req.data_folder)
    if not terminal.exists():
        raise HTTPException(404, f"terminal64.exe não encontrado: {terminal}")
    if not data_folder.exists():
        raise HTTPException(404, f"data_folder não encontrado: {data_folder}")

    jobs = [multi_symbol.SymbolJob(
        symbol=j.symbol, period=j.period,
        from_date=j.from_date, to_date=j.to_date,
    ) for j in req.jobs]

    results = multi_symbol.run_multi_symbol(
        terminal_exe=terminal, data_folder=data_folder,
        ea_relative_path=req.ea_relative_path,
        ea_inputs_defaults=req.ea_inputs_defaults,
        jobs=jobs,
        deposit=req.deposit, leverage=req.leverage, currency=req.currency,
        label_prefix=req.label_prefix,
    )
    return [multi_symbol.as_dict(r) for r in results]
