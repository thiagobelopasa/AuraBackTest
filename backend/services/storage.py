"""Persistência SQLite de runs, análises e otimizações.

Minimalista propositadamente — SQLite serve para histórico local single-user.
Se for virar multi-user no futuro, trocar por Postgres ainda é trivial.

Schema:
    runs              — cada execução (backtest single, optimization ou WFA)
    trades            — trades extraídos do report (1:N para runs)
    analyses          — snapshots de full_analysis por run
    monte_carlo_results — um por (run, mode, runs, seed)
    optimization_passes — N por optimization run
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any


def _resolve_db_path() -> Path:
    """DB mora em AURABACKTEST_DATA_DIR no app empacotado; em dev fica no backend/."""
    data_dir = os.environ.get("AURABACKTEST_DATA_DIR")
    if data_dir:
        root = Path(data_dir)
        root.mkdir(parents=True, exist_ok=True)
        return root / "aurabacktest.db"
    return Path(__file__).resolve().parent.parent / "aurabacktest.db"


_DB_PATH: Path = _resolve_db_path()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id            TEXT PRIMARY KEY,
    kind          TEXT NOT NULL,        -- 'single' | 'optimization' | 'wfa'
    ea_path       TEXT,
    symbol        TEXT,
    timeframe     TEXT,
    from_date     TEXT,
    to_date       TEXT,
    deposit       REAL,
    report_path   TEXT,
    parameters    TEXT,                 -- JSON
    metrics       TEXT,                 -- JSON (métricas do report/analytics)
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trades (
    run_id        TEXT NOT NULL,
    seq           INTEGER NOT NULL,
    time_in       TEXT,
    time_out      TEXT,
    symbol        TEXT,
    side          TEXT,
    volume        REAL,
    entry_price   REAL,
    exit_price    REAL,
    profit        REAL,
    balance       REAL,
    duration_sec  REAL,
    PRIMARY KEY (run_id, seq),
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS analyses (
    run_id        TEXT PRIMARY KEY,
    initial_equity REAL,
    result_json   TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS monte_carlo_results (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT NOT NULL,
    mode          TEXT NOT NULL,
    runs          INTEGER NOT NULL,
    seed          INTEGER,
    result_json   TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS optimization_passes (
    run_id        TEXT NOT NULL,
    pass_idx      INTEGER NOT NULL,
    parameters    TEXT NOT NULL,        -- JSON
    metrics       TEXT NOT NULL,        -- JSON
    PRIMARY KEY (run_id, pass_idx),
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_runs_created ON runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_kind ON runs(kind);

CREATE TABLE IF NOT EXISTS live_opt_sessions (
    id            TEXT PRIMARY KEY,
    robot_name    TEXT,
    symbol        TEXT,
    timeframe     TEXT,
    started_at    TEXT NOT NULL,
    ended_at      TEXT,
    initial_deposit REAL,
    label         TEXT,
    notes         TEXT
);

CREATE TABLE IF NOT EXISTS live_opt_passes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL,
    pass_id       TEXT,
    timestamp     TEXT,
    parameters    TEXT NOT NULL,   -- JSON
    native_metrics TEXT,           -- JSON
    computed_metrics TEXT,         -- JSON
    num_trades    INTEGER,
    trades_json   TEXT,            -- JSON (trades processados)
    FOREIGN KEY (session_id) REFERENCES live_opt_sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_live_sessions_started ON live_opt_sessions(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_live_passes_session ON live_opt_passes(session_id);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    """Migrações idempotentes para bancos antigos (ADD COLUMN se não existir)."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(runs)").fetchall()}
    for col, ddl in [
        ("label", "ALTER TABLE runs ADD COLUMN label TEXT"),
        ("params_hash", "ALTER TABLE runs ADD COLUMN params_hash TEXT"),
        ("favorite", "ALTER TABLE runs ADD COLUMN favorite INTEGER DEFAULT 0"),
        ("ticks_parquet_path", "ALTER TABLE runs ADD COLUMN ticks_parquet_path TEXT"),
    ]:
        if col not in cols:
            conn.execute(ddl)

    # Sessions table pode não existir em bancos muito antigos — ignora erro
    try:
        sess_cols = {r[1] for r in conn.execute("PRAGMA table_info(live_opt_sessions)").fetchall()}
        for col, ddl in [
            ("favorite", "ALTER TABLE live_opt_sessions ADD COLUMN favorite INTEGER DEFAULT 0"),
        ]:
            if sess_cols and col not in sess_cols:
                conn.execute(ddl)
    except sqlite3.OperationalError:
        pass


def init_db(path: Path | None = None) -> None:
    db = path or _DB_PATH
    with sqlite3.connect(db) as conn:
        conn.executescript(_SCHEMA)
        _migrate(conn)
        conn.commit()


