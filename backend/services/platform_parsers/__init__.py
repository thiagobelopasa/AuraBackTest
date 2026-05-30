"""Registry de parsers de plataforma + auto-detect de formato."""
from __future__ import annotations

from typing import Any, Literal

from .canonical import CanonicalTrade, ValidationReport, validate_trades
from .profitchart import COLUMN_SYNONYMS as PROFIT_SYNONYMS
from .profitchart import parse_profitchart_csv
from .tradelocker import COLUMN_SYNONYMS as TL_SYNONYMS
from .tradelocker import parse_tradelocker_csv

Platform = Literal["mt5", "profitchart", "tradelocker", "auto"]


def detect_platform(content: bytes | str, filename: str = "") -> str:
    """Tenta detectar a plataforma pelo conteúdo + nome do arquivo.

    Heurística:
    - Se contém marcadores típicos do MT5 HTM (<title>Strategy Tester) → 'mt5'
    - Se cabeçalho tem palavras PT-BR distintas (data entrada/saída, lado, lucro) → 'profitchart'
    - Se cabeçalho tem palavras EN (open time, close time, p&l) → 'tradelocker'
    - Default: 'profitchart' (mais comum no público alvo BR)
    """
    if isinstance(content, bytes):
        try:
            sample = content[:5000].decode("utf-8", errors="ignore")
        except UnicodeDecodeError:
            sample = content[:5000].decode("cp1252", errors="ignore")
    else:
        sample = content[:5000]
    sample_low = sample.lower()

    name = (filename or "").lower()

    # MT5 HTM (já existe parser dedicado em mt5_report.py)
    if "<html" in sample_low and ("strategy tester" in sample_low or "metatrader" in sample_low):
        return "mt5"
    if name.endswith(".htm") or name.endswith(".html"):
        return "mt5"

    # Conta keywords PT-BR vs EN no head do arquivo
    pt_keywords = ["data entrada", "data saída", "data saida", "lucro", "compra", "venda", "lado", "operação", "operacao"]
    en_keywords = ["open time", "close time", "p&l", "p/l", "instrument", "filled", "long", "short"]

    pt_score = sum(1 for k in pt_keywords if k in sample_low)
    en_score = sum(1 for k in en_keywords if k in sample_low)

    # TradeLocker tem nome típico
    if "tradelocker" in name or "tl_" in name or "account_history" in name:
        return "tradelocker"
    if "profit" in name or "nelogica" in name or "backtest" in name and pt_score >= en_score:
        return "profitchart"

    if pt_score > en_score:
        return "profitchart"
    if en_score > pt_score:
        return "tradelocker"

    # Empate: default = profitchart (público alvo)
    return "profitchart"


def parse_by_platform(
    platform: str,
    content: bytes | str,
    default_symbol: str = "UNKNOWN",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Dispatcher: chama o parser correto baseado na plataforma."""
    if platform == "profitchart":
        return parse_profitchart_csv(content, default_symbol=default_symbol)
    if platform == "tradelocker":
        return parse_tradelocker_csv(content, default_symbol=default_symbol)
    raise ValueError(
        f"Plataforma '{platform}' não suportada por este parser. "
        f"Para MT5 use o pipeline existente (/analysis/ingest-upload)."
    )


__all__ = [
    "CanonicalTrade",
    "ValidationReport",
    "validate_trades",
    "detect_platform",
    "parse_by_platform",
    "parse_profitchart_csv",
    "parse_tradelocker_csv",
]
