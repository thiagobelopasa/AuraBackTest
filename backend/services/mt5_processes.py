"""Detecção de processos MT5 rodando no sistema + casamento com instalações.

Varre os processos com `psutil` procurando `terminal64.exe` e `metaeditor64.exe`
e casa o caminho do executável com as instalações detectadas pelo `mt5_env`.

Útil para:
- Destacar no UI qual MT5 está "ativo" agora
- Detectar quando o Strategy Tester está aberto (processo rodando)
- Evitar que o usuário precise escolher instalação manualmente quando só um MT5 está aberto
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil

from services import mt5_env


@dataclass
class RunningMT5:
    pid: int
    terminal_exe: str
    data_folder: str | None        # casado via mt5_env.detect_installations
    label: str                     # nome amigável (pasta do exe)
    started_at: float              # unix timestamp de start do processo
    has_editor_open: bool          # True se metaeditor64.exe do mesmo path tb roda


def detect_running_mt5() -> list[RunningMT5]:
    """Lista MT5s atualmente rodando, casando com instalações conhecidas."""
    # Indexa instalações por caminho do exe pra casar rapidamente
    installs = {str(i.terminal_exe): i for i in mt5_env.detect_installations()}

    # Coleta terminal64.exe e metaeditor64.exe separadamente
    terminals: list[tuple[psutil.Process, Path]] = []
    editor_paths: set[str] = set()
    for proc in psutil.process_iter(["name", "exe", "pid", "create_time"]):
        try:
            name = (proc.info.get("name") or "").lower()
            exe = proc.info.get("exe") or ""
            if not exe:
                continue
            if name == "terminal64.exe":
                terminals.append((proc, Path(exe)))
            elif name == "metaeditor64.exe":
                editor_paths.add(str(Path(exe).parent))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    out: list[RunningMT5] = []
    for proc, exe_path in terminals:
        exe_str = str(exe_path)
        install = installs.get(exe_str)
        out.append(RunningMT5(
            pid=proc.info["pid"],
            terminal_exe=exe_str,
            data_folder=str(install.data_folder) if install else None,
            label=install.label if install else exe_path.parent.name,
            started_at=proc.info.get("create_time") or 0.0,
            has_editor_open=str(exe_path.parent) in editor_paths,
        ))
    return out


def active_mt5() -> RunningMT5 | None:
    """Retorna um único MT5 "ativo" se houver apenas um rodando.

    Se houver múltiplos, retorna None — o UI pede pro usuário escolher.
    Se não houver nenhum, retorna None.
    """
    running = detect_running_mt5()
    if len(running) == 1:
        return running[0]
    return None


def as_dict(r: RunningMT5) -> dict[str, Any]:
    return {
        "pid": r.pid,
        "terminal_exe": r.terminal_exe,
        "data_folder": r.data_folder,
        "label": r.label,
        "started_at": r.started_at,
        "has_editor_open": r.has_editor_open,
    }