@contextmanager
def connect(path: Path | None = None):
    db = path or _DB_PATH
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


# --------------------------------------------------------------------- runs
def _params_hash(parameters: dict[str, Any] | None) -> str:
    """Hash curto dos parâmetros — serve como 'impressão digital' do setup do robô.
    Diferencia configs quase iguais quando o nome/label é o mesmo."""
    import hashlib
    if not parameters:
        return ""
    canonical = json.dumps(parameters, sort_keys=True, default=str)
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:8]


def save_run(
    run_id: str,
    kind: str,
    ea_path: str | None,
    symbol: str | None,
    timeframe: str | None,
    from_date: str | None,
    to_date: str | None,
    deposit: float | None,
    report_path: str | None,
    parameters: dict[str, Any] | None,
    metrics: dict[str, Any] | None,
    label: str | None = None,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO runs
                (id, kind, ea_path, symbol, timeframe, from_date, to_date,
                 deposit, report_path, parameters, metrics, created_at,
                 label, params_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, kind, ea_path, symbol, timeframe, from_date, to_date,
                deposit, report_path,
                json.dumps(parameters or {}),
                json.dumps(metrics or {}),
                _now(),
                label, _params_hash(parameters),
            ),
        )


def update_run_label(run_id: str, label: str) -> bool:
    with connect() as conn:
        cur = conn.execute("UPDATE runs SET label=? WHERE id=?", (label, run_id))
        return cur.rowcount > 0


def set_run_favorite(run_id: str, favorite: bool) -> bool:
    with connect() as conn:
        cur = conn.execute(
            "UPDATE runs SET favorite=? WHERE id=?", (1 if favorite else 0, run_id)
        )
        return cur.rowcount > 0


def update_run_ticks_path(run_id: str, ticks_parquet_path: str) -> bool:
    with connect() as conn:
        cur = conn.execute(
            "UPDATE runs SET ticks_parquet_path=? WHERE id=?",
            (ticks_parquet_path, run_id),
        )
        return cur.rowcount > 0


def set_session_favorite(session_id: str, favorite: bool) -> bool:
    with connect() as conn:
        cur = conn.execute(
            "UPDATE live_opt_sessions SET favorite=? WHERE id=?",
            (1 if favorite else 0, session_id),
        )
        return cur.rowcount > 0


def list_runs(limit: int = 50, kind: str | None = None) -> list[dict[str, Any]]:
    with connect() as conn:
        if kind:
            cur = conn.execute(
                "SELECT * FROM runs WHERE kind=? ORDER BY created_at DESC LIMIT ?",
                (kind, limit),
            )
        else:
            cur = conn.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
            )
        return [dict(r) for r in cur.fetchall()]


