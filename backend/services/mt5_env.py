"""Auto-detecção de instalações do MetaTrader 5 no Windows.

Locais conhecidos:
- Executável: `C:\\Program Files\\<Broker ou MetaTrader 5>\\terminal64.exe`
- Data folder: `%APPDATA%\\MetaQuotes\\Terminal\\<hash>\\` (nome = 32 chars hex)

Cada data folder contém um `origin.txt` em UTF-16 com o caminho da pasta
do executável que o criou — usamos isso para casar exe ↔ data folder.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MT5Installation:
    terminal_exe: Path
    data_folder: Path

    @property
    def label(self) -> str:
        """Nome amigável: pasta do executável (normalmente o broker/versão)."""
        return self.terminal_exe.parent.name

    @property
    def experts_dir(self) -> Path:
        return self.data_folder / "MQL5" / "Experts"


@dataclass
class ExpertFile:
    """Arquivo .mq5 ou .ex5 dentro de MQL5/Experts."""
    absolute_path: Path
    relative_path: str   # ex: 'RPAlgo/Big-Small' (sem extensão, forward-slash)
    extension: str       # 'mq5' ou 'ex5'
    size_bytes: int
    has_source: bool     # True se existe .mq5 correspondente


def _list_data_folders() -> list[Path]:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return []
    base = Path(appdata) / "MetaQuotes" / "Terminal"
    if not base.exists():
        return []
    # Nomes de data folder do MT5 são hashes de 32 caracteres hex uppercase.
    return [p for p in base.iterdir() if p.is_dir() and len(p.name) == 32]


def _find_terminal_exes() -> list[Path]:
    roots = [
        Path(r"C:\Program Files"),
        Path(r"C:\Program Files (x86)"),
    ]
    exes: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for d in root.iterdir():
            if not d.is_dir():
                continue
            exe = d / "terminal64.exe"
            if exe.exists():
                exes.append(exe)
    return exes


def _read_origin(data_folder: Path) -> Path | None:
    origin_file = data_folder / "origin.txt"
    if not origin_file.exists():
        return None
    for enc in ("utf-16", "utf-16-le", "utf-8", "cp1252"):
        try:
            txt = origin_file.read_text(encoding=enc).strip()
            if txt:
                return Path(txt)
        except UnicodeError:
            continue
    return None


def detect_installations() -> list[MT5Installation]:
    """Retorna instalações MT5 prováveis, cruzando data folders com executáveis."""
    data_folders = _list_data_folders()
    exes = _find_terminal_exes()

    installations: list[MT5Installation] = []
    for folder in data_folders:
        origin = _read_origin(folder)
        matched: Path | None = None
        if origin is not None:
            origin_exe = origin / "terminal64.exe"
            if origin_exe.exists():
                matched = origin_exe
            else:
                # origin aponta para pasta; procurar exe dentro dela
                for exe in exes:
                    try:
                        if exe.parent.resolve() == origin.resolve():
                            matched = exe
                            break
                    except OSError:
                        continue
        if matched is None and len(exes) == 1:
            matched = exes[0]
        if matched is not None:
            installations.append(
                MT5Installation(terminal_exe=matched, data_folder=folder)
            )
    return installations


def list_experts(data_folder: Path, include_compiled: bool = True) -> list[ExpertFile]:
    """Varre `data_folder/MQL5/Experts/` em busca de .mq5 e .ex5.

    - `.mq5` é o código-fonte; pode ser compilado e otimizado.
    - `.ex5` é o compilado; pode ser rodado mesmo sem fonte (robôs comerciais).
    Quando ambos existem com o mesmo nome, preferimos o .mq5.
    """
    experts_root = Path(data_folder) / "MQL5" / "Experts"
    if not experts_root.exists():
        return []

    mq5_files = list(experts_root.rglob("*.mq5"))
    ex5_files = list(experts_root.rglob("*.ex5")) if include_compiled else []

    # Mapa por caminho-sem-extensão para detectar duplicatas mq5/ex5
    mq5_stems = {f.with_suffix("").as_posix() for f in mq5_files}

    results: list[ExpertFile] = []
    for f in mq5_files:
        rel = f.relative_to(experts_root).with_suffix("").as_posix()
        try:
            size = f.stat().st_size
        except OSError:
            size = 0
        results.append(
            ExpertFile(
                absolute_path=f,
                relative_path=rel,
                extension="mq5",
                size_bytes=size,
                has_source=True,
            )
        )
    for f in ex5_files:
        stem = f.with_suffix("").as_posix()
        if stem in mq5_stems:
            continue  # já listado como .mq5
        rel = f.relative_to(experts_root).with_suffix("").as_posix()
        try:
            size = f.stat().st_size
        except OSError:
            size = 0
        results.append(
            ExpertFile(
                absolute_path=f,
                relative_path=rel,
                extension="ex5",
                size_bytes=size,
                has_source=False,
            )
        )

    results.sort(key=lambda e: e.relative_path.lower())
    return results
