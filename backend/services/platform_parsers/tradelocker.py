"""Parser de CSV exportado pelo TradeLocker.

Fluxo do usuário:
1. No TradeLocker (desktop ou web), abrir "Accounts" → "View account"
2. Selecionar período em "Trade History"
3. Clicar no ícone "⋮" (3 pontos) ao lado do número da conta
4. "Export account History"

TradeLocker exporta em CSV padrão internacional:
- Encoding: UTF-8
- Separador: `,` (vírgula)
- Decimal: `.` (ponto)
- Datas: ISO `YYYY-MM-DD HH:MM:SS` ou formato US `MM/DD/YYYY HH:MM:SS`
- Colunas em inglês

Como exportações podem variar entre brokers usando TradeLocker, o parser é
defensivo (mesmos sinônimos que o ProfitChart, em inglês).
"""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any

from .canonical import CanonicalTrade, _norm_side, _parse_datetime, _parse_float


COLUMN_SYNONYMS: dict[str, list[str]] = {
    "time_in": [
        "open time", "entry time", "open date", "opened",
        "open datetime", "creation time", "entry datetime",
        "open", "opened at",
    ],
    "time_out": [
        "close time", "exit time", "close date", "closed",
        "close datetime", "exit datetime", "filled time", "execution time",
        "closed at", "close",
    ],
    "side": [
        "side", "type", "direction", "buy/sell", "order side", "position side",
    ],
    "symbol": [
        "instrument", "symbol", "ticker", "asset", "pair", "market",
        "instrument name", "trading symbol",
    ],
    "volume": [
        "quantity", "qty", "volume", "size", "lots", "lot size", "amount",
        "units", "position size",
    ],
    "entry_price": [
        "open price", "entry price", "fill price", "open rate",
        "entry rate", "opening price",
    ],
    "exit_price": [
        "close price", "exit price", "close rate", "exit rate",
        "closing price", "fill price exit",
    ],
    "profit": [
        "p&l", "p/l", "profit", "net p/l", "net profit", "pnl",
        "realized p&l", "realized pnl", "gross profit", "result",
    ],
    "balance": [
        "balance", "running balance", "account balance",
    ],
    "commission": [
        "commission", "fee", "fees", "broker fee", "commissions",
    ],
    "swap": [
        "swap", "rollover", "overnight fee", "interest",
    ],
    "comment": [
        "comment", "note", "notes", "memo", "description",
    ],
}


def _detect_encoding(content: bytes) -> str:
    if content.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if content.startswith(b"\xff\xfe") or content.startswith(b"\xfe\xff"):
        return "utf-16"
    try:
        content.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "cp1252"


