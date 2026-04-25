"""Neighborhood stability analysis para resultados de otimização.

A ideia: um setup "bom" isolado num pico agudo do espaço de parâmetros é
overfitting. Um setup bom cercado de vizinhos também bons é robusto.

Para cada pass, acha os vizinhos (±1 step em cada dimensão do grid) e computa:
    - neighbor_count: quantos vizinhos existem no resultado
    - score_mean:    média do score (ele + vizinhos)
    - score_std:     desvio-padrão
    - stability:     1 - std/|mean|  (clamp 0..1) — alto = platô estável
    - robust_score:  score * stability — ranking recomendado
"""
from __future__ import annotations

import math
import statistics
from typing import Any


def _numeric_params(params: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for k, v in params.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[k] = float(v)
    return out


def _infer_steps(passes: list[dict[str, Any]]) -> dict[str, float]:
    """Para cada param numérico, step = menor diferença positiva entre valores únicos."""
    by_param: dict[str, set[float]] = {}
    for p in passes:
        for k, v in _numeric_params(p["parameters"]).items():
            by_param.setdefault(k, set()).add(v)
    steps: dict[str, float] = {}
    for k, values in by_param.items():
        sv = sorted(values)
        diffs = [sv[i + 1] - sv[i] for i in range(len(sv) - 1) if sv[i + 1] - sv[i] > 0]
        steps[k] = min(diffs) if diffs else 1.0
    return steps


def compute_stability(
    passes: list[dict[str, Any]],
    score_key: str = "score",
) -> list[dict[str, Any]]:
    """Enriquece cada pass com métricas de estabilidade.

    `passes`: lista de {pass_idx, parameters, metrics}
    `score_key`: chave dentro de metrics usada pra ranking (ex: 'net_profit').
    """
    if not passes:
        return []

    # Fallback: se o score_key não existe em ninguém, tenta 'score' depois 'net_profit'
    def _score(p: dict[str, Any]) -> float | None:
        m = p.get("metrics", {})
        for k in (score_key, "score", "net_profit"):
            if k in m and m[k] is not None:
                try:
                    return float(m[k])
                except (TypeError, ValueError):
                    pass
        return None

    steps = _infer_steps(passes)

    # Indexa passes por tupla de (param, valor arredondado)
    def _key(params: dict[str, Any]) -> tuple:
        np = _numeric_params(params)
        return tuple(sorted((k, round(v, 8)) for k, v in np.items()))

    index: dict[tuple, dict[str, Any]] = {_key(p["parameters"]): p for p in passes}

    enriched: list[dict[str, Any]] = []
    for p in passes:
        np = _numeric_params(p["parameters"])
        own_score = _score(p)
        if own_score is None:
            enriched.append({**p, "stability": 0.0, "neighbor_count": 0,
                             "score_mean": 0.0, "score_std": 0.0, "robust_score": 0.0})
            continue

        neighbor_scores: list[float] = [own_score]
        # Vizinhos: ±1 step em cada dimensão (um param de cada vez)
        for param, val in np.items():
            step = steps.get(param, 1.0)
            for delta in (-step, +step):
                candidate = dict(np)
                candidate[param] = round(val + delta, 8)
                key = tuple(sorted(candidate.items()))
                neighbor = index.get(key)
                if neighbor is not None:
                    ns = _score(neighbor)
                    if ns is not None:
                        neighbor_scores.append(ns)

        mean = statistics.fmean(neighbor_scores)
        std = statistics.pstdev(neighbor_scores) if len(neighbor_scores) > 1 else 0.0
        denom = abs(mean) if abs(mean) > 1e-9 else 1.0
        stability = max(0.0, min(1.0, 1.0 - std / denom))
        if math.isnan(stability):
            stability = 0.0
        robust_score = own_score * stability

        enriched.append({
            **p,
            "neighbor_count": len(neighbor_scores) - 1,
            "score_mean": mean,
            "score_std": std,
            "stability": stability,
            "robust_score": robust_score,
        })

    return enriched
