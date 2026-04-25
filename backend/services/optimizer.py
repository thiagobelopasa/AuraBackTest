"""Wrapper para o otimizador nativo do MT5 Strategy Tester.

No Build 5800 o Strategy Tester grava — em runs de otimização — um arquivo
`<report>.xml` no `data_folder` raiz com UM row por combinação testada (pass).
O arquivo é SpreadsheetML (formato Office 2003): namespace
`urn:schemas-microsoft-com:office:spreadsheet`.

Esse módulo:
    1. Gera .set com ranges + .ini com Optimization=1|2|3
    2. Chama mt5_runner.run_strategy_tester
    3. Parseia o report de otimização (SpreadsheetML XML) → lista de passes
    4. Rankeia por critério configurável

Critérios de ranking: usa a mesma chave que OptimizationCriterion, mas resolvido
contra os nomes de coluna reais do XML (que variam levemente em pt-BR/en).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from models.schemas import (
    ModelingQuality,
    OptimizationCriterion,
    ParameterRange,
)
from services import mt5_runner


# Modo de otimização do MT5 Strategy Tester:
#   0 = sem otimização (single run)
#   1 = slow / complete (grid exaustivo)
#   2 = fast (genetic algorithm)
#   3 = all symbols selected
_OPT_MODE_SLOW = 1
_OPT_MODE_GENETIC = 2


# Mapeia coluna do report de otimização → chave canônica
# Nomes observados em runs reais pt-BR / en-US
_OPT_COL_MAP: dict[str, str] = {
    "result": "score",
    "resultado": "score",
    "pass": "pass_idx",
    "profit": "net_profit",
    "lucro": "net_profit",
    "expected payoff": "expected_payoff",
    "expectativa matemática": "expected_payoff",
    "profit factor": "profit_factor",
    "fator de lucro": "profit_factor",
    "recovery factor": "recovery_factor",
    "fator de recuperação": "recovery_factor",
    "sharpe ratio": "sharpe_ratio",
    "razão de sharpe": "sharpe_ratio",
    "custom": "custom_score",
    "equity dd %": "equity_dd_pct",
    "rebaixamento de capital %": "equity_dd_pct",
    "trades": "total_trades",
    "negociações": "total_trades",
    "negociacoes": "total_trades",
}


_CRITERION_TO_KEY: dict[OptimizationCriterion, str] = {
    OptimizationCriterion.BALANCE: "net_profit",
    OptimizationCriterion.PROFIT_FACTOR: "profit_factor",
    OptimizationCriterion.EXPECTED_PAYOFF: "expected_payoff",
    OptimizationCriterion.DRAWDOWN: "equity_dd_pct",  # menor é melhor
    OptimizationCriterion.RECOVERY: "recovery_factor",
    OptimizationCriterion.SHARPE: "sharpe_ratio",
    OptimizationCriterion.COMPLEX: "score",
}


@dataclass
class OptimizationPass:
    """Uma combinação de parâmetros testada pelo otimizador."""
    pass_idx: int
    parameters: dict[str, Any]
    metrics: dict[str, float]


@dataclass
class OptimizationResult:
    run_id: str
    set_file: Path
    ini_file: Path
    return_code: int
    elapsed_seconds: float
    report_xml_path: Path | None
    passes: list[OptimizationPass] = field(default_factory=list)
    best_pass: OptimizationPass | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""


# --------------------------------------------------------- Parser SpreadsheetML
_SSML_NS = "{urn:schemas-microsoft-com:office:spreadsheet}"


def _load_xml_text(path: Path) -> str:
    """Tenta encodings comuns do MT5 — auto-gerado é UTF-16 LE, export manual
    ('Open XML') pode vir em UTF-8 ou UTF-16 sem BOM."""
    raw = path.read_bytes()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16", errors="ignore")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig", errors="ignore")
    # Heurística: muitos NULs → UTF-16 LE sem BOM
    if raw[:200].count(b"\x00") > 20:
        return raw.decode("utf-16-le", errors="ignore")
    return raw.decode("utf-8", errors="ignore")


def _row_cells(row: ET.Element) -> list[str]:
    """Lê células de uma <Row>, respeitando ss:Index (células puladas)."""
    out: list[str] = []
    expected_idx = 1
    for cell in row.findall(f"{_SSML_NS}Cell"):
        idx_attr = cell.get(f"{_SSML_NS}Index")
        if idx_attr is not None:
            target = int(idx_attr)
            while expected_idx < target:
                out.append("")
                expected_idx += 1
        data = cell.find(f"{_SSML_NS}Data")
        out.append(data.text if (data is not None and data.text is not None) else "")
        expected_idx += 1
    return out


def _to_number(s: str) -> float | None:
    if not s:
        return None
    cleaned = s.replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_optimization_xml(xml_path: Path) -> list[OptimizationPass]:
    """Parseia report de otimização SpreadsheetML → lista de passes.

    Cada row da primeira <Table> com mais de 1 data-row é um pass. A PRIMEIRA
    row é header. Colunas desconhecidas viram `parameters[<nome>]`, conhecidas
    viram `metrics[<canonical>]`.
    """
    text = _load_xml_text(xml_path)
    root = ET.fromstring(text)
    # Namespace-agnóstico: busca primeiro <Table> em qualquer profundidade
    table = None
    for elem in root.iter():
        if elem.tag == f"{_SSML_NS}Table":
            table = elem
            break
    if table is None:
        return []

    rows = table.findall(f"{_SSML_NS}Row")
    if len(rows) < 2:
        return []

    header = [h.strip().lower() for h in _row_cells(rows[0])]
    passes: list[OptimizationPass] = []
    for r_idx, row in enumerate(rows[1:]):
        cells = _row_cells(row)
        if not any(c.strip() for c in cells):
            continue
        metrics: dict[str, float] = {}
        parameters: dict[str, Any] = {}
        pass_idx = r_idx
        for i, label in enumerate(header):
            if i >= len(cells):
                break
            value = cells[i]
            canonical = _OPT_COL_MAP.get(label)
            if canonical == "pass_idx":
                n = _to_number(value)
                if n is not None:
                    pass_idx = int(n)
                continue
            if canonical:
                n = _to_number(value)
                if n is not None:
                    metrics[canonical] = n
            else:
                # coluna não mapeada = parâmetro do EA
                n = _to_number(value)
                parameters[label] = n if n is not None else value
        passes.append(
            OptimizationPass(pass_idx=pass_idx, parameters=parameters, metrics=metrics)
        )
    return passes


def rank_passes(
    passes: list[OptimizationPass],
    criterion: OptimizationCriterion,
) -> list[OptimizationPass]:
    """Ordena passes pelo critério, do melhor pro pior.

    Drawdown é minimização (menor = melhor); o resto é maximização.
    """
    key = _CRITERION_TO_KEY[criterion]
    reverse = criterion != OptimizationCriterion.DRAWDOWN

    def _score(p: OptimizationPass) -> float:
        return p.metrics.get(key, float("-inf") if reverse else float("inf"))

    return sorted(passes, key=_score, reverse=reverse)


# --------------------------------------------------------- Localizador do XML
def _locate_opt_xml(env: mt5_runner.MT5Environment, report_name: str) -> Path | None:
    candidates = [
        env.data_folder / f"{report_name}.xml",
        env.data_folder / "MQL5" / "Files" / f"{report_name}.xml",
        env.tester_dir / f"{report_name}.xml",
    ]
    return next((p for p in candidates if p.exists()), None)


# -------------------------------------------------------------- Orquestração
def run_optimization(
    env: mt5_runner.MT5Environment,
    ea_relative_path: str,
    ea_inputs_defaults: dict[str, Any],
    ranges: list[ParameterRange],
    symbol: str,
    period: str,
    from_date: date,
    to_date: date,
    modeling: ModelingQuality = ModelingQuality.REAL_TICKS,
    criterion: OptimizationCriterion = OptimizationCriterion.COMPLEX,
    genetic: bool = True,
    deposit: float = 10_000.0,
    leverage: int = 100,
    currency: str = "USD",
    timeout_seconds: int = 21_600,
) -> OptimizationResult:
    """Dispara otimização no MT5 e retorna passes rankeados.

    `genetic=True` usa GA (rápido, recomendado quando o espaço é grande).
    `genetic=False` força busca exaustiva (grid completo).
    """
    import time
    import uuid

    if not ranges:
        raise ValueError("Otimização exige pelo menos um ParameterRange")

    run_id = uuid.uuid4().hex[:8]
    report_name = f"aura_opt_{run_id}"

    config_dir = env.config_dir
    config_dir.mkdir(parents=True, exist_ok=True)
    set_file = config_dir / f"{report_name}.set"
    ini_file = config_dir / f"{report_name}.ini"

    mt5_runner.generate_set_file(ea_inputs_defaults, ranges, set_file)
    mt5_runner.generate_tester_ini(
        ea_relative_path=ea_relative_path,
        set_file=set_file,
        symbol=symbol,
        period=period,
        from_date=from_date,
        to_date=to_date,
        modeling=modeling,
        optimization=_OPT_MODE_GENETIC if genetic else _OPT_MODE_SLOW,
        criterion=criterion,
        report_name=report_name,
        deposit=deposit,
        leverage=leverage,
        currency=currency,
        output_ini=ini_file,
    )

    t0 = time.time()
    proc = mt5_runner.run_strategy_tester(env.terminal_exe, ini_file, timeout_seconds)
    elapsed = time.time() - t0

    xml_path = _locate_opt_xml(env, report_name)
    passes = parse_optimization_xml(xml_path) if xml_path else []
    ranked = rank_passes(passes, criterion) if passes else []

    return OptimizationResult(
        run_id=run_id,
        set_file=set_file,
        ini_file=ini_file,
        return_code=proc.returncode,
        elapsed_seconds=elapsed,
        report_xml_path=xml_path,
        passes=ranked,
        best_pass=ranked[0] if ranked else None,
        stdout_tail=(proc.stdout or "")[-1000:],
        stderr_tail=(proc.stderr or "")[-1000:],
    )
