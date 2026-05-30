"""Modelo canônico de trade — alinhado com o que o restante do sistema espera.

Todos os parsers de plataforma (MT5, ProfitChart, TradeLocker, …) devem produzir
listas de dicionários neste formato. Assim `analytics.full_analysis()` e o
resto do pipeline funcionam sem mudança.

Campos obrigatórios:
  time_in, time_out (datetime ISO), symbol, side ('buy'|'sell'),
  volume, entry_price, exit_price, profit
Campos opcionais:
  balance, duration_sec, commission, swap, comment
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CanonicalTrade:
    time_in: datetime
    time_out: datetime
    symbol: str
    side: str  # 'buy' | 'sell'
    volume: float
    entry_price: float
    exit_price: float
    profit: float
    balance: float | None = None
    duration_sec: int | None = None
    commission: float | None = None
    swap: float | None = None
    comment: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["time_in"] = self.time_in.isoformat() if isinstance(self.time_in, datetime) else self.time_in
        d["time_out"] = self.time_out.isoformat() if isinstance(self.time_out, datetime) else self.time_out
        return d


@dataclass
class ValidationReport:
    ok: bool
    n_trades: int
    n_errors: int
    n_warnings: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _norm_side(value: Any) -> str | None:
    """Normaliza qualquer representação de lado para 'buy' ou 'sell'."""
    if value is None:
        return None
    s = str(value).strip().lower()
    if not s:
        return None
    if s in {"buy", "long", "compra", "c", "b", "0", "+1", "bullish"}:
        return "buy"
    if s in {"sell", "short", "venda", "v", "s", "1", "-1", "bearish"}:
        return "sell"
    if "buy" in s or "long" in s or "compra" in s:
        return "buy"
    if "sell" in s or "short" in s or "venda" in s:
        return "sell"
    return None


def _parse_float(value: Any) -> float | None:
    """Converte string PT-BR ou EN para float. Aceita '1.234,56' e '1,234.56'."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s or s.lower() in {"nan", "null", "-"}:
        return None
    # Remove currency markers
    for marker in ["R$", "$", "USD", "BRL", "€", " "]:
        s = s.replace(marker, "")
    s = s.replace("(", "-").replace(")", "")
    # PT-BR: 1.234,56 → 1234.56
    if "," in s and "." in s:
        # Se vírgula vem depois do ponto, é PT-BR
        if s.rindex(",") > s.rindex("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        # Só vírgula: assume decimal PT-BR
        s = s.replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _parse_datetime(value: Any) -> datetime | None:
    """Tenta diversos formatos de data/hora comuns em CSVs de trading."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    if not s:
        return None
    # Tira timezone abreviação tipo "(UTC)" no fim
    for tz_marker in [" UTC", " GMT", "(UTC)", "(GMT)"]:
        if s.endswith(tz_marker):
            s = s[: -len(tz_marker)].strip()
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M",
        "%Y.%m.%d %H:%M:%S",
        "%Y.%m.%d %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y",
        "%Y-%m-%d",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    # Último recurso: ISO format genérico
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def validate_trades(trades: list[dict[str, Any]]) -> ValidationReport:
    """Valida lista de trades canônicos. Não modifica os trades."""
    errors: list[str] = []
    warnings: list[str] = []
    if not trades:
        return ValidationReport(False, 0, 1, 0, ["Lista de trades vazia"], [])

    required = {"time_in", "time_out", "side", "profit"}
    for i, t in enumerate(trades):
        missing = [k for k in required if k not in t or t[k] is None]
        if missing:
            errors.append(f"Trade #{i+1}: faltam campos {missing}")
            continue
        if t["side"] not in ("buy", "sell"):
            errors.append(f"Trade #{i+1}: side inválido '{t['side']}' (esperado buy/sell)")
        try:
            float(t["profit"])
        except (ValueError, TypeError):
            errors.append(f"Trade #{i+1}: profit não-numérico '{t.get('profit')}'")

    # Aviso se datas não estão crescentes (não é erro — pode ser ordenação diferente)
    prev = None
    out_of_order = 0
    for t in trades:
        ti = t.get("time_out")
        if not ti:
            continue
        if prev and isinstance(prev, str) and isinstance(ti, str) and ti < prev:
            out_of_order += 1
        prev = ti
    if out_of_order > 0:
        warnings.append(
            f"{out_of_order} trades fora de ordem cronológica — análise reordena automaticamente"
        )

    return ValidationReport(
        ok=len(errors) == 0,
        n_trades=len(trades),
        n_errors=len(errors),
        n_warnings=len(warnings),
        errors=errors[:20],  # limita pra não estourar tela
        warnings=warnings[:20],
    )
