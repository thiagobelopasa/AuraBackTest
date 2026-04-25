"""Avaliador de expressões matemáticas customizadas sobre métricas.

Usuário define fórmulas tipo `net_profit / max_drawdown_pct` ou
`(sharpe_ratio + sortino_ratio) / 2` pra rankear passes/runs por critério
próprio.

Segurança: usamos `ast.parse` e só permitimos uma lista curta de nós AST
(BinOp, UnaryOp, Num, Name, Call de funções whitelisted). Zero `eval()`,
zero `__import__`, zero side-effects.

Funções disponíveis: min, max, abs, log, sqrt, exp, pow.
"""
from __future__ import annotations

import ast
import math
import operator
from typing import Any


_ALLOWED_FUNCS = {
    "min": min, "max": max, "abs": abs,
    "log": math.log, "sqrt": math.sqrt,
    "exp": math.exp, "pow": math.pow,
}

_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_ALLOWED_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


class FormulaError(Exception):
    """Fórmula inválida ou insegura."""


def _eval_node(node: ast.AST, variables: dict[str, float]) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, variables)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise FormulaError(f"Constante não-numérica: {node.value!r}")
    if isinstance(node, ast.Num):  # compat py<3.8
        return float(node.n)
    if isinstance(node, ast.Name):
        name = node.id
        if name not in variables:
            raise FormulaError(f"Variável desconhecida: {name!r}")
        v = variables[name]
        if v is None or (isinstance(v, float) and math.isnan(v)):
            raise FormulaError(f"Variável {name!r} é None/NaN")
        return float(v)
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_BINOPS:
            raise FormulaError(f"Operador não permitido: {op_type.__name__}")
        left = _eval_node(node.left, variables)
        right = _eval_node(node.right, variables)
        try:
            return _ALLOWED_BINOPS[op_type](left, right)
        except ZeroDivisionError:
            raise FormulaError("Divisão por zero") from None
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_UNARYOPS:
            raise FormulaError(f"Unário não permitido: {op_type.__name__}")
        return _ALLOWED_UNARYOPS[op_type](_eval_node(node.operand, variables))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise FormulaError("Só funções por nome (sem atributo)")
        fname = node.func.id
        if fname not in _ALLOWED_FUNCS:
            raise FormulaError(f"Função não permitida: {fname!r}")
        args = [_eval_node(a, variables) for a in node.args]
        return float(_ALLOWED_FUNCS[fname](*args))
    raise FormulaError(f"Nó AST não permitido: {type(node).__name__}")


def evaluate(formula: str, variables: dict[str, Any]) -> float:
    """Avalia `formula` usando os valores em `variables`.

    Exemplo:
        evaluate("net_profit / max_drawdown_pct",
                 {"net_profit": 5000, "max_drawdown_pct": 10})
        -> 500.0
    """
    if not formula or not formula.strip():
        raise FormulaError("Fórmula vazia")
    try:
        tree = ast.parse(formula, mode="eval")
    except SyntaxError as e:
        raise FormulaError(f"Sintaxe inválida: {e}") from e

    # Sanitiza: só passa números por isso converte em float já na coleta
    cleaned: dict[str, float] = {}
    for k, v in (variables or {}).items():
        if isinstance(v, (int, float)) and not math.isnan(float(v)):
            cleaned[k] = float(v)

    return _eval_node(tree, cleaned)


def evaluate_safe(formula: str, variables: dict[str, Any]) -> float | None:
    """Igual a `evaluate` mas retorna None se der erro (útil pra ranking)."""
    try:
        return evaluate(formula, variables)
    except (FormulaError, ZeroDivisionError, ValueError, OverflowError):
        return None


def available_variables_from_passes(passes: list[dict[str, Any]]) -> list[str]:
    """Descobre variáveis disponíveis olhando computed_metrics + native_metrics."""
    seen: set[str] = set()
    for p in passes[:20]:  # amostra
        for key in ("computed_metrics", "native_metrics"):
            for k, v in (p.get(key) or {}).items():
                if isinstance(v, (int, float)):
                    seen.add(k)
        for k, v in (p.get("parameters") or {}).items():
            if isinstance(v, (int, float)):
                seen.add(k)
    return sorted(seen)