def _detect_separator(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        counts = {sep: line.count(sep) for sep in [",", ";", "\t", "|"]}
        best = max(counts, key=counts.get)
        if counts[best] >= 3:
            return best
        return ","
    return ","


def _normalize_header(h: str) -> str:
    h = h.strip().lower()
    for ch in [":", "(", ")", "[", "]", "$", "%", "*"]:
        h = h.replace(ch, "")
    h = " ".join(h.split())
    return h


def _match_column(header: str, synonyms: list[str]) -> bool:
    h = _normalize_header(header)
    for syn in synonyms:
        sn = _normalize_header(syn)
        if h == sn:
            return True
        if h.startswith(sn + " ") or sn in h.split():
            return True
    return False


def _build_column_map(headers: list[str]) -> dict[str, int]:
    col_map: dict[str, int] = {}
    for canonical, synonyms in COLUMN_SYNONYMS.items():
        for i, h in enumerate(headers):
            if _match_column(h, synonyms) and canonical not in col_map:
                col_map[canonical] = i
                break
    return col_map


def _find_header_row(rows: list[list[str]], min_keywords: int = 3) -> int:
    all_synonyms = [s for syns in COLUMN_SYNONYMS.values() for s in syns]
    best_row = -1
    best_count = 0
    for i, row in enumerate(rows[:30]):
        matches = sum(
            1 for cell in row if any(_match_column(cell, [s]) for s in all_synonyms)
        )
        if matches > best_count:
            best_count = matches
            best_row = i
        if matches >= min_keywords + 2:
            return i
    return best_row if best_count >= min_keywords else -1


def parse_tradelocker_csv(
    content: bytes | str, default_symbol: str = "UNKNOWN"
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Parseia CSV exportado pelo TradeLocker (Export account History).

    Returns: (trades, metadata)
    """
    if isinstance(content, bytes):
        encoding = _detect_encoding(content)
        try:
            text = content.decode(encoding, errors="replace")
        except (LookupError, UnicodeDecodeError):
            text = content.decode("utf-8", errors="replace")
            encoding = "utf-8"
    else:
        text = content
        encoding = "utf-8"

    sep = _detect_separator(text)
    reader = csv.reader(io.StringIO(text), delimiter=sep)
    all_rows: list[list[str]] = [row for row in reader if row]

    if not all_rows:
        return [], {
            "headers_detected": [],
            "column_map": {},
            "sep_used": sep,
            "encoding_used": encoding,
            "rows_total": 0,
            "rows_parsed": 0,
            "error": "Arquivo vazio",
        }

    header_idx = _find_header_row(all_rows)
    if header_idx < 0:
        return [], {
            "headers_detected": all_rows[0] if all_rows else [],
            "column_map": {},
            "sep_used": sep,
            "encoding_used": encoding,
            "rows_total": len(all_rows),
            "rows_parsed": 0,
            "error": (
                "Cabeçalho não encontrado. Esperamos colunas como "
                "'Open Time', 'Close Time', 'Side', 'P&L', 'Instrument'. "
                "Verifique se o arquivo é o 'Export account History' do TradeLocker "
                "(menu 3 pontos no Trade History)."
            ),
        }

    headers = all_rows[header_idx]
    column_map = _build_column_map(headers)
    data_rows = all_rows[header_idx + 1:]

    trades: list[dict[str, Any]] = []
    skipped_reasons: dict[str, int] = {}

    def skip(reason: str):
        skipped_reasons[reason] = skipped_reasons.get(reason, 0) + 1

    for row in data_rows:
        if not any(cell.strip() for cell in row):
            skip("linha vazia")
            continue
        if column_map and len(row) < max(column_map.values()) + 1:
            skip("colunas insuficientes")
            continue

        def get(key: str) -> str | None:
            idx = column_map.get(key)
            if idx is None or idx >= len(row):
                return None
            return row[idx].strip() if row[idx] else None

        time_in = _parse_datetime(get("time_in"))
        time_out = _parse_datetime(get("time_out"))
        if not time_out:
            skip("sem close time")
            continue
        if not time_in:
            time_in = time_out

        side = _norm_side(get("side"))
        if side is None:
            skip("side indefinido")
            continue

        profit = _parse_float(get("profit"))
        if profit is None:
            skip("profit não-numérico")
            continue

        volume = _parse_float(get("volume")) or 1.0
        entry_price = _parse_float(get("entry_price")) or 0.0
        exit_price = _parse_float(get("exit_price")) or 0.0

        symbol = get("symbol") or default_symbol
        balance = _parse_float(get("balance"))
        commission = _parse_float(get("commission"))
        swap = _parse_float(get("swap"))
        comment = get("comment")

        duration_sec = None
        if isinstance(time_in, datetime) and isinstance(time_out, datetime):
            duration_sec = max(0, int((time_out - time_in).total_seconds()))

        trades.append(CanonicalTrade(
            time_in=time_in,
            time_out=time_out,
            symbol=symbol,
            side=side,
            volume=volume,
            entry_price=entry_price,
            exit_price=exit_price,
            profit=profit,
            balance=balance,
            duration_sec=duration_sec,
            commission=commission,
            swap=swap,
            comment=comment,
        ).to_dict())

    return trades, {
        "platform": "tradelocker",
        "headers_detected": headers,
        "column_map": column_map,
        "sep_used": sep,
        "encoding_used": encoding,
        "rows_total": len(data_rows),
        "rows_parsed": len(trades),
        "skipped_reasons": skipped_reasons,
    }
