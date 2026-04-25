"""Endpoints para coleta ao vivo de passes durante otimização MT5.

Cada sessão de coleta fica persistida em `live_opt_sessions` com identificação
por robô + timeframe + símbolo. Os passes ficam em `live_opt_passes` com os
trades processados — permite:
  - Listar sessions no Histórico
  - Enviar session completa pra Triagem (análise de robustez por vizinhança)
  - Abrir os top-N passes como Runs tradicionais (análise individual com MC,
    MAE/MFE, stat validation, etc.)

Fluxo:
  1. POST /live-optimization/start   → cria session no banco, inicia watcher
  2. Cliente roda otimização no MT5 (EA instrumentado grava cada pass no dir comum)
  3. Watcher ingere → computed_metrics + trades → persiste + WS
  4. POST /live-optimization/stop    → encerra session
  5. Cliente pode: deletar, enviar pra triagem, abrir top 10 como runs.
"""
from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from services import analytics, custom_metrics, pbo, stability, storage
from services.pass_watcher import watcher


router = APIRouter(prefix="/live-optimization", tags=["live-optimization"])


# -------------------------------------------------------- start/stop/snapshot
class StartRequest(BaseModel):
    robot_name: str | None = None       # preenchido pelo frontend a partir do nome do EA
    timeframe: str | None = None        # ex: "M1", "H1" — preenchido pelo frontend
    label: str | None = None            # descrição amigável (opcional)
    watch_dir: str | None = None


class StartResponse(BaseModel):
    session_id: str
    running: bool
    watch_dir: str
    message: str


def _detect_stale_files(watch_dir: Path) -> dict[str, int]:
    """Detecta arquivos antigos no diretório de watch.

    Retorna contagem de .json.processed e .json.error (sinais de coletas anteriores).
    """
    if not watch_dir.exists():
        return {"processed": 0, "error": 0}

    counts = {"processed": 0, "error": 0}
    for fname in watch_dir.iterdir():
        if fname.is_file():
            if fname.name.endswith(".json.processed"):
                counts["processed"] += 1
            elif fname.name.endswith(".json.error"):
                counts["error"] += 1
    return counts


@router.post("/start", response_model=StartResponse)
def start(req: StartRequest) -> StartResponse:
    # Se havia uma session ativa anterior, encerra antes de começar nova.
    # (watcher singleton — uma session por vez)
    prev = _current_session_id()
    if prev:
        storage.end_live_session(prev)

    if req.watch_dir:
        watcher.watch_dir = Path(req.watch_dir)

    session_id = uuid.uuid4().hex[:12]
    storage.create_live_session(
        session_id=session_id,
        robot_name=req.robot_name,
        symbol=None,          # descoberto no primeiro pass
        timeframe=req.timeframe,
        label=req.label,
    )
    watcher.start(session_id=session_id)

    # Detectar arquivos antigos e avisar ao usuário
    stale = _detect_stale_files(watcher.watch_dir)
    warning = ""
    if stale["processed"] > 0 or stale["error"] > 0:
        warning = f"⚠️ Detectados {stale['processed']} arquivos processados e {stale['error']} com erro. Clique em '🗑️ Limpar arquivos' antes de iniciar."

    return StartResponse(
        session_id=session_id,
        running=watcher.is_running(),
        watch_dir=str(watcher.watch_dir),
        message=warning or f"Monitorando {watcher.watch_dir}. Rode a otimização no MT5.",
    )


@router.post("/stop")
def stop() -> dict[str, Any]:
    sid = _current_session_id()
    watcher.stop()
    if sid:
        storage.end_live_session(sid)

    # Auto-limpar arquivos processados para evitar re-coleta acidental
    cleared_files = 0
    if watcher.watch_dir.exists():
        for fname in watcher.watch_dir.iterdir():
            if fname.is_file() and (fname.name.endswith(".json.processed") or fname.name.endswith(".json.error")):
                try:
                    fname.unlink()
                    cleared_files += 1
                except OSError:
                    pass

    return {
        "running": watcher.is_running(),
        "session_id": sid,
        "auto_cleared_files": cleared_files,
    }


