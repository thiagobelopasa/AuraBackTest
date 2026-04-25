"""Schemas Pydantic compartilhados entre rotas, serviços e frontend."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- MQL5 inputs
class MQ5Type(str, Enum):
    INT = "int"
    LONG = "long"
    ULONG = "ulong"
    DOUBLE = "double"
    BOOL = "bool"
    STRING = "string"
    DATETIME = "datetime"
    COLOR = "color"


class EAInput(BaseModel):
    """Input extraído de um arquivo .mq5 via mq5_parser."""
    name: str
    type: MQ5Type
    default: Any
    comment: str | None = None
    optimizable: bool = True  # heurística: ulong/string/color viram False


class EADefinition(BaseModel):
    """Resultado do parse de um .mq5."""
    file_path: str
    inputs: list[EAInput]


# ---------------------------------------------------------------- Ticks
class TickDatasetInfo(BaseModel):
    """Metadados de um dataset de ticks convertido para Parquet."""
    source_csv: str
    parquet_dir: str
    symbol: str
    first_timestamp: datetime
    last_timestamp: datetime
    total_ticks: int
    size_bytes_parquet: int


# ---------------------------------------------------------------- Otimização
class ParameterRange(BaseModel):
    """Range de otimização para um input do EA."""
    name: str
    start: float
    stop: float
    step: float
    fixed_value: float | None = None  # se preenchido, ignora start/stop/step


class OptimizationMode(str, Enum):
    SINGLE = "single"              # rodar uma vez com defaults/fixed
    GRID = "grid"                  # busca exaustiva
    GENETIC = "genetic"            # GA nativo do MT5
    WALK_FORWARD = "walk_forward"  # WFA com folds


class ModelingQuality(str, Enum):
    REAL_TICKS = "every_tick_real"
    GENERATED_TICKS = "every_tick"
    OHLC_1M = "1min_ohlc"


class OptimizationCriterion(str, Enum):
    BALANCE = "balance"
    PROFIT_FACTOR = "profit_factor"
    EXPECTED_PAYOFF = "expected_payoff"
    DRAWDOWN = "drawdown_min"
    RECOVERY = "recovery_factor"
    SHARPE = "sharpe_ratio"
    COMPLEX = "complex_criterion"  # combinação do MT5


class OptimizationRequest(BaseModel):
    ea_path: str
    symbol: str
    timeframe: str = "M1"
    from_date: date
    to_date: date
    deposit: float = 10_000.0
    leverage: int = 100
    currency: str = "USD"
    modeling: ModelingQuality = ModelingQuality.REAL_TICKS
    mode: OptimizationMode = OptimizationMode.GRID
    criterion: OptimizationCriterion = OptimizationCriterion.COMPLEX
    parameters: list[ParameterRange]

    # WFA
    wfa_folds: int = 5
    wfa_oos_pct: float = 0.25  # 25% out-of-sample por fold

    # Monte Carlo (rodado em cima dos trades do melhor setup)
    mc_runs: int = 1000
    mc_confidence: float = 0.95


# ---------------------------------------------------------------- Resultados
class BacktestMetrics(BaseModel):
    """Conjunto de métricas estilo QuantAnalyzer + MT5 Report."""
    # Lucros
    net_profit: float
    gross_profit: float
    gross_loss: float
    profit_factor: float
    expected_payoff: float

    # Risco / qualidade
    sharpe_ratio: float
    sortino_ratio: float
    recovery_factor: float
    sqn: float  # System Quality Number (Van Tharp)
    max_drawdown: float
    max_drawdown_pct: float
    ulcer_index: float

    # Trades
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    consecutive_wins: int
    consecutive_losses: int

    # Exposição temporal
    bars_in_test: int | None = None
    ticks_modeled: int | None = None


class BacktestRun(BaseModel):
    run_id: str
    parameters: dict[str, float | int | bool | str]
    metrics: BacktestMetrics
    started_at: datetime
    finished_at: datetime


class OptimizationReport(BaseModel):
    request: OptimizationRequest
    runs: list[BacktestRun]
    best_by_criterion: BacktestRun | None = None
    wfa_stability: float | None = None  # score OOS médio / IS médio
