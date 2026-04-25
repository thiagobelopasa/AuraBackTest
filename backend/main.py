import argparse
import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from routers import analysis, ea, live_optimization, mt5, optimization, portfolio, ticks, triage
from services import storage


app = FastAPI(
    title="AuraBackTest API",
    description="Motor de backtesting de estratégias MQL5 com análise estilo QuantAnalyzer",
    version="0.3.0",
)


@app.on_event("startup")
def _init_db() -> None:
    storage.init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "null"],
    allow_origin_regex=r"http://localhost:\d+",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ea.router)
app.include_router(ticks.router)
app.include_router(mt5.router)
app.include_router(analysis.router)
app.include_router(optimization.router)
app.include_router(triage.router)
app.include_router(portfolio.router)
app.include_router(live_optimization.router)


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Frontend estático: serve frontend/dist em /app quando existe.
# Em dev puro (sem build), a rota cai para a mensagem de API.
# ---------------------------------------------------------------------------
def _resolve_frontend_dist() -> Path | None:
    candidates = [
        # Em dev: ../frontend/dist relativo a backend/main.py
        Path(__file__).resolve().parent.parent / "frontend" / "dist",
        # Em pacote Electron: resources/frontend
        Path(os.environ.get("AURABACKTEST_FRONTEND_DIR", "")) if os.environ.get("AURABACKTEST_FRONTEND_DIR") else None,
    ]
    for c in candidates:
        if c and c.exists() and (c / "index.html").exists():
            return c
    return None


_FRONTEND_DIST = _resolve_frontend_dist()

if _FRONTEND_DIST:
    # Mount em /app para não conflitar com os routers
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")

    @app.get("/app")
    @app.get("/app/{full_path:path}")
    def serve_frontend(full_path: str = "") -> FileResponse:
        return FileResponse(_FRONTEND_DIST / "index.html")

    @app.get("/")
    def root_redirect():
        return FileResponse(_FRONTEND_DIST / "index.html")
else:
    @app.get("/")
    def root():
        return {"status": "AuraBackTest API rodando", "version": app.version,
                "frontend": "não encontrado — rode `npm run build` em frontend/"}


def _main() -> None:
    """Entry point quando empacotado via PyInstaller. Aceita --host/--port."""
    parser = argparse.ArgumentParser(prog="AuraBackTestServer")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--port", type=int,
        default=int(os.environ.get("AURABACKTEST_PORT", "8765")),
    )
    args = parser.parse_args()

    import uvicorn  # noqa: WPS433 — import tardio para PyInstaller coletar só quando usado
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    _main()
