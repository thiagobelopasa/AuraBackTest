"""Parser de reports do MT5 Strategy Tester (HTM UTF-16).

O layout do HTM (observado no Build 5800 pt-BR) tem dois padrões:

1. **Configuração inicial**: pares `label:valor` em 2 colunas por linha.
2. **Resultados agregados**: pares em 3 colunas por linha — (label1: val1) (label2: val2) (label3: val3).
   Minha primeira versão pegava só o último par, o que corrompia `net_profit`
   (aparecia positivo porque o "rebaixamento absoluto" fica na última posição).

Estratégia nova: iterar as células, detectando pares por `label terminado com ':'`
+ próxima célula não-vazia como valor. Captura todos os pares de uma linha.

A tabela de Transações (deals) é identificada pelo `<th>` com texto "Transações"
ou "Deals" — depois parseio as linhas de 12-13 colunas com timestamp/side/profit.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


# Mapeamento label → (chave canônica, tipo)
# tipo = "num" (extrai número) ou "str" (mantém valor textual)
_LABEL_MAP: dict[str, tuple[str, str]] = {
    # Lucros/perdas — num
    "lucro líquido total": ("net_profit", "num"),
    "total net profit": ("net_profit", "num"),
    "lucro bruto": ("gross_profit", "num"),
    "gross profit": ("gross_profit", "num"),
    "perda bruta": ("gross_loss", "num"),
    "gross loss": ("gross_loss", "num"),
    # Qualidade — num
    "fator de lucro": ("profit_factor", "num"),
    "profit factor": ("profit_factor", "num"),
    "expectativa matemática": ("expected_payoff", "num"),
    "expectativa matematica": ("expected_payoff", "num"),
    "retorno esperado (payoff)": ("expected_payoff", "num"),
    "expected payoff": ("expected_payoff", "num"),
    "fator de recuperação": ("recovery_factor", "num"),
    "fator de recuperacao": ("recovery_factor", "num"),
    "recovery factor": ("recovery_factor", "num"),
    "razão de sharpe": ("sharpe_ratio", "num"),
    "razao de sharpe": ("sharpe_ratio", "num"),
    "sharpe ratio": ("sharpe_ratio", "num"),
    "índice de sharpe": ("sharpe_ratio", "num"),
    "indice de sharpe": ("sharpe_ratio", "num"),
    "z-pontuação": ("z_score", "num"),
    "correlação lr": ("lr_correlation", "num"),
    "erro padrão lr": ("lr_std_error", "num"),
    "ahpr": ("ahpr", "num"),
    "ghpr": ("ghpr", "num"),
    # Drawdown — num
    "rebaixamento absoluto do saldo": ("balance_dd_abs", "num"),
    "rebaixamento absoluto do capital líquido": ("equity_dd_abs", "num"),
    "rebaixamento absoluto do capital": ("equity_dd_abs", "num"),
    "rebaixamento máximo do saldo": ("balance_dd_max", "num"),
    "rebaixamento maximo do saldo": ("balance_dd_max", "num"),
    "rebaixamento máximo do capital líquido": ("equity_dd_max", "num"),
    "rebaixamento máximo do capital": ("equity_dd_max", "num"),
    "rebaixamento maximo do capital": ("equity_dd_max", "num"),
    "rebaixamento relativo do saldo": ("balance_dd_pct", "num"),
    "rebaixamento relativo do capital líquido": ("equity_dd_pct", "num"),
    "rebaixamento relativo do capital": ("equity_dd_pct", "num"),
    "balance drawdown absolute": ("balance_dd_abs", "num"),
    "balance drawdown maximal": ("balance_dd_max", "num"),
    "balance drawdown relative": ("balance_dd_pct", "num"),
    "equity drawdown absolute": ("equity_dd_abs", "num"),
    "equity drawdown maximal": ("equity_dd_max", "num"),
    "equity drawdown relative": ("equity_dd_pct", "num"),
    # Trades — num
    "total de negócios": ("total_trades", "num"),
    "total de negocios": ("total_trades", "num"),
    "total trades": ("total_trades", "num"),
    "total de negociações": ("total_trades", "num"),
    "total de negociacoes": ("total_trades", "num"),
    "total deals": ("total_deals", "num"),
    "ofertas total": ("total_orders", "num"),
    "total orders": ("total_orders", "num"),
    "negociações com lucro (% of total)": ("win_trades_pct", "num"),
    "negociacoes com lucro (% of total)": ("win_trades_pct", "num"),
    "negociações com perda (% of total)": ("loss_trades_pct", "num"),
    "negociacoes com perda (% of total)": ("loss_trades_pct", "num"),
    "posições compradas (% de ganhos)": ("long_trades_pct", "num"),
    "posicoes compradas (% de ganhos)": ("long_trades_pct", "num"),
    "posições vendidas (% e ganhos)": ("short_trades_pct", "num"),
    "posicoes vendidas (% e ganhos)": ("short_trades_pct", "num"),
    "maior lucro da negociação": ("largest_win", "num"),
    "maior lucro da negociacao": ("largest_win", "num"),
    "maior perda na negociação": ("largest_loss", "num"),
    "maior perda na negociacao": ("largest_loss", "num"),
    "média lucro da negociação": ("avg_win", "num"),
    "media lucro da negociacao": ("avg_win", "num"),
    "média perda na negociação": ("avg_loss", "num"),
    "media perda na negociacao": ("avg_loss", "num"),
    "máximo ganhos consecutivos ($)": ("max_consec_wins_count", "num"),
    "maximo ganhos consecutivos ($)": ("max_consec_wins_count", "num"),
    "máximo perdas consecutivas ($)": ("max_consec_losses_count", "num"),
    "maximo perdas consecutivas ($)": ("max_consec_losses_count", "num"),
    "máxima lucro consecutivo (contagem)": ("max_consec_wins_money", "num"),
    "máxima perda consecutiva (contagem)": ("max_consec_losses_money", "num"),
    # Modelagem — num
    "barras": ("bars", "num"),
    "ticks": ("ticks_modeled", "num"),
    "qualidade da modelagem": ("modeling_quality_pct", "num"),
    # Depósito — num
    "depósito inicial": ("initial_deposit", "num"),
    "deposito inicial": ("initial_deposit", "num"),
    # Ambiente — str (não forçar número!)
    "qualidade do histórico": ("history_quality", "str"),
    "qualidade do historico": ("history_quality", "str"),
    "alavancagem": ("leverage", "str"),
    "moeda": ("currency", "str"),
    "empresa": ("broker", "str"),
    "ativo": ("symbol", "str"),
    "período": ("period_range", "str"),
    "periodo": ("period_range", "str"),
}


_NUMBER_RE = re.compile(r"-?\d[\d \u00a0,.]*")


def _parse_number(text: str) -> float | None:
    if not text:
        return None
    cleaned = text.replace("\u00a0", " ").strip()
    m = _NUMBER_RE.search(cleaned)
    if not m:
        return None
    s = m.group(0).replace(" ", "").replace(",", ".")
    if s.count(".") > 1:
        parts = s.split(".")
        s = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(s)
    except ValueError:
        return None


def _load_htm(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xff\xfe"):
        return raw.decode("utf-16-le", errors="ignore")
    if raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16-be", errors="ignore")
    for enc in ("utf-16", "utf-8", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def _extract_pairs_from_row(texts: list[str]) -> list[tuple[str, str]]:
    """Percorre células de uma linha e emite pares (label_com_':', próximo_valor).

    Suporta linhas tipo `[label1:, val1, label2:, val2, label3:, val3]`.
    """
    pairs: list[tuple[str, str]] = []
    i = 0
    while i < len(texts) - 1:
        t = texts[i].strip()
        if t.endswith(":") and len(t) > 1:
            # próxima célula NÃO vazia
            j = i + 1
            while j < len(texts) and not texts[j].strip():
                j += 1
            if j < len(texts):
                label = t.rstrip(":").strip().lower()
                value = texts[j].strip()
                if label and value:
                    pairs.append((label, value))
                i = j + 1
                continue
        i += 1
    return pairs


def _collect_label_value_pairs(soup: BeautifulSoup) -> dict[str, str]:
    raw: dict[str, str] = {}
    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"])
        texts = [c.get_text(" ", strip=True) for c in cells]
        for label, value in _extract_pairs_from_row(texts):
            if label not in raw:
                raw[label] = value
    return raw


def parse_report_htm(path: str | Path) -> dict[str, Any]:
    """Parsea relatório HTM do MT5. Retorna `metrics` (canônicas) + `raw` (todos pares)."""
    path = Path(path)
    html = _load_htm(path)
    soup = BeautifulSoup(html, "lxml")
    raw = _collect_label_value_pairs(soup)

    metrics: dict[str, Any] = {}
    for label, value in raw.items():
        entry = _LABEL_MAP.get(label)
        if not entry:
            continue
        canonical, value_type = entry
        if value_type == "num":
            num = _parse_number(value)
            if num is not None:
                metrics[canonical] = num
        else:
            metrics[canonical] = value

    return {"path": str(path), "metrics": metrics, "raw": raw}


# --------------------------------------------------------------------- Deals
_DEAL_HEADER_MARKERS = {"transações", "transacoes", "deals", "transactions"}


def _find_deals_header_row(soup: BeautifulSoup):
    """Retorna o <tr> que contém o <th>/<td> com 'Transações' ou equivalente."""
    for cell in soup.find_all(["th", "td"]):
        txt = cell.get_text(" ", strip=True).lower()
        if txt in _DEAL_HEADER_MARKERS:
            return cell.find_parent("tr")
    return None


def extract_deals_htm(path: str | Path) -> list[dict[str, Any]]:
    """Extrai lista de deals/trades a partir da tabela 'Transações' do HTM.

    O MT5 usa estas colunas (pt-BR): Hora, Deal, Símbolo, Tipo, Direção, Volume,
    Preço, Ordem, Comissão, Swap, Lucro, Saldo, Comentário.
    """
    path = Path(path)
    html = _load_htm(path)
    soup = BeautifulSoup(html, "lxml")

    marker_row = _find_deals_header_row(soup)
    if marker_row is None:
        return []

    # Header está na PRÓXIMA tr após o título de seção
    header_row = marker_row.find_next("tr")
    if header_row is None:
        return []
    header = [c.get_text(" ", strip=True).lower() for c in header_row.find_all(["td", "th"])]
    # fallback: se header tem poucos campos, usa cabeçalho canônico
    if len([h for h in header if h]) < 6:
        header = [
            "time", "deal", "symbol", "type", "direction",
            "volume", "price", "order", "commission", "swap",
            "profit", "balance", "comment",
        ]

    deals: list[dict[str, Any]] = []
    row = header_row.find_next("tr")
    while row is not None:
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        non_empty = [c for c in cells if c]
        if len(non_empty) < 5:
            # linha vazia ou linha de total → fim da tabela
            break
        item: dict[str, Any] = {}
        for i, cell in enumerate(cells):
            key = header[i] if i < len(header) else f"col{i}"
            item[key] = cell
        deals.append(item)
        row = row.find_next("tr")
    return deals


def deals_to_trades(deals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Converte lista de deals do MT5 em 'trades' (round-trips fechados).

    No MT5, um trade fechado vira 2 deals: um `in` (entrada) e um `out` (saída).
    O deal `out` carrega o P&L. Pareamos por `order` (mesmo ticket de ordem não
    serve — a entrada e a saída têm orders distintos). Na prática o MT5 registra
    o lucro no deal `out`, então cada deal `out` é um trade fechado.

    Retorna lista de dicts: `{time, symbol, side, volume, entry_price, exit_price,
    profit, balance, duration_sec}`.
    """
    from datetime import datetime

    def _f(v: Any) -> float:
        n = _parse_number(v) if isinstance(v, str) else v
        return float(n) if n is not None else 0.0

    def _dt(v: Any) -> datetime | None:
        if not isinstance(v, str):
            return None
        for fmt in ("%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M"):
            try:
                return datetime.strptime(v, fmt)
            except ValueError:
                continue
        return None

    def _get(d: dict, *keys: str) -> Any:
        """Busca valor em várias variantes de chave (acentuadas ou não)."""
        for k in keys:
            if k in d and d[k] not in ("", None):
                return d[k]
        return None

    time_keys = ("time", "hora", "horário", "horario")
    sym_keys = ("symbol", "símbolo", "simbolo", "ativo")
    dir_keys = ("direction", "direção", "direcao")
    type_keys = ("type", "tipo")
    price_keys = ("price", "preço", "preco")
    profit_keys = ("profit", "lucro")
    balance_keys = ("balance", "saldo")
    commission_keys = ("commission", "comissão", "comissao")
    swap_keys = ("swap",)

    trades: list[dict[str, Any]] = []
    last_entry: dict[str, Any] | None = None
    for d in deals:
        direction = str(_get(d, *dir_keys) or "").lower()
        if direction == "in":
            last_entry = d
            continue
        if direction == "out" and last_entry is not None:
            t_in = _dt(_get(last_entry, *time_keys))
            t_out = _dt(_get(d, *time_keys))
            duration = (t_out - t_in).total_seconds() if (t_in and t_out) else None
            gross_profit = _f(_get(d, *profit_keys))
            commission = _f(_get(last_entry, *commission_keys)) + _f(_get(d, *commission_keys))
            swap = _f(_get(last_entry, *swap_keys)) + _f(_get(d, *swap_keys))
            trades.append(
                {
                    "time_in": _get(last_entry, *time_keys),
                    "time_out": _get(d, *time_keys),
                    "symbol": _get(d, *sym_keys) or _get(last_entry, *sym_keys),
                    "side": str(_get(last_entry, *type_keys) or "").lower(),
                    "volume": _f(_get(d, "volume")),
                    "entry_price": _f(_get(last_entry, *price_keys)),
                    "exit_price": _f(_get(d, *price_keys)),
                    "profit": gross_profit + commission + swap,
                    "gross_profit": gross_profit,
                    "commission": commission,
                    "swap": swap,
                    "balance": _f(_get(d, *balance_keys)),
                    "duration_sec": duration,
                }
            )
            last_entry = None
    return trades
