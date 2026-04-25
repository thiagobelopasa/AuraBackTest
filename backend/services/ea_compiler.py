"""Compila arquivos .mq5 chamando o MetaEditor64.exe via CLI.

MetaEditor fica na mesma pasta do `terminal64.exe` da instalação.
Sintaxe:
    metaeditor64.exe /compile:"caminho\\completo\\arquivo.mq5" /log:"arquivo.log"

Retorna `CompileResult` com o código de saída e o log (tail) pra diagnóstico.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CompileResult:
    source_path: Path
    ex5_path: Path | None
    ok: bool
    return_code: int
    log_tail: str
    duration_seconds: float


def find_metaeditor(terminal_exe: str | Path) -> Path | None:
    """Tenta localizar o metaeditor64.exe ao lado do terminal64.exe."""
    terminal = Path(terminal_exe)
    candidates = [
        terminal.with_name("metaeditor64.exe"),
        terminal.with_name("MetaEditor64.exe"),  # Windows é case-insensitive mas documentamos
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def compile_ea(
    source_path: str | Path,
    metaeditor_exe: str | Path,
    include_dir: str | Path | None = None,
    timeout_seconds: int = 120,
) -> CompileResult:
    """Compila um .mq5 e retorna o resultado.

    Args:
        source_path: caminho absoluto do .mq5 a compilar.
        metaeditor_exe: caminho do metaeditor64.exe (use find_metaeditor).
        include_dir: opcional — MetaEditor já resolve includes relativos à
            pasta Include do data folder do terminal dono do exe, mas pode
            ser forçado aqui.
        timeout_seconds: limite pra evitar travar caso o processo encalhe.

    Returns:
        CompileResult com ok=True se o .ex5 foi gerado, False caso contrário.
    """
    import time

    src = Path(source_path)
    editor = Path(metaeditor_exe)
    if not src.exists():
        raise FileNotFoundError(f"Fonte não encontrada: {src}")
    if not editor.exists():
        raise FileNotFoundError(f"MetaEditor não encontrado: {editor}")

    log_path = src.with_suffix(".log")
    ex5_path = src.with_suffix(".ex5")
    # Remove .ex5 antigo pra detectar corretamente se a compilação gerou um novo
    if ex5_path.exists():
        try:
            ex5_path.unlink()
        except OSError:
            pass

    args = [str(editor), f"/compile:{src}", f"/log:{log_path}"]
    if include_dir:
        args.append(f"/include:{Path(include_dir)}")

    start = time.time()
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            creationflags=0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        return_code = proc.returncode
    except subprocess.TimeoutExpired:
        return_code = -1
    elapsed = time.time() - start

    log_tail = ""
    if log_path.exists():
        try:
            # Logs do MetaEditor saem em UTF-16 LE com BOM
            raw = log_path.read_bytes()
            for enc in ("utf-16", "utf-16-le", "utf-8", "cp1252"):
                try:
                    log_tail = raw.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
        except OSError:
            log_tail = ""

    ok = ex5_path.exists() and ex5_path.stat().st_size > 0
    return CompileResult(
        source_path=src,
        ex5_path=ex5_path if ok else None,
        ok=ok,
        return_code=return_code,
        log_tail=log_tail[-3000:],  # últimas ~3000 chars pra UI
        duration_seconds=round(elapsed, 2),
    )
