"""Conversor de CSV de ticks (export MT5) para Parquet.

Formato do CSV MT5 (tab-separated):
    <DATE>  <TIME>  <BID>  <ASK>  <LAST>  <VOLUME>  <FLAGS>
    2024.01.02  01:05:00.071  16828.50  16830.70        6

Saída: um único arquivo Parquet comprimido com zstd, lido em streaming via
Polars — arquivos de múltiplos GB cabem em RAM normal.

Para datasets muito grandes, o Parquet pode ser particionado por ano/mês
passando `partition=True` (escreve um diretório em vez de um arquivo único).
"""
from __future__ import annotations

from pathlib import Path

import polars as pl

from models.schemas import TickDatasetInfo


EXPECTED_COLUMNS = ["<DATE>", "<TIME>", "<BID>", "<ASK>", "<LAST>", "<VOLUME>", "<FLAGS>"]


def inspect_mt5_csv(csv_path: str | Path, nrows: int = 10) -> dict:
    """Inspeção rápida: cabeçalho, tamanho em bytes e primeiras linhas.

    Usa leitura eager só do head — não carrega o arquivo inteiro.
    """
    csv_path = Path(csv_path)
    df = pl.read_csv(csv_path, separator="\t", n_rows=nrows, has_header=True)
    return {
        "path": str(csv_path),
        "size_bytes": csv_path.stat().st_size,
        "columns": df.columns,
        "preview": df.to_dicts(),
    }


def _build_lazy_frame(csv_path: Path, symbol: str) -> pl.LazyFrame:
    """Monta a pipeline lazy de normalização do CSV MT5."""
    return (
        pl.scan_csv(
            csv_path,
            separator="\t",
            has_header=True,
            null_values=["", " "],
            schema_overrides={
                "<DATE>": pl.Utf8,
                "<TIME>": pl.Utf8,
                "<BID>": pl.Float64,
                "<ASK>": pl.Float64,
                "<LAST>": pl.Float64,
                "<VOLUME>": pl.Int64,
                "<FLAGS>": pl.Int32,
            },
        )
        .rename(
            {
                "<DATE>": "date_str",
                "<TIME>": "time_str",
                "<BID>": "bid",
                "<ASK>": "ask",
                "<LAST>": "last",
                "<VOLUME>": "volume",
                "<FLAGS>": "flags",
            }
        )
        .with_columns(
            pl.concat_str(["date_str", "time_str"], separator=" ")
            .str.strptime(
                pl.Datetime("ms"),
                format="%Y.%m.%d %H:%M:%S%.3f",
                strict=False,
            )
            .alias("timestamp"),
            pl.lit(symbol).alias("symbol"),
        )
        .with_columns(
            pl.col("timestamp").dt.year().alias("year"),
            pl.col("timestamp").dt.month().alias("month"),
        )
        .select(
            [
                "timestamp",
                "symbol",
                "bid",
                "ask",
                "last",
                "volume",
                "flags",
                "year",
                "month",
            ]
        )
        .drop_nulls(subset=["timestamp"])
    )


def convert_mt5_csv_to_parquet(
    csv_path: str | Path,
    output_dir: str | Path,
    symbol: str,
    partition: bool = False,
) -> TickDatasetInfo:
    """Converte o CSV para Parquet zstd em streaming.

    Se `partition=True`, escreve em `output_dir/year=YYYY/month=MM/part-*.parquet`.
    Caso contrário, um único `output_dir/ticks.parquet`.
    """
    csv_path = Path(csv_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    lf = _build_lazy_frame(csv_path, symbol)

    if partition:
        # Polars >=1.10 suporta sink_parquet com partition_by via pyarrow
        out_target = output_dir
        lf.sink_parquet(
            out_target,
            compression="zstd",
            compression_level=3,
            partition_by=["year", "month"],
        )
        scan_target: str | Path = output_dir / "**" / "*.parquet"
    else:
        out_target = output_dir / "ticks.parquet"
        lf.sink_parquet(
            out_target,
            compression="zstd",
            compression_level=3,
        )
        scan_target = out_target

    # Metadata cheap: collect só o agregado
    meta = (
        pl.scan_parquet(scan_target)
        .select(
            pl.col("timestamp").min().alias("first"),
            pl.col("timestamp").max().alias("last"),
            pl.len().alias("total"),
        )
        .collect()
    )

    total_bytes = (
        sum(p.stat().st_size for p in output_dir.rglob("*.parquet"))
        if partition
        else out_target.stat().st_size
    )

    return TickDatasetInfo(
        source_csv=str(csv_path),
        parquet_dir=str(output_dir),
        symbol=symbol,
        first_timestamp=meta["first"][0],
        last_timestamp=meta["last"][0],
        total_ticks=int(meta["total"][0]),
        size_bytes_parquet=total_bytes,
    )
