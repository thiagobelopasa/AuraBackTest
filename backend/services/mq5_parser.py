"""Parser leve de inputs de arquivos .mq5.

Extrai declarações `input` e `sinput`, identificando nome, tipo, default e
comentário. Não executa o código — só interpreta declarações sintáticas.

Tipos não-numéricos (string, color, datetime, ulong) são marcados como
non-optimizable por padrão — o usuário pode forçar otimização manualmente.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from models.schemas import EADefinition, EAInput, MQ5Type


# Regex explicada:
#   ^\s*(?:s?input)\s+         -> 'input' ou 'sinput' no início da linha
#   (?P<type>int|long|ulong|double|bool|string|datetime|color)\s+
#   (?P<name>\w+)              -> identificador
#   (?:\s*=\s*(?P<default>[^;/]+?))?   -> default opcional, até ; ou //
#   \s*;                        -> fim da declaração
#   (?:[ \t]*//[ \t]*(?P<comment>[^\r\n]*))? -> comentário inline opcional
#       (precisa estar na MESMA linha do ';' — por isso só aceita espaço/tab)
_INPUT_RE = re.compile(
    r"""
    ^[ \t]*
    (?:s?input)[ \t]+
    (?P<type>int|long|ulong|double|bool|string|datetime|color)[ \t]+
    (?P<name>\w+)
    (?:[ \t]*=[ \t]*(?P<default>[^;/\r\n]+?))?
    [ \t]*;
    (?:[ \t]*//[ \t]*(?P<comment>[^\r\n]*))?
    """,
    re.VERBOSE | re.MULTILINE,
)

_NON_OPTIMIZABLE_TYPES = {MQ5Type.STRING, MQ5Type.COLOR, MQ5Type.DATETIME, MQ5Type.ULONG}


def read_mq5_source(path: str | Path) -> str:
    """Lê um .mq5 detectando encoding (UTF-16 LE/BE, UTF-8 BOM, cp1252).

    MetaEditor salva em encodings variados conforme como o EA foi criado.
    Normaliza removendo BOMs — MQL5 não aceita 0xFEFF literal no código
    e o compilador retorna `error 110: unknown symbol '' (0xFEFF)`.
    """
    raw = Path(path).read_bytes()
    if raw.startswith(b"\xff\xfe"):
        text = raw[2:].decode("utf-16-le", errors="replace")
    elif raw.startswith(b"\xfe\xff"):
        text = raw[2:].decode("utf-16-be", errors="replace")
    elif raw.startswith(b"\xef\xbb\xbf"):
        text = raw[3:].decode("utf-8", errors="replace")
    else:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("cp1252", errors="replace")
    return text.replace("﻿", "")


def _coerce(raw: str, mql_type: MQ5Type) -> Any:
    v = raw.strip()
    if mql_type in (MQ5Type.INT, MQ5Type.LONG, MQ5Type.ULONG):
        # remove sufixos MQL5 comuns (L, U)
        v = v.rstrip("LlUu")
        try:
            return int(v)
        except ValueError:
            return v  # deixa como string se não for literal numérico
    if mql_type == MQ5Type.DOUBLE:
        try:
            return float(v)
        except ValueError:
            return v
    if mql_type == MQ5Type.BOOL:
        return v.lower() == "true"
    if mql_type == MQ5Type.STRING:
        return v.strip('"')
    return v  # datetime/color -> string literal


def parse_mq5(path: str | Path) -> EADefinition:
    """Lê um .mq5 e retorna sua definição com todos os inputs encontrados."""
    path = Path(path)
    source = read_mq5_source(path)

    # remove comentários de bloco /* ... */ para não enganar o matcher
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)

    seen: set[str] = set()
    inputs: list[EAInput] = []
    for m in _INPUT_RE.finditer(source):
        name = m.group("name")
        if name in seen:
            continue
        seen.add(name)

        mql_type = MQ5Type(m.group("type"))
        raw_default = (m.group("default") or "").strip()
        default = _coerce(raw_default, mql_type) if raw_default else None
        comment = (m.group("comment") or "").strip() or None

        inputs.append(
            EAInput(
                name=name,
                type=mql_type,
                default=default,
                comment=comment,
                optimizable=mql_type not in _NON_OPTIMIZABLE_TYPES,
            )
        )

    return EADefinition(file_path=str(path), inputs=inputs)
