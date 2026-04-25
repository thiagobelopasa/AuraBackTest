"""Rotas relacionadas ao Expert Advisor (EA) — parse de .mq5 e auto-instrumentação."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models.schemas import EADefinition
from services.ea_compiler import compile_ea, find_metaeditor
from services.ea_instrumenter import instrument_ea
from services.mq5_parser import parse_mq5


router = APIRouter(prefix="/ea", tags=["ea"])


class ParseRequest(BaseModel):
    path: str


@router.post("/parse", response_model=EADefinition)
def parse_ea(req: ParseRequest) -> EADefinition:
    """Lê um arquivo .mq5 e retorna seus inputs."""
    path = Path(req.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Arquivo não encontrado: {path}")
    if path.suffix.lower() != ".mq5":
        raise HTTPException(
            status_code=400,
            detail=f"Extensão inválida: esperado .mq5, recebido {path.suffix}",
        )
    return parse_mq5(path)


class InstrumentRequest(BaseModel):
    ea_path: str                    # caminho absoluto do .mq5 original
    terminal_exe: str               # caminho do terminal64.exe da instalação alvo
    suffix: str = "_Aura"           # sufixo do nome do arquivo gerado
    compile_after: bool = True      # se True, chama MetaEditor pra compilar


class InstrumentResponse(BaseModel):
    output_path: str                # .mq5 gerado
    output_name: str                # nome pra exibir (usuário seleciona no Navigator MT5)
    ex5_path: str | None            # caminho do .ex5 compilado (se compile_after=True e ok)
    inputs_captured: list[str]
    inputs_skipped: list[str]
    had_existing_on_tester: bool
    compiled: bool
    compile_log_tail: str


@router.post("/instrument", response_model=InstrumentResponse)
def instrument_and_compile(req: InstrumentRequest) -> InstrumentResponse:
    """Auto-instrumenta um .mq5 e (opcionalmente) compila via MetaEditor.

    O cliente só precisa:
      1. Selecionar o EA dele (caminho do .mq5)
      2. Selecionar a instalação MT5 alvo
      3. Chamar esse endpoint
    Resultado: um novo .ex5 fica disponível no Navigator do MT5 com o nome
    `<original>_Aura`. O cliente usa essa versão no Strategy Tester e o
    pass_watcher captura cada pass em tempo real.
    """
    src = Path(req.ea_path)
    if not src.exists():
        raise HTTPException(404, f"EA não encontrado: {src}")

    try:
        instr = instrument_ea(src, suffix=req.suffix)
    except Exception as e:
        raise HTTPException(500, f"Falha ao instrumentar: {e}") from e

    compiled = False
    compile_log = ""
    ex5_path: str | None = None

    if req.compile_after:
        editor = find_metaeditor(req.terminal_exe)
        if not editor:
            raise HTTPException(
                404,
                f"metaeditor64.exe não encontrado ao lado de {req.terminal_exe}",
            )
        try:
            result = compile_ea(instr.output_path, editor)
        except Exception as e:
            raise HTTPException(500, f"Falha ao compilar: {e}") from e
        compiled = result.ok
        compile_log = result.log_tail
        ex5_path = str(result.ex5_path) if result.ex5_path else None

    return InstrumentResponse(
        output_path=str(instr.output_path),
        output_name=instr.output_name,
        ex5_path=ex5_path,
        inputs_captured=instr.inputs_captured,
        inputs_skipped=instr.inputs_skipped,
        had_existing_on_tester=instr.had_existing_on_tester,
        compiled=compiled,
        compile_log_tail=compile_log,
    )
