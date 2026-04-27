"""Orquestrador do MT5 Strategy Tester via linha de comando.

Fluxo:
    1. Gera arquivo .set com parâmetros do EA (valor fixo ou range de otimização).
    2. Gera arquivo .ini com configurações do Tester (símbolo, período, datas).
    3. Dispara `terminal64.exe /config:<ini>` como subprocess síncrono.
       Com `ShutdownTerminal=1` no ini, o MT5 fecha ao fim do teste.
    4. Localiza e retorna o caminho do report gerado (parse é em mt5_report).

Arquivos de config do MT5 precisam estar em UTF-16 LE com BOM.
"""
from __future__ import annotations

import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from models.schemas import (
    ModelingQuality,
    OptimizationCriterion,
    ParameterRange,
)


# Mapeamento dos modos do Strategy Tester do MT5
_MODELING_INT = {
    ModelingQuality.REAL_TICKS: 4,      # "Every tick based on real ticks"
    ModelingQuality.GENERATED_TICKS: 0,  # "Every tick" (gerado)
    ModelingQuality.OHLC_1M: 1,          # "1 minute OHLC"
}

_CRITERION_INT = {
    OptimizationCriterion.BALANCE: 0,
    OptimizationCriterion.PROFIT_FACTOR: 1,
    OptimizationCriterion.EXPECTED_PAYOFF: 2,
    OptimizationCriterion.DRAWDOWN: 3,
    OptimizationCriterion.RECOVERY: 4,
    OptimizationCriterion.SHARPE: 5,
    OptimizationCriterion.COMPLEX: 6,    # Custom max / "Criterio complexo"
}


@dataclass
class MT5Environment:
    terminal_exe: Path
    data_folder: Path

    @property
    def experts_dir(self) -> Path:
        return self.data_folder / "MQL5" / "Experts"

    @property
    def tester_dir(self) -> Path:
        return self.data_folder / "Tester"

    @property
    def config_dir(self) -> Path:
        return self.data_folder / "config"

    @property
    def work_dir(self) -> Path:
        return self.data_folder / "MQL5" / "Files" / "aurabacktest"


def _fmt_date(d: date) -> str:
    return d.strftime("%Y.%m.%d")


