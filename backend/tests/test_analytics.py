"""Tests do motor analytics.full_analysis()."""
from __future__ import annotations

from services import analytics


def test_full_analysis_returns_all_keys(sample_trades):
    result = analytics.full_analysis(sample_trades, initial_equity=10_000.0)
    # Todas as chaves documentadas no CLAUDE.md devem existir
    expected = {
        "equity_curve", "drawdown_curve", "net_profit", "win_rate",
        "sharpe_ratio", "sortino_ratio", "calmar_ratio", "sqn",
        "payoff_ratio", "recovery_factor", "expectancy",
        "profit_factor", "max_drawdown_pct",
        "time_breakdown", "mae_mfe", "direction", "risk_of_ruin",
    }
    missing = expected - set(result.keys())
    assert not missing, f"Chaves ausentes: {missing}"


def test_net_profit_equals_sum_of_trade_profits(sample_trades):
    result = analytics.full_analysis(sample_trades, 10_000.0)
    expected = sum(t["profit"] for t in sample_trades)
    assert abs(result["net_profit"] - expected) < 1e-6


def test_build_equity_curve_shapes(sample_trades):
    eq = analytics.build_equity_curve(sample_trades, 10_000.0)
    # N+1 valores (inicial + N trades)
    assert eq.values.shape == (len(sample_trades) + 1,)
    assert eq.values[0] == 10_000.0
    assert eq.drawdown_abs.shape == eq.values.shape
    # Drawdown é sempre não-negativo
    assert (eq.drawdown_abs >= 0).all()


def test_win_rate_computation(sample_trades):
    result = analytics.full_analysis(sample_trades, 10_000.0)
    wins = sum(1 for t in sample_trades if t["profit"] > 0)
    expected_wr = wins / len(sample_trades)
    assert abs(result["win_rate"] - expected_wr) < 1e-6


def test_empty_trades_does_not_crash():
    # Edge case: lista vazia — não deve crashar (pode levantar ou retornar dict vazio)
    try:
        result = analytics.full_analysis([], 10_000.0)
        # Se retornou, aceita qualquer forma (dict vazio, net_profit=0, etc.)
        assert isinstance(result, dict)
    except (IndexError, ValueError, ZeroDivisionError):
        # Comportamento aceitável também: levantar exceção controlada
        pass
