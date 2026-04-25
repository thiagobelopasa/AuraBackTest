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

            # Filtra passes inúteis: prejuízo líquido ou DD excessivo
            cm = parsed.get("computed_metrics", {})
            net_profit = cm.get("net_profit")
            max_dd = cm.get("max_drawdown_pct")
            if (net_profit is not None and net_profit <= 0) or \
               (max_dd is not None and max_dd > 50):
                try:
                    fpath.rename(fpath.with_suffix(".json.filtered"))
                except OSError:
                    pass
                continue

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


_DT_FMT = "%Y.%m.%d %H:%M:%S"

# DEAL_ENTRY constants (MT5)
_ENTRY_IN = 0
_ENTRY_OUT = 1
_ENTRY_INOUT = 2
_ENTRY_OUT_BY = 3


def _duration_sec(time_in: str | None, time_out: str | None) -> int:
    if not time_in or not time_out:
        return 0
    try:
        return max(0, int((datetime.strptime(time_out, _DT_FMT) - datetime.strptime(time_in, _DT_FMT)).total_seconds()))
    except ValueError:
        return 0


def _deals_to_trades(deals: list[dict]) -> list[dict]:
    """Constrói trades round-trip a partir de deals MT5.

    Formato novo (>= v2): cada deal tem position_id + entry (0=IN, 1=OUT).
    Formato legado (v1):  só deals OUT, sem position_id/entry — fallback direto.
    """
    has_position_id = any("position_id" in d for d in deals)

    if has_position_id:
        # Agrupa por position_id e pareia IN↔OUT
        positions: dict[int, dict] = {}
        for d in deals:
            pid = int(d.get("position_id", 0))
            entry = int(d.get("entry", -1))
            if entry == _ENTRY_IN:
                positions.setdefault(pid, {})["in"] = d
            elif entry in (_ENTRY_OUT, _ENTRY_OUT_BY):
                positions.setdefault(pid, {})["out"] = d
            elif entry == _ENTRY_INOUT:
                # Reversão: trata como fechamento da posição anterior
                positions.setdefault(pid, {})["out"] = d

        trades = []
        for sides in positions.values():
            out_deal = sides.get("out")
            if out_deal is None:
                continue  # posição não fechada — ignora
            in_deal = sides.get("in")

            profit = (float(out_deal.get("profit", 0.0))
                      + float(out_deal.get("swap", 0.0))
                      + float(out_deal.get("commission", 0.0)))
            # IN deal type=0 → buy (long), type=1 → sell (short)
            in_type = int(in_deal.get("type", 0)) if in_deal else None
            out_type = int(out_deal.get("type", 0))
            if in_type is not None:
                side = "buy" if in_type == 0 else "sell"
            else:
                # legado sem IN: tipo no OUT é invertido (sell fecha buy)
                side = "sell" if out_type == 0 else "buy"

            time_in = in_deal.get("time") if in_deal else out_deal.get("time")
            time_out = out_deal.get("time")
            entry_price = float(in_deal.get("price", 0.0)) if in_deal else float(out_deal.get("price", 0.0))
            exit_price = float(out_deal.get("price", 0.0))
            volume = float(out_deal.get("volume", 0.0))

            trades.append({
                "time_in": time_in,
                "time_out": time_out,
                "side": side,
                "volume": volume,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "profit": profit,
                "balance": 0.0,
                "duration_sec": _duration_sec(time_in, time_out),
            })
        return trades

    # Formato legado: só deals OUT sem position_id
    trades = []
    for d in deals:
        profit = float(d.get("profit", 0.0)) + float(d.get("swap", 0.0)) + float(d.get("commission", 0.0))
        out_type = int(d.get("type", 0))
        # OUT deal tipo=1 (DEAL_TYPE_SELL) fecha BUY → side="buy"
        side = "sell" if out_type == 0 else "buy"
        t = d.get("time")
        trades.append({
            "time_in": t,
            "time_out": t,
            "side": side,
            "volume": float(d.get("volume", 0.0)),
            "entry_price": float(d.get("price", 0.0)),
            "exit_price": float(d.get("price", 0.0)),
            "profit": profit,
            "balance": 0.0,
            "duration_sec": 0,
        })
    return trades


def _parse_pass_file(fpath: Path) -> dict[str, Any]:
    """Converte o JSON gravado pelo EA em {pass_id, parameters, metrics, trades}."""
    raw = json.loads(fpath.read_text(encoding="utf-8", errors="ignore"))

    deals = raw.get("deals", [])
    trades = _deals_to_trades(deals)

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
