"""Watcher de passes da otimização MT5 (modo "coleta ao vivo").

Durante uma otimização no MT5, o EA do cliente (com o include
`AuraBackTestCollector.mqh`) grava um JSON por pass no diretório comum
de dados do MT5: `%APPDATA%\\MetaQuotes\\Terminal\\Common\\Files\\AuraBackTest\\`.

Este módulo faz polling desse diretório em uma thread de fundo, converte cada
JSON em uma estrutura de trades, calcula métricas via `analytics.full_analysis`
e publica num buffer in-memory que o endpoint WebSocket consome para streaming
em tempo real para o frontend.

Design decisions:
- Polling simples (1s) — evita dep nova (watchdog); diretório pequeno, custo baixo.
- Thread-safe via `threading.Lock`; passes acumulam em `_passes` (lista).
- `_subscribers` é uma lista de asyncio.Queue para fan-out via WebSocket.
- File lock: arquivos são renomeados para `.processed` após leitura, evitando
  reprocessar em checks subsequentes.
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from services import analytics, storage


# Diretório comum do MT5 (constante no Windows)
def default_common_files_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return Path.home() / "AppData" / "Roaming" / "MetaQuotes" / "Terminal" / "Common" / "Files"
    return Path(appdata) / "MetaQuotes" / "Terminal" / "Common" / "Files"


DEFAULT_WATCH_DIR = default_common_files_dir() / "AuraBackTest"


class PassWatcher:
    """Monitora o diretório e publica novos passes em um buffer."""

    def __init__(self, watch_dir: Path | None = None, poll_interval: float = 1.0):
        self.watch_dir = Path(watch_dir) if watch_dir else DEFAULT_WATCH_DIR
        self.poll_interval = poll_interval
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._passes: list[dict[str, Any]] = []
        self._subscribers: list[Any] = []  # asyncio.Queue instances
        self._started_at: datetime | None = None
        self._session_id: str | None = None  # session ativa (pra persistir cada pass)

    # ------------- Controle de ciclo de vida
    def start(self, session_id: str | None = None) -> None:
        if self._thread and self._thread.is_alive():
            return
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        self._stop.clear()
        self._started_at = datetime.utcnow()
        self._session_id = session_id
        with self._lock:
            self._passes = []
        self._thread = threading.Thread(target=self._run, name="pass-watcher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        self._thread = None
        # Session permanece no banco; não mexe em _session_id aqui
        # (o router decide se encerra a session via end_live_session)

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------- Consulta
    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self.is_running(),
                "watch_dir": str(self.watch_dir),
                "started_at": self._started_at.isoformat() if self._started_at else None,
                "count": len(self._passes),
                "passes": list(self._passes),
            }

    # ------------- Pub/Sub para WebSocket
    def subscribe(self, queue) -> None:
        self._subscribers.append(queue)

    def unsubscribe(self, queue) -> None:
        try:
            self._subscribers.remove(queue)
        except ValueError:
            pass

    def _publish(self, message: dict[str, Any]) -> None:
        dead = []
        for q in self._subscribers:
            try:
                q.put_nowait(message)
            except Exception:
                dead.append(q)
        for q in dead:
            self.unsubscribe(q)

    # ------------- Loop principal
    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._scan_once()
            except Exception as e:  # noqa: BLE001 — watcher deve sobreviver a qualquer erro
                # evita parar por 1 arquivo corrompido
                print(f"[pass_watcher] erro no scan: {e}")
            self._stop.wait(self.poll_interval)

    def _scan_once(self) -> None:
        if not self.watch_dir.exists():
            return
        for fname in sorted(os.listdir(self.watch_dir)):
            if not fname.endswith(".json"):
                continue
            fpath = self.watch_dir / fname
            try:
                # se o arquivo ainda está sendo escrito, pula — pega no próximo ciclo
                if not _file_is_stable(fpath):
                    continue
                parsed = _parse_pass_file(fpath)
            except Exception as e:  # noqa: BLE001
                print(f"[pass_watcher] falha parseando {fname}: {e}")
                # renomeia pra .error pra não tentar de novo
                try:
                    fpath.rename(fpath.with_suffix(".json.error"))
                except OSError:
                    pass
                continue

            # trades já foram derivados dentro de _parse_pass_file
            trades = parsed.pop("_trades", [])

            with self._lock:
                self._passes.append(parsed)

            # Persiste no banco, se houver session ativa. No primeiro pass da
            # session, atualiza metadata ainda não preenchida (symbol, deposit).
            if self._session_id:
                try:
                    if len(self._passes) == 1:
                        storage.update_live_session_metadata(
                            self._session_id,
                            symbol=parsed.get("symbol"),
                            initial_deposit=parsed.get("initial_deposit"),
                        )
                    storage.add_pass_to_session(self._session_id, parsed, trades)
                except Exception as e:  # noqa: BLE001
                    print(f"[pass_watcher] falha ao persistir pass: {e}")

            self._publish({"event": "pass", "data": parsed})

            try:
                fpath.rename(fpath.with_suffix(".json.processed"))
            except OSError:
                pass


def _file_is_stable(fpath: Path, min_age_seconds: float = 0.5) -> bool:
    """Evita ler arquivo que o EA ainda está escrevendo."""
    try:
        st = fpath.stat()
    except OSError:
        return False
    return (time.time() - st.st_mtime) >= min_age_seconds


def _parse_pass_file(fpath: Path) -> dict[str, Any]:
    """Converte o JSON gravado pelo EA em {pass_id, parameters, metrics, trades}."""
    raw = json.loads(fpath.read_text(encoding="utf-8", errors="ignore"))

    trades = []
    for d in raw.get("deals", []):
        profit = float(d.get("profit", 0.0)) + float(d.get("swap", 0.0)) + float(d.get("commission", 0.0))
        trades.append({
            "time_in": d.get("time"),
            "time_out": d.get("time"),
            "side": "buy" if d.get("type") == 0 else "sell",
            "volume": float(d.get("volume", 0.0)),
            "entry_price": float(d.get("price", 0.0)),
            "exit_price": float(d.get("price", 0.0)),
            "profit": profit,
            "balance": 0.0,
            "duration_sec": 0,
        })

    initial = float(raw.get("initial_deposit", 10000.0))
    computed: dict[str, Any] = {}
    if trades:
        try:
            full = analytics.full_analysis(trades, initial)
            # Só manda de volta as métricas escalares (sem equity_curve gigante) pra UI
            for k in (
                "net_profit", "win_rate", "sharpe_ratio", "sortino_ratio", "calmar_ratio",
                "sqn", "k_ratio", "ulcer_index", "payoff_ratio", "recovery_factor",
                "expectancy", "annual_return_pct", "profit_factor", "max_drawdown_pct",
            ):
                if k in full:
                    computed[k] = full[k]
            # amostra da equity (pra eventual sparkline — no máximo 200 pontos)
            eq = full.get("equity_curve")
            if eq is not None:
                values = eq if isinstance(eq, list) else list(eq)
                if len(values) > 200:
                    step = max(1, len(values) // 200)
                    values = values[::step]
                computed["equity_sparkline"] = values
        except Exception as e:  # noqa: BLE001
            computed["_analytics_error"] = str(e)

    # métricas nativas do MT5 gravadas pelo EA (sanity check / fallback)
    native = {
        k: raw[k] for k in ("net_profit", "profit_factor", "expected_payoff", "sharpe_ratio", "trades_count")
        if k in raw
    }

    return {
        "pass_id": raw.get("pass_id"),
        "timestamp": raw.get("timestamp"),
        "symbol": raw.get("symbol"),
        "parameters": raw.get("parameters", {}),
        "initial_deposit": initial,
        "num_trades": len(trades),
        "native_metrics": native,
        "computed_metrics": computed,
        # Chave privada — removida antes de publicar via WS, só pra persistir no SQLite
        "_trades": trades,
    }


# Singleton compartilhado entre o router HTTP e o WebSocket
watcher = PassWatcher()