@router.get("/snapshot")
def snapshot() -> dict[str, Any]:
    """Snapshot da session ATIVA (ou da última, se já parada)."""
    s = watcher.snapshot()
    s["session_id"] = _current_session_id()
    return s


@router.post("/clear")
def clear() -> dict[str, Any]:
    """Limpa buffer em memória (não apaga do banco). Útil pra recomeçar visualização."""
    with watcher._lock:  # noqa: SLF001
        watcher._passes = []
    return {"cleared": True}


@router.post("/clear-files")
def clear_files() -> dict[str, Any]:
    """Limpa arquivos processados do diretório de watch.

    Evita que passes antigos sejam recoletados quando você para e reinicia.
    Remove .json.processed e .json.error — deixa .json (em processamento) intactos.
    """
    if not watcher.watch_dir.exists():
        return {"cleared_count": 0, "error": "watch_dir não existe"}

    cleared = 0
    for fname in watcher.watch_dir.iterdir():
        if fname.is_file() and (fname.suffix in (".processed", ".error") or fname.name.endswith(".json.processed") or fname.name.endswith(".json.error")):
            try:
                fname.unlink()
                cleared += 1
            except OSError:
                pass

    # Também limpa o buffer em memória
    with watcher._lock:  # noqa: SLF001
        watcher._passes = []

    return {"cleared_files": cleared, "cleared_memory": True}


def _current_session_id() -> str | None:
    return watcher._session_id  # noqa: SLF001


# ------------------------------------------------------------- WebSocket stream
@router.websocket("/ws")
async def websocket_stream(ws: WebSocket) -> None:
    await ws.accept()
    queue: asyncio.Queue = asyncio.Queue(maxsize=500)
    await ws.send_json({"event": "snapshot", "data": watcher.snapshot()})
    watcher.subscribe(queue)
    try:
        while True:
            msg = await queue.get()
            await ws.send_json(msg)
    except WebSocketDisconnect:
        pass
    finally:
        watcher.unsubscribe(queue)


# ---------------------------------------------------------- sessions (histórico)
@router.get("/sessions")
def list_sessions(limit: int = 100) -> list[dict[str, Any]]:
    return storage.list_live_sessions(limit=limit)


@router.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    s = storage.get_live_session(session_id)
    if not s:
        raise HTTPException(404, f"Session não encontrada: {session_id}")
    return s


@router.get("/sessions/{session_id}/passes")
def get_session_passes(session_id: str) -> dict[str, Any]:
    s = storage.get_live_session(session_id)
    if not s:
        raise HTTPException(404, f"Session não encontrada: {session_id}")
    passes = storage.load_session_passes(session_id)
    # Remove trades do payload pra não pesar demais no browser
    for p in passes:
        p.pop("trades", None)
    return {"session": s, "passes": passes}


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str) -> dict[str, Any]:
    ok = storage.delete_live_session(session_id)
    if not ok:
        raise HTTPException(404, f"Session não encontrada: {session_id}")
    return {"deleted": True}


class SessionFavoriteRequest(BaseModel):
    favorite: bool


@router.patch("/sessions/{session_id}/favorite")
def patch_session_favorite(session_id: str, req: SessionFavoriteRequest) -> dict[str, Any]:
    ok = storage.set_session_favorite(session_id, req.favorite)
    if not ok:
        raise HTTPException(404, f"Session não encontrada: {session_id}")
    return {"session_id": session_id, "favorite": req.favorite}


# ------------------------------------------ criar runs tradicionais a partir de passes
class OpenTopNRequest(BaseModel):
    sort_key: str = "sortino_ratio"
    top_n: int = 10
    ascending: bool = False
    custom_formula: str | None = None   # se definido, ignora sort_key e usa fórmula


