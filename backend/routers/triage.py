"""Triagem: upload de XML de otimização do MT5 + análise de robustez.

Fluxo QuantAnalyzer-like: usuário roda a otimização no MT5 (onde funciona
nativo), exporta o XML, e sobe aqui para filtrar overfitting via vizinhança.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from services import optimizer, projection, stability


router = APIRouter(prefix="/triage", tags=["triage"])


class ProjectRequest(BaseModel):
    passes: list[dict[str, Any]]
    params: list[str]
    metric_key: str = "robust_score"
    mode: str = "sphere"  # 'sphere' | 'scatter'


@router.post("/project-3d")
def project_3d(req: ProjectRequest) -> dict[str, Any]:
    """Projeta passes em 3D via PCA. Retorna coords + métricas para visualização."""
    return projection.project(req.passes, req.params, req.metric_key, req.mode)


class TriageResponse(BaseModel):
    num_passes: int
    score_key: str
    available_metrics: list[str]
    passes: list[dict[str, Any]]


@router.post("/upload-xml", response_model=TriageResponse)
async def upload_xml(
    file: UploadFile = File(...),
    score_key: str = "net_profit",
) -> TriageResponse:
    """Aceita XML de otimização do MT5 (SpreadsheetML) e devolve passes com
    estabilidade de vizinhança calculada.
    """
    content = await file.read()
    if not content:
        raise HTTPException(400, "Arquivo vazio")

    fd, tmp_path = tempfile.mkstemp(suffix=".xml")
    os.close(fd)
    tmp = Path(tmp_path)
    try:
        tmp.write_bytes(content)
        passes = optimizer.parse_optimization_xml(tmp)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass

    if not passes:
        raise HTTPException(
            400,
            "XML sem passes válidos. Confira se é um report de OTIMIZAÇÃO "
            "(não de um backtest único) exportado do MT5.",
        )

    passes_dict = [
        {"pass_idx": p.pass_idx, "parameters": p.parameters, "metrics": p.metrics}
        for p in passes
    ]
    enriched = stability.compute_stability(passes_dict, score_key=score_key)
    enriched.sort(key=lambda p: p.get("robust_score", 0.0), reverse=True)

    metrics_seen: set[str] = set()
    for p in passes_dict:
        metrics_seen.update(p["metrics"].keys())

    return TriageResponse(
        num_passes=len(enriched),
        score_key=score_key,
        available_metrics=sorted(metrics_seen),
        passes=enriched,
    )