def get_run(run_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        return dict(row) if row else None


def delete_run(run_id: str) -> bool:
    with connect() as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        cur = conn.execute("DELETE FROM runs WHERE id=?", (run_id,))
        return cur.rowcount > 0


# --------------------------------------------------------------------- trades
def save_trades(run_id: str, trades: list[dict[str, Any]]) -> None:
    if not trades:
        return
    with connect() as conn:
        conn.execute("DELETE FROM trades WHERE run_id=?", (run_id,))
        conn.executemany(
            """
            INSERT INTO trades
                (run_id, seq, time_in, time_out, symbol, side, volume,
                 entry_price, exit_price, profit, balance, duration_sec)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id, i,
                    t.get("time_in"), t.get("time_out"), t.get("symbol"),
                    t.get("side"), t.get("volume"),
                    t.get("entry_price"), t.get("exit_price"),
                    t.get("profit"), t.get("balance"), t.get("duration_sec"),
                )
                for i, t in enumerate(trades)
            ],
        )


def load_trades(run_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        cur = conn.execute(
            "SELECT * FROM trades WHERE run_id=? ORDER BY seq", (run_id,)
        )
        return [dict(r) for r in cur.fetchall()]


# --------------------------------------------------------------------- analysis
def save_analysis(run_id: str, initial_equity: float, result: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO analyses (run_id, initial_equity, result_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (run_id, initial_equity, json.dumps(result), _now()),
        )


def load_analysis(run_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM analyses WHERE run_id=?", (run_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["result"] = json.loads(d.pop("result_json"))
        return d


# --------------------------------------------------------------- monte_carlo
def save_monte_carlo(
    run_id: str, mode: str, runs: int, seed: int | None, result: dict[str, Any]
) -> int:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO monte_carlo_results (run_id, mode, runs, seed, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, mode, runs, seed, json.dumps(result), _now()),
        )
        return cur.lastrowid


def list_monte_carlo(run_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        cur = conn.execute(
            "SELECT * FROM monte_carlo_results WHERE run_id=? ORDER BY id DESC",
            (run_id,),
        )
        out = []
        for r in cur.fetchall():
            d = dict(r)
            d["result"] = json.loads(d.pop("result_json"))
            out.append(d)
        return out


# --------------------------------------------------------- optimization_passes
def save_optimization_passes(
    run_id: str, passes: list[tuple[int, dict[str, Any], dict[str, Any]]]
) -> None:
    """`passes`: lista de (pass_idx, parameters, metrics)."""
    if not passes:
        return
    with connect() as conn:
        conn.execute("DELETE FROM optimization_passes WHERE run_id=?", (run_id,))
        conn.executemany(
            """
            INSERT INTO optimization_passes (run_id, pass_idx, parameters, metrics)
            VALUES (?, ?, ?, ?)
            """,
            [
                (run_id, idx, json.dumps(params), json.dumps(metrics))
                for idx, params, metrics in passes
            ],
        )


def load_optimization_passes(run_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        cur = conn.execute(
            "SELECT * FROM optimization_passes WHERE run_id=? ORDER BY pass_idx",
            (run_id,),
        )
        out = []
        for r in cur.fetchall():
            d = dict(r)
            d["parameters"] = json.loads(d["parameters"])
            d["metrics"] = json.loads(d["metrics"])
            out.append(d)
        return out


# ----------------------------------------------------- live optimization sessions
def create_live_session(
    session_id: str,
    robot_name: str | None,
    symbol: str | None,
    timeframe: str | None,
    initial_deposit: float | None = None,
    label: str | None = None,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO live_opt_sessions
                (id, robot_name, symbol, timeframe, started_at,
                 initial_deposit, label)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, robot_name, symbol, timeframe, _now(),
             initial_deposit, label),
        )


def end_live_session(session_id: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE live_opt_sessions SET ended_at=? WHERE id=? AND ended_at IS NULL",
            (_now(), session_id),
        )


def update_live_session_metadata(
    session_id: str,
    robot_name: str | None = None,
    symbol: str | None = None,
    timeframe: str | None = None,
    initial_deposit: float | None = None,
) -> None:
    """Atualiza metadados da session se ainda não preenchidos (primeiro pass manda).

    Só sobrescreve campos NULL — não pisa em valores já gravados.
    """
    sets = []
    params: list[Any] = []
    for col, val in [
        ("robot_name", robot_name),
        ("symbol", symbol),
        ("timeframe", timeframe),
        ("initial_deposit", initial_deposit),
    ]:
        if val is not None:
            sets.append(f"{col} = COALESCE({col}, ?)")
            params.append(val)
    if not sets:
        return
    params.append(session_id)
    with connect() as conn:
        conn.execute(
            f"UPDATE live_opt_sessions SET {', '.join(sets)} WHERE id=?",
            params,
        )


def list_live_sessions(limit: int = 100) -> list[dict[str, Any]]:
    """Lista sessions com contagem de passes agregada."""
    with connect() as conn:
        cur = conn.execute(
            """
            SELECT s.*, COUNT(p.id) AS pass_count
            FROM live_opt_sessions s
            LEFT JOIN live_opt_passes p ON p.session_id = s.id
            GROUP BY s.id
            ORDER BY s.started_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]


def get_live_session(session_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM live_opt_sessions WHERE id=?", (session_id,)
        ).fetchone()
        return dict(row) if row else None


def delete_live_session(session_id: str) -> bool:
    with connect() as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        cur = conn.execute("DELETE FROM live_opt_sessions WHERE id=?", (session_id,))
        return cur.rowcount > 0


def add_pass_to_session(
    session_id: str,
    pass_data: dict[str, Any],
    trades: list[dict[str, Any]] | None = None,
) -> int:
    """Persiste um pass coletado. `pass_data` é o dict retornado pelo pass_watcher."""
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO live_opt_passes
                (session_id, pass_id, timestamp, parameters, native_metrics,
                 computed_metrics, num_trades, trades_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                pass_data.get("pass_id"),
                pass_data.get("timestamp"),
                json.dumps(pass_data.get("parameters") or {}),
                json.dumps(pass_data.get("native_metrics") or {}),
                json.dumps(pass_data.get("computed_metrics") or {}),
                pass_data.get("num_trades", 0),
                json.dumps(trades or []),
            ),
        )
        return cur.lastrowid


def load_session_passes(session_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        cur = conn.execute(
            "SELECT * FROM live_opt_passes WHERE session_id=? ORDER BY id",
            (session_id,),
        )
        out = []
        for r in cur.fetchall():
            d = dict(r)
            d["parameters"] = json.loads(d["parameters"]) if d["parameters"] else {}
            d["native_metrics"] = json.loads(d["native_metrics"]) if d["native_metrics"] else {}
            d["computed_metrics"] = json.loads(d["computed_metrics"]) if d["computed_metrics"] else {}
            d["trades"] = json.loads(d.pop("trades_json")) if d.get("trades_json") else []
            out.append(d)
        return out