def _write_utf16(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-16")


def _fmt_val(v: Any) -> str:
    """Formata valor para .set file. MT5 exige bool em minúsculo (true/false)."""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def generate_set_file(
    defaults: dict[str, Any],
    ranges: list[ParameterRange],
    output_path: Path,
) -> Path:
    """Gera arquivo .set de parâmetros do EA.

    Sem otimização:  `name=value`
    Com otimização:  `name=default||start||step||stop||Y`

    `fixed_value` em ParameterRange força valor fixo mesmo com range definido.
    """
    range_map = {r.name: r for r in ranges}
    lines: list[str] = []
    for name, default in defaults.items():
        r = range_map.get(name)
        if r is None:
            lines.append(f"{name}={_fmt_val(default)}")
        elif r.fixed_value is not None:
            lines.append(f"{name}={_fmt_val(r.fixed_value)}")
        else:
            lines.append(f"{name}={_fmt_val(default)}||{r.start}||{r.step}||{r.stop}||Y")
    _write_utf16(output_path, "\n".join(lines) + "\n")
    return output_path


def generate_tester_ini(
    ea_relative_path: str,
    set_file: Path,
    symbol: str,
    period: str,
    from_date: date,
    to_date: date,
    modeling: ModelingQuality,
    optimization: int,
    criterion: OptimizationCriterion,
    report_name: str,
    deposit: float,
    leverage: int,
    currency: str,
    output_ini: Path,
) -> Path:
    # MT5 no Windows exige backslash no Expert path (path relativo a MQL5\Experts).
    # Nosso listExperts devolve com '/', então normalizamos aqui.
    expert_path = ea_relative_path.replace("/", "\\")
    ini_lines = [
        "[Tester]",
        f"Expert={expert_path}",
        f"ExpertParameters={set_file.name}",
        f"Symbol={symbol}",
        f"Period={period}",
        f"Model={_MODELING_INT[modeling]}",
        f"Optimization={optimization}",
        f"OptimizationCriterion={_CRITERION_INT[criterion]}",
        f"FromDate={_fmt_date(from_date)}",
        f"ToDate={_fmt_date(to_date)}",
        "ForwardMode=0",
        f"Deposit={deposit:.2f}",
        f"Currency={currency}",
        "ProfitInPips=0",
        f"Leverage=1:{leverage}",
        "ExecutionMode=0",
        f"Report={report_name}",
        "ReplaceReport=1",
        "ShutdownTerminal=1",
    ]
    _write_utf16(output_ini, "\n".join(ini_lines) + "\n")
    return output_ini


def run_strategy_tester(
    terminal_exe: Path,
    ini_path: Path,
    timeout_seconds: int = 3600,
) -> subprocess.CompletedProcess:
    """Dispara terminal64.exe /config:<ini>. Bloqueia até encerrar."""
    cmd = [str(terminal_exe), f"/config:{ini_path}"]
    return subprocess.run(
        cmd,
        timeout=timeout_seconds,
        capture_output=True,
        text=True,
        check=False,
    )


def _locate_report(env: MT5Environment, report_name: str) -> Path | None:
    """Busca o report gerado nas locations conhecidas do MT5.

    Ordem empírica observada no MT5 Build 5800: HTM é gerado no data_folder
    raiz (sem subpasta). XML não é gerado via CLI — só via GUI/context menu.
    """
    candidates = [
        env.data_folder / f"{report_name}.htm",
        env.data_folder / "MQL5" / "Files" / f"{report_name}.htm",
        env.tester_dir / f"{report_name}.htm",
        env.data_folder / "reports" / f"{report_name}.htm",
        env.data_folder / f"{report_name}.xml",
        env.data_folder / "MQL5" / "Files" / f"{report_name}.xml",
        env.tester_dir / f"{report_name}.xml",
    ]
    return next((p for p in candidates if p.exists()), None)


@dataclass
class BacktestRunResult:
    run_id: str
    set_file: Path
    ini_file: Path
    return_code: int
    elapsed_seconds: float
    stdout_tail: str
    stderr_tail: str
    report_path: Path | None


def prepare_and_run(
    env: MT5Environment,
    ea_relative_path: str,
    ea_inputs_defaults: dict[str, Any],
    ranges: list[ParameterRange],
    symbol: str,
    period: str,
    from_date: date,
    to_date: date,
    modeling: ModelingQuality,
    optimization: int,
    criterion: OptimizationCriterion,
    deposit: float,
    leverage: int,
    currency: str,
    timeout_seconds: int = 3600,
) -> BacktestRunResult:
    """Orquestra geração de config + execução + localização do report."""
    run_id = uuid.uuid4().hex[:8]
    report_name = f"aura_{run_id}"

    # MT5 lê ExpertParameters relativo ao config_dir; salvar .set e .ini juntos lá.
    config_dir = env.config_dir
    config_dir.mkdir(parents=True, exist_ok=True)

    set_file = config_dir / f"{report_name}.set"
    ini_file = config_dir / f"{report_name}.ini"

    generate_set_file(ea_inputs_defaults, ranges, set_file)
    generate_tester_ini(
        ea_relative_path=ea_relative_path,
        set_file=set_file,
        symbol=symbol,
        period=period,
        from_date=from_date,
        to_date=to_date,
        modeling=modeling,
        optimization=optimization,
        criterion=criterion,
        report_name=report_name,
        deposit=deposit,
        leverage=leverage,
        currency=currency,
        output_ini=ini_file,
    )

    t0 = time.time()
    proc = run_strategy_tester(env.terminal_exe, ini_file, timeout_seconds)
    elapsed = time.time() - t0

    return BacktestRunResult(
        run_id=run_id,
        set_file=set_file,
        ini_file=ini_file,
        return_code=proc.returncode,
        elapsed_seconds=elapsed,
        stdout_tail=(proc.stdout or "")[-1000:],
        stderr_tail=(proc.stderr or "")[-1000:],
        report_path=_locate_report(env, report_name),
    )