class OpenedRun(BaseModel):
    run_id: str
    pass_id: str | None
    label: str
    rank: int
    score: float | None


@router.post("/sessions/{session_id}/open-top", response_model=list[OpenedRun])
def open_top_as_runs(session_id: str, req: OpenTopNRequest) -> list[OpenedRun]:
    """Cria N Runs tradicionais a partir dos top-N passes da session.

    Cada pass coletado tem os trades processados; convertendo-os em Run normal
    permite rodar Monte Carlo, MAE/MFE ticks, stat validation, suite de
    robustez, etc. individualmente — tudo via pipeline existente.
    """
    s = storage.get_live_session(session_id)
    if not s:
        raise HTTPException(404, f"Session não encontrada: {session_id}")
    passes = storage.load_session_passes(session_id)
    if not passes:
        raise HTTPException(400, "Session sem passes coletados")

    # Fórmula customizada tem precedência; senão usa sort_key direto
    if req.custom_formula:
        def score_of(p: dict[str, Any]) -> float:
            vars_p = {**p.get("computed_metrics", {}), **p.get("native_metrics", {}),
                      **p.get("parameters", {})}
            v = custom_metrics.evaluate_safe(req.custom_formula, vars_p)
            return v if v is not None else -1e18
    else:
        def score_of(p: dict[str, Any]) -> float:
            v = p["computed_metrics"].get(req.sort_key)
            if v is None:
                v = p["native_metrics"].get(req.sort_key)
            return v if isinstance(v, (int, float)) else -1e18

    passes.sort(key=score_of, reverse=not req.ascending)
    top = passes[: req.top_n]

    robot = s.get("robot_name") or "live"
    symbol = s.get("symbol") or ""
    timeframe = s.get("timeframe") or ""
    initial = s.get("initial_deposit") or 10000.0

    opened: list[OpenedRun] = []
    for rank, p in enumerate(top, start=1):
        run_id = uuid.uuid4().hex[:12]
        score = score_of(p)
        label = f"{robot} #{rank} ({req.sort_key}={score:.3f})"

        # Salva run + trades + analysis no formato tradicional
        metrics = {**p.get("native_metrics", {}), **p.get("computed_metrics", {})}
        storage.save_run(
            run_id=run_id,
            kind="live_pass",
            ea_path=None,
            symbol=symbol,
            timeframe=timeframe,
            from_date=None,
            to_date=None,
            deposit=initial,
            report_path=None,
            parameters=p.get("parameters") or {},
            metrics=metrics,
            label=label,
        )
        trades = p.get("trades") or []
        if trades:
            storage.save_trades(run_id, trades)
            try:
                full = analytics.full_analysis(trades, initial)
                storage.save_analysis(run_id, initial, full)
            except Exception as e:  # noqa: BLE001
                # analytics pode falhar em passes muito pequenos — salva o run mesmo assim
                print(f"[open-top] analytics falhou para pass #{rank}: {e}")

        opened.append(OpenedRun(
            run_id=run_id,
            pass_id=p.get("pass_id"),
            label=label,
            rank=rank,
            score=score if score > -1e17 else None,
        ))
    return opened


# --------------------------------------------------- PBO via CSCV (overfit check)
class SessionPBORequest(BaseModel):
    subsets: int = 16
    min_trades: int = 20       # descarta passes com trades insuficientes


class EvalFormulaRequest(BaseModel):
    formula: str
    session_id: str


