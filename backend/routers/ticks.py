"""Rotas para inspeção e conversão de CSVs de ticks exportados do MT5."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from models.schemas import TickDatasetInfo
from services import mt5_ticks_auto
from services.tick_converter import convert_mt5_csv_to_parquet, inspect_mt5_csv


router = APIRouter(prefix="/ticks", tags=["ticks"])


class InspectRequest(BaseModel):
    path: str
    nrows: int = Field(default=10, ge=1, le=1000)


class InspectResponse(BaseModel):
    path: str
    size_bytes: int
    size_human: str
    columns: list[str]
    preview: list[dict[str, Any]]


class ConvertRequest(BaseModel):
    csv_path: str
    output_dir: str
    symbol: str
    partition: bool = False


def _human_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    x = float(n)
    for u in units:
        if x < 1024 or u == units[-1]:
            return f"{x:.2f} {u}"
        x /= 1024
    return f"{x:.2f} TB"


@router.post("/inspect", response_model=InspectResponse)
def inspect(req: InspectRequest) -> InspectResponse:
    path = Path(req.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Arquivo não encontrado: {path}")
    info = inspect_mt5_csv(path, nrows=req.nrows)
    return InspectResponse(
        path=info["path"],
        size_bytes=info["size_bytes"],
        size_human=_human_bytes(info["size_bytes"]),
        columns=info["columns"],
        preview=info["preview"],
    )


class AutoFetchRequest(BaseModel):
    terminal_exe: str
    symbol: str
    from_datetime: datetime
    to_datetime: datetime


@router.post("/auto-fetch")
def auto_fetch(req: AutoFetchRequest) -> dict[str, Any]:
    """Baixa ticks do MT5 automaticamente (sem CSV manual) e salva em parquet.

    Usa o pacote oficial MetaTrader5. O arquivo fica pronto pra usar em
    MAE/MFE com ticks reais e Monte Carlo com ticks.
    """
    try:
        result = mt5_ticks_auto.fetch_ticks(
            terminal_exe=req.terminal_exe,
            symbol=req.symbol,
            from_datetime=req.from_datetime,
            to_datetime=req.to_datetime,
        )
        return mt5_ticks_auto.as_dict(result)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/convert", response_model=TickDatasetInfo)
def convert(req: ConvertRequest) -> TickDatasetInfo:
    """Converte CSV de ticks MT5 para Parquet.

    ATENÇÃO: operação long-running (minutos para arquivos de múltiplos GB).
    Roda síncrona por enquanto — o frontend deve mostrar spinner ou mover
    para job assíncrono depois.
    """
    csv_path = Path(req.csv_path)
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail=f"CSV não encontrado: {csv_path}")
    return convert_mt5_csv_to_parquet(
        csv_path=csv_path,
        output_dir=req.output_dir,
        symbol=req.symbol,
        partition=req.partition,
    )
