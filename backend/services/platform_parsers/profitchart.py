"""Parser de CSV exportado pelo ProfitChart Pro (Nelogica).

Fluxo do usuário:
1. No ProfitChart, abre Editor de Estratégias → Backtest
2. Aba "Operações"
3. Botão "Exportar Lista de Ordens CSV" (no menu inferior)

O ProfitChart historicamente exporta com:
- Encoding: UTF-8 com BOM ou CP1252
- Separador: `;` (padrão Excel pt-BR) — às vezes `,`
- Decimal: `,` (vírgula PT-BR)
- Datas: `dd/mm/yyyy hh:mm:ss` ou `dd/mm/yyyy`
- Colunas em PT-BR

Como o formato exato pode variar entre versões, o parser é DEFENSIVO:
detecta separador, encoding e mapeia colunas por sinônimos.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any

from .canonical import CanonicalTrade, _norm_side, _parse_datetime, _parse_float


# Sinônimos: chave canônica → lista de variantes case-insensitive aceitas
COLUMN_SYNONYMS: dict[str, list[str]] = {
    "time_in": [
        "data entrada", "data de entrada", "data abertura", "data de abertura",
        "abertura", "entrada", "hora entrada", "data/hora entrada",
        "data inicial", "início", "open time", "entry time", "open date",
        "data ent.", "data abr.",
    ],
    "time_out": [
        "data saída", "data de saída", "data saida", "data de saida",
        "data fechamento", "data de fechamento", "fechamento", "saída",
        "saida", "hora saída", "data/hora saída", "data final", "fim",
        "close time", "exit time", "close date", "data sai.", "data fec.",
    ],
    "side": [
        "lado", "tipo", "compra/venda", "operação", "direção", "side",
        "direction", "type", "buy/sell",
    ],
    "symbol": [
        "ativo", "papel", "ticker", "símbolo", "simbolo", "contrato",
        "instrumento", "symbol", "instrument",
    ],
    "volume": [
        "quantidade", "qtd", "qtde", "lote", "volume", "qty", "size",
        "contratos", "lots",
    ],
    "entry_price": [
        "preço entrada", "preco entrada", "preço de entrada", "preço abertura",
        "preço de abertura", "abertura", "open price", "entry price",
        "preço ent.", "p. entrada",
    ],
    "exit_price": [
        "preço saída", "preco saida", "preço de saída", "preço fechamento",
        "preço de fechamento", "fechamento", "close price", "exit price",
        "preço sai.", "p. saída",
    ],
    "profit": [
        "lucro", "resultado", "lucro/prejuízo", "lucro líquido", "líquido",
        "net", "p&l", "p/l", "profit", "net profit", "net p/l",
        "resultado líquido", "result.",
    ],
    "balance": [
        "saldo", "balanço", "balance", "saldo acumulado",
    ],
    "commission": [
        "comissão", "comissao", "taxa", "corretagem", "commission", "fee",
    ],
    "swap": [
        "swap", "rollover", "overnight",
    ],
    "comment": [
        "comentário", "comentario", "observação", "obs", "comment", "note",
    ],
}


def _detect_encoding(content: bytes) -> str:
    """Detecta encoding probável testando markers comuns no Brasil."""
    if content.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if content.startswith(b"\xff\xfe") or content.startswith(b"\xfe\xff"):
        return "utf-16"
    # Heurística: se decodifica em UTF-8 sem erro, usa
    try:
        content.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    return "cp1252"


def _detect_separator(text: str) -> str:
    """Conta ocorrências de candidatos a separador na primeira linha não-vazia."""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        counts = {sep: line.count(sep) for sep in [";", ",", "\t", "|"]}
        best = max(counts, key=counts.get)
        if counts[best] >= 3:  # pelo menos 4 colunas
            return best
        return ";"  # padrão Excel BR
    return ";"


def _normalize_header(h: str) -> str:
    """Lowercase, sem acentos, sem pontuação extra."""
    h = h.strip().lower()
    # Remove acentos básicos
    translations = str.maketrans("áàâãäéèêëíìîïóòôõöúùûüç", "aaaaaeeeeiiiiooooouuuuc")
    h = h.translate(translations)
    # Remove caracteres extras de cabeçalho como "(R$)", ":", etc
    for ch in [":", "(", ")", "[", "]", "$", "%"]:
        h = h.replace(ch, "")
    h = " ".join(h.split())  # collapse whitespace
    return h


def _match_column(header: str, synonyms: list[str]) -> bool:
    """True se `header` (já normalizado) corresponde a qualquer sinônimo."""
    h = _normalize_header(header)
    for syn in synonyms:
        sn = _normalize_header(syn)
        if h == sn:
            return True
        # Match parcial se header começa com sinônimo (ex: "data entrada (utc)" → "data entrada")
        if h.startswith(sn + " ") or sn in h.split():
            return True
    return False


def _build_column_map(headers: list[str]) -> dict[str, int]:
    """Mapeia chave canônica → índice de coluna no CSV."""
    col_map: dict[str, int] = {}
    for canonical, synonyms in COLUMN_SYNONYMS.items():
        for i, h in enumerate(headers):
            if _match_column(h, synonyms) and canonical not in col_map:
                col_map[canonical] = i
                break
    return col_map


def _find_header_row(rows: list[list[str]], min_keywords: int = 3) -> int:
    """Encontra a linha do header (a primeira com 3+ colunas reconhecidas)."""
    all_synonyms = [s for syns in COLUMN_SYNONYMS.values() for s in syns]
    best_row = -1
    best_count = 0
    for i, row in enumerate(rows[:30]):  # busca nas primeiras 30 linhas
        matches = sum(
            1 for cell in row if any(_match_column(cell, [s]) for s in all_synonyms)
        )
        if matches > best_count:
            best_count = matches
            best_row = i
        if matches >= min_keywords + 2:
            return i
    return best_row if best_count >= min_keywords else -1


def parse_profitchart_csv(
    content: bytes | str, default_symbol: str = "UNKNOWN"
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Parseia bytes/string de CSV do ProfitChart.

    Returns:
        (trades, metadata): lista de trades canônicos + dict com {headers_detected,
        column_map, sep_used, encoding_used, rows_total, rows_parsed, skipped_reasons}
    """
    if isinstance(content, bytes):
        encoding = _detect_encoding(content)
        try:
            text = content.decode(encoding, errors="replace")
        except (LookupError, UnicodeDecodeError):
            text = content.decode("cp1252", errors="replace")
            encoding = "cp1252"
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
                "Cabeçalho não encontrado. O CSV precisa ter colunas como "
                "'Data Entrada', 'Data Saída', 'Lado', 'Lucro'. "
                "Verifique se você exportou pela aba 'Operações' do Backtest."
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
        if len(row) < max(column_map.values(), default=0) + 1:
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
            # ProfitChart às vezes exporta linha de sumário sem time_out
            skip("sem data de saída")
            continue
        if not time_in:
            # Trade sem entrada pode ser um sumário ou linha quebrada
            time_in = time_out  # fallback

        side = _norm_side(get("side"))
        if side is None:
            skip("lado indefinido")
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
        if time_in and time_out and isinstance(time_in, datetime) and isinstance(time_out, datetime):
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
        "platform": "profitchart",
        "headers_detected": headers,
        "column_map": column_map,
        "sep_used": sep,
        "encoding_used": encoding,
        "rows_total": len(data_rows),
        "rows_parsed": len(trades),
        "skipped_reasons": skipped_reasons,
    }
