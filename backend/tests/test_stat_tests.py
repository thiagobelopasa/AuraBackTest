"""Smoke tests dos 6 testes estatísticos Simons-style."""
from __future__ import annotations

from services.stat_tests import run_stat_validation


def test_run_stat_validation_returns_scorecard(sample_trades):
    r = run_stat_validation(sample_trades, initial=10_000.0)
    # Estrutura esperada: {items: [...], pass_count, fail_count, overall}
    # (confirma ao menos que roda sem crashar e retorna dict)
    assert isinstance(r, dict)
    # Deve conter campos-chave
    keys = set(r.keys())
    assert keys & {"items", "scorecard", "tests"}  # algum deles existe


def test_stat_validation_handles_tiny_sample():
    """Poucos trades — ainda deve retornar sem crash, mesmo que com NaN/FAIL."""
    tiny = [
        {"time_in": "2024-01-01", "time_out": "2024-01-01", "profit": 10.0,
         "balance": 10010.0, "side": "buy", "volume": 0.1, "entry_price": 1.0,
         "exit_price": 1.01, "duration_sec": 3600},
        {"time_in": "2024-01-02", "time_out": "2024-01-02", "profit": -5.0,
         "balance": 10005.0, "side": "sell", "volume": 0.1, "entry_price": 1.01,
         "exit_price": 1.00, "duration_sec": 3600},
    ]
    # Não deve crashar
    r = run_stat_validation(tiny, initial=10_000.0)
    assert r is not None
