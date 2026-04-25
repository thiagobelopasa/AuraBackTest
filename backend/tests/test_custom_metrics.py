"""Tests do parser de métricas customizadas (segurança + correção)."""
from __future__ import annotations

import pytest

from services.custom_metrics import FormulaError, evaluate, evaluate_safe


def test_basic_arithmetic():
    assert evaluate("a + b", {"a": 1, "b": 2}) == 3
    assert evaluate("a * b - c", {"a": 3, "b": 4, "c": 2}) == 10
    assert evaluate("(a + b) / 2", {"a": 10, "b": 20}) == 15


def test_math_functions():
    assert evaluate("sqrt(x)", {"x": 16}) == 4
    assert evaluate("abs(x)", {"x": -7}) == 7
    assert evaluate("max(a, b)", {"a": 3, "b": 5}) == 5
    assert evaluate("min(a, b)", {"a": 3, "b": 5}) == 3


def test_unary_negation():
    assert evaluate("-x", {"x": 5}) == -5
    assert evaluate("+x", {"x": 5}) == 5


def test_division_by_zero_raises():
    with pytest.raises(FormulaError, match="Divisão por zero"):
        evaluate("a / b", {"a": 1, "b": 0})


def test_unknown_variable_raises():
    with pytest.raises(FormulaError, match="desconhecida"):
        evaluate("a + x", {"a": 1})


def test_blocks_dunder_attribute_access():
    """Previne ataques tipo __import__, __class__, etc."""
    with pytest.raises(FormulaError):
        evaluate("x.__class__", {"x": 1})


def test_blocks_function_calls_to_non_allowed():
    with pytest.raises(FormulaError, match="não permitida"):
        evaluate("eval('1+1')", {})


def test_blocks_attribute_call():
    with pytest.raises(FormulaError):
        evaluate("str(1).lower()", {})


def test_evaluate_safe_returns_none_on_error():
    assert evaluate_safe("a / b", {"a": 1, "b": 0}) is None
    assert evaluate_safe("bogus syntax ***", {}) is None
    assert evaluate_safe("a + b", {"a": 1}) is None


def test_nan_variables_filtered_out():
    import math
    # NaN em variáveis é tratado como ausente → raise
    with pytest.raises(FormulaError):
        evaluate("a + b", {"a": 1.0, "b": math.nan})