@router.post("/eval-formula")
def eval_formula(req: EvalFormulaRequest) -> dict[str, Any]:
    """Testa uma fórmula custom sobre os passes de uma session e retorna
    preview do ranking (top 5 + bottom 2) pro usuário validar antes de aplicar.
    """
    passes = storage.load_session_passes(req.session_id)
    if not passes:
        raise HTTPException(400, "Session sem passes")

    scored = []
    errors = 0
    for p in passes:
        vars_p = {**p.get("computed_metrics", {}), **p.get("native_metrics", {}),
                  **p.get("parameters", {})}
        v = custom_metrics.evaluate_safe(req.formula, vars_p)
        if v is None:
            errors += 1
            continue
        scored.append({
            "pass_id": p.get("pass_id"),
            "parameters": p.get("parameters"),
            "score": v,
        })

    if not scored:
        # Tenta uma vez mostrando o erro real
        try:
            custom_metrics.evaluate(req.formula, {**passes[0].get("computed_metrics", {}),
                                                   **passes[0].get("native_metrics", {})})
        except custom_metrics.FormulaError as e:
            raise HTTPException(400, f"Fórmula inválida: {e}") from e
        raise HTTPException(400, "Fórmula não retornou valor pra nenhum pass")

    scored.sort(key=lambda x: x["score"], reverse=True)
    return {
        "variables_available": custom_metrics.available_variables_from_passes(passes),
        "total_passes": len(passes),
        "evaluated": len(scored),
        "errors": errors,
        "top": scored[:5],
        "bottom": scored[-2:] if len(scored) > 5 else [],
    }


@router.post("/sessions/{session_id}/pbo")
def session_pbo(session_id: str, req: SessionPBORequest) -> dict[str, Any]:
    """Calcula PBO (Probability of Backtest Overfitting) via CSCV sobre os
    retornos dos passes coletados.

    Retorna probabilidade de que os vencedores em IS percam em OOS — métrica
    chave para avaliar risco de overfit na otimização.
    """
    s = storage.get_live_session(session_id)
    if not s:
        raise HTTPException(404, f"Session não encontrada: {session_id}")
    passes = storage.load_session_passes(session_id)
    if not passes:
        raise HTTPException(400, "Session sem passes")

    # Constrói equity curves dos trades de cada pass com num_trades >= min_trades
    equity_curves = []
    initial = float(s.get("initial_deposit") or 10000.0)
    for p in passes:
        trades = p.get("trades") or []
        if len(trades) < req.min_trades:
            continue
        eq = analytics.build_equity_curve(trades, initial)
        equity_curves.append(eq.values.tolist())

    if len(equity_curves) < 2:
        raise HTTPException(
            400,
            f"Precisa de ≥2 passes com ≥{req.min_trades} trades cada. "
            f"Encontrados {len(equity_curves)}.",
        )

    try:
        M = pbo.equity_curves_to_returns_matrix(equity_curves)
        result = pbo.compute_pbo(M, subsets=req.subsets)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e)) from e

    return {"session": s, **pbo.as_dict(result)}


# --------------------------------------------------- enviar session pra triagem
class SessionTriageRequest(BaseModel):
    score_key: str = "sortino_ratio"


@router.post("/sessions/{session_id}/to-triage")
def to_triage(session_id: str, req: SessionTriageRequest) -> dict[str, Any]:
    """Converte passes da session no formato aceito pelo `stability.compute_stability`
    e devolve o scorecard já calculado. Reaproveita o motor da aba Triagem."""
    s = storage.get_live_session(session_id)
    if not s:
        raise HTTPException(404, f"Session não encontrada: {session_id}")
    passes = storage.load_session_passes(session_id)
    if not passes:
        raise HTTPException(400, "Session sem passes coletados")

    # Formato esperado pelo stability.compute_stability
    adapted = []
    for i, p in enumerate(passes):
        metrics = {**p.get("native_metrics", {}), **p.get("computed_metrics", {})}
        adapted.append({
            "pass_idx": i,
            "parameters": p.get("parameters") or {},
            "metrics": metrics,
        })

    enriched = stability.compute_stability(adapted, score_key=req.score_key)
    enriched.sort(key=lambda p: p.get("robust_score", 0.0), reverse=True)

    metrics_seen: set[str] = set()
    for p in adapted:
        metrics_seen.update(p["metrics"].keys())

    return {
        "session": s,
        "num_passes": len(enriched),
        "score_key": req.score_key,
        "available_metrics": sorted(metrics_seen),
        "passes": enriched,
    }
