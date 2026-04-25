"""Endpoints de otimização (MT5 Strategy Tester nativo — grid / genetic)."""
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
from services import mt5_runner, optimizer, storage


router = APIRouter(prefix="/optimization", tags=["optimization"])


class OptimizeRequest(BaseModel):
    terminal_exe: str
    data_folder: str
    ea_relative_path: str = Field(
        description="Relativo a MQL5/Experts sem extensão, ex: 'RPAlgo/Big-Small'"
    )
    ea_inputs_defaults: dict[str, Any]
    ranges: list[ParameterRange]
    symbol: str
    period: str = "M1"
    from_date: date
    to_date: date
    modeling: ModelingQuality = ModelingQuality.REAL_TICKS
    criterion: OptimizationCriterion = OptimizationCriterion.COMPLEX
    genetic: bool = True
    deposit: float = 10_000.0
    leverage: int = 100
    currency: str = "USD"
    timeout_seconds: int = Field(default=21_600, ge=60, le=86_400)


class OptimizeResponse(BaseModel):
    run_id: str
    set_file: str
    ini_file: str
    return_code: int
    elapsed_seconds: float
    report_xml_path: str | None
    num_passes: int
    best: dict[str, Any] | None
    top10: list[dict[str, Any]]
    stdout_tail: str = ""
    stderr_tail: str = ""


@router.post("/run", response_model=OptimizeResponse)
def run_optimization(req: OptimizeRequest) -> OptimizeResponse:
    """Dispara otimização no MT5. Bloqueia até o terminal encerrar (horas).

    Ao fim: parseia o XML de otimização, rankeia pelo critério e persiste no
    SQLite para consulta posterior.
    """
    if not req.ranges:
        raise HTTPException(400, "Otimização exige pelo menos um ParameterRange")
    if req.from_date >= req.to_date:
        raise HTTPException(
            400,
            f"Datas inválidas: from_date ({req.from_date}) precisa ser anterior a to_date ({req.to_date})",
        )

    terminal_exe = Path(req.terminal_exe)
    data_folder = Path(req.data_folder)
    if not terminal_exe.exists():
        raise HTTPException(404, f"terminal64.exe não encontrado: {terminal_exe}")
    if not data_folder.exists():
        raise HTTPException(404, f"data folder não encontrado: {data_folder}")

    env = mt5_runner.MT5Environment(terminal_exe=terminal_exe, data_folder=data_folder)
    result = optimizer.run_optimization(
        env=env,
        ea_relative_path=req.ea_relative_path,
        ea_inputs_defaults=req.ea_inputs_defaults,
        ranges=req.ranges,
        symbol=req.symbol,
        period=req.period,
        from_date=req.from_date,
        to_date=req.to_date,
        modeling=req.modeling,
        criterion=req.criterion,
        genetic=req.genetic,
        deposit=req.deposit,
        leverage=req.leverage,
        currency=req.currency,
        timeout_seconds=req.timeout_seconds,
    )

    # Persistência
    storage.init_db()
    storage.save_run(
        run_id=result.run_id,
        kind="optimization",
        ea_path=req.ea_relative_path,
        symbol=req.symbol,
        timeframe=req.period,
        from_date=req.from_date.isoformat(),
        to_date=req.to_date.isoformat(),
        deposit=req.deposit,
        report_path=str(result.report_xml_path) if result.report_xml_path else None,
        parameters={
            "ranges": [r.model_dump() for r in req.ranges],
            "criterion": req.criterion.value,
            "genetic": req.genetic,
        },
        metrics={"num_passes": len(result.passes)},
    )
    storage.save_optimization_passes(
        result.run_id,
        [(p.pass_idx, p.parameters, p.metrics) for p in result.passes],
    )

    def _pass_dict(p):
        return {
            "pass_idx": p.pass_idx,
            "parameters": p.parameters,
            "metrics": p.metrics,
        }

    return OptimizeResponse(
        run_id=result.run_id,
        set_file=str(result.set_file),
        ini_file=str(result.ini_file),
        return_code=result.return_code,
        elapsed_seconds=result.elapsed_seconds,
        report_xml_path=str(result.report_xml_path) if result.report_xml_path else None,
        num_passes=len(result.passes),
        best=_pass_dict(result.best_pass) if result.best_pass else None,
        top10=[_pass_dict(p) for p in result.passes[:10]],
        stdout_tail=result.stdout_tail,
        stderr_tail=result.stderr_tail,
    )


class ParseOptReportRequest(BaseModel):
    xml_path: str
    criterion: OptimizationCriterion = OptimizationCriterion.COMPLEX


@router.post("/parse")
def parse_opt_report(req: ParseOptReportRequest) -> dict[str, Any]:
    """Parseia um XML de otimização já existente (sem rodar o MT5)."""
    path = Path(req.xml_path)
    if not path.exists():
        raise HTTPException(404, f"XML não encontrado: {path}")
    passes = optimizer.parse_optimization_xml(path)
    ranked = optimizer.rank_passes(passes, req.criterion)
    return {
        "path": str(path),
        "num_passes": len(ranked),
        "top10": [
            {"pass_idx": p.pass_idx, "parameters": p.parameters, "metrics": p.metrics}
            for p in ranked[:10]
        ],
    }


@router.get("/runs/{run_id}/passes")
def list_passes(run_id: str) -> list[dict[str, Any]]:
    storage.init_db()
    return storage.load_optimization_passes(run_id)
