"""Redução dimensional para visualização 3D dos resultados de otimização.

PCA via SVD (numpy). Sem dependências externas (sklearn/umap).

Dois modos de saída:
    - 'scatter': coordenadas (x, y, z) = 3 primeiras componentes principais
    - 'sphere':  mapeia (PC1, PC2) para (azimute, elevação) na esfera unitária e
                 usa a métrica (normalizada) como extensão radial — "montanhas
                 num planeta". Candidatos parecidos ficam próximos na superfície.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np


def _numeric_matrix(passes: list[dict[str, Any]], params: list[str]) -> np.ndarray:
    """Monta matriz (N, P) só com params numéricos. Normaliza coluna a coluna."""
    rows = []
    for p in passes:
        row = []
        for k in params:
            v = p["parameters"].get(k)
            row.append(float(v) if isinstance(v, (int, float)) else 0.0)
        rows.append(row)
    X = np.array(rows, dtype=np.float64)
    # Z-score por coluna; colunas constantes viram zeros
    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    return (X - mu) / sd


def _pca_3d(X: np.ndarray) -> np.ndarray:
    """Retorna (N, 3) via SVD. Se o espaço tem <3 dims, completa com zeros."""
    n, p = X.shape
    if n == 0 or p == 0:
        return np.zeros((n, 3))
    k = min(3, p)
    # SVD da matriz centralizada (já foi z-scored)
    U, S, Vt = np.linalg.svd(X, full_matrices=False)
    # Componentes principais: U[:, :k] * S[:k]
    coords = U[:, :k] * S[:k]
    if k < 3:
        pad = np.zeros((n, 3 - k))
        coords = np.concatenate([coords, pad], axis=1)
    return coords


def _metric_values(passes: list[dict[str, Any]], metric_key: str) -> np.ndarray:
    vals = []
    for p in passes:
        if metric_key == "robust_score":
            v = p.get("robust_score", 0.0)
        elif metric_key == "stability":
            v = p.get("stability", 0.0)
        else:
            v = p.get("metrics", {}).get(metric_key, 0.0)
        vals.append(float(v) if v is not None else 0.0)
    return np.array(vals, dtype=np.float64)


def project(
    passes: list[dict[str, Any]],
    params: list[str],
    metric_key: str = "robust_score",
    mode: str = "sphere",
    sphere_radius: float = 1.0,
    sphere_amplitude: float = 0.5,
) -> dict[str, Any]:
    """Retorna dict com x, y, z, metric, stability, neighbor_count por ponto.

    mode:
        'scatter' — (x,y,z) = PC1, PC2, PC3 escalados
        'sphere'  — base na esfera + extensão radial proporcional à métrica
    """
    if not passes or not params:
        return {"mode": mode, "x": [], "y": [], "z": [], "metric": [],
                "stability": [], "neighbor_count": [], "param_values": {}}

    X = _numeric_matrix(passes, params)
    pcs = _pca_3d(X)  # (N, 3)
    # Escala para [-1, 1] em cada eixo
    for i in range(3):
        col = pcs[:, i]
        mx = np.max(np.abs(col))
        if mx > 0:
            pcs[:, i] = col / mx

    metric = _metric_values(passes, metric_key)
    # Normaliza métrica para [0, 1]
    mn, mx = float(metric.min()), float(metric.max())
    if mx > mn:
        metric_norm = (metric - mn) / (mx - mn)
    else:
        metric_norm = np.zeros_like(metric)

    if mode == "scatter":
        x, y, z = pcs[:, 0], pcs[:, 1], pcs[:, 2]
    else:  # sphere
        # PC1 -> azimute (0..2π), PC2 -> elevação (-π/2..π/2)
        phi = (pcs[:, 0] + 1.0) * math.pi  # 0..2π
        theta = pcs[:, 1] * (math.pi / 2)  # -π/2..π/2
        r = sphere_radius + metric_norm * sphere_amplitude
        x = r * np.cos(theta) * np.cos(phi)
        y = r * np.cos(theta) * np.sin(phi)
        z = r * np.sin(theta)

    stability = [float(p.get("stability", 0.0)) for p in passes]
    neighbors = [int(p.get("neighbor_count", 0)) for p in passes]
    param_values = {k: [p["parameters"].get(k) for p in passes] for k in params}

    return {
        "mode": mode,
        "x": x.tolist(),
        "y": y.tolist(),
        "z": z.tolist(),
        "metric": metric.tolist(),
        "metric_key": metric_key,
        "stability": stability,
        "neighbor_count": neighbors,
        "param_values": param_values,
        "metric_range": [mn, mx],
    }
