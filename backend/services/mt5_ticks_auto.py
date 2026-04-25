"""Baixa ticks diretamente do terminal MT5 via pacote oficial `MetaTrader5`.

Elimina a necessidade do cliente exportar CSV manualmente. Os ticks são
salvos em parquet (zstd) no mesmo formato que `tick_converter.py` produz —
compatível com `tick_mae_mfe.py` e `tick_monte_carlo.py`.

Limitações:
- A lib MetaTrader5 só funciona com um terminal por vez por processo Python.
- Se o terminal está rodando em modo normal (GUI), `initialize(path=)` conecta
  nele. Caso contrário, o MT5 abre um terminal headless (window hide).
- O histórico de ticks depende do broker/FTMO; alguns só disponibilizam 2 anos.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


def _resolve_data_dir() -> Path:
    data_dir = os.environ.get("AURABACKTEST_DATA_DIR")
    if data_dir:
        return Path(data_dir)
    return Path(__file__).resolve().parent.parent / "data"


@dataclass
class FetchResult:
    symbol: str
    from_datetime: str
    to_datetime: str
    rows: int
    output_path: str
    elapsed_seconds: float


def fetch_ticks(
    terminal_exe: str | Path,
    symbol: str,
    from_datetime: datetime,
    to_datetime: datetime,
    output_dir: Path | None = None,
) -> FetchResult:
    """Baixa ticks do MT5 no range [from_datetime, to_datetime] e salva como parquet.

    Retorna metadados com caminho do arquivo pronto pra usar em MAE/MFE/MC ticks.
    """
    import time

    # Import tardio — MetaTrader5 só existe no Windows
    import MetaTrader5 as mt5
    import pandas as pd

    terminal_exe = Path(terminal_exe)
    if not terminal_exe.exists():
        raise FileNotFoundError(f"terminal64.exe não encontrado: {terminal_exe}")

    out_dir = Path(output_dir) if output_dir else (_resolve_data_dir() / "ticks" / symbol)
    out_dir.mkdir(parents=True, exist_ok=True)

    fname = (
        f"{symbol}_{from_datetime.strftime('%Y%m%d')}"
        f"_{to_datetime.strftime('%Y%m%d')}.parquet"
    )
    out_path = out_dir / fname

    start = time.time()
    if not mt5.initialize(path=str(terminal_exe)):
        err = mt5.last_error()
        raise RuntimeError(f"mt5.initialize falhou: {err}")

    try:
        ticks = mt5.copy_ticks_range(
            symbol, from_datetime, to_datetime, mt5.COPY_TICKS_ALL
        )
        if ticks is None:
            raise RuntimeError(f"copy_ticks_range retornou None: {mt5.last_error()}")
        if len(ticks) == 0:
            raise RuntimeError(
                f"Sem ticks para {symbol} em {from_datetime}..{to_datetime}. "
                "O broker pode não disponibilizar esse histórico."
            )

        df = pd.DataFrame(ticks)
        # Converte time (unix seconds) → datetime
        df["timestamp"] = pd.to_datetime(df["time"], unit="s", utc=True)
        # mid_price pra ser compatível com tick_mae_mfe (que procura esse campo)
        if "bid" in df.columns and "ask" in df.columns:
            df["mid_price"] = (df["bid"] + df["ask"]) / 2.0
        df["symbol"] = symbol

        df.to_parquet(out_path, compression="zstd", index=False)
        elapsed = time.time() - start

        return FetchResult(
            symbol=symbol,
            from_datetime=from_datetime.isoformat(),
            to_datetime=to_datetime.isoformat(),
            rows=len(df),
            output_path=str(out_path),
            elapsed_seconds=round(elapsed, 2),
        )
    finally:
        mt5.shutdown()


def as_dict(r: FetchResult) -> dict[str, Any]:
    return {
        "symbol": r.symbol,
        "from_datetime": r.from_datetime,
        "to_datetime": r.to_datetime,
        "rows": r.rows,
        "output_path": r.output_path,
        "elapsed_seconds": r.elapsed_seconds,
    }
