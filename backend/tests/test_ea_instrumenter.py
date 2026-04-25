"""Tests do auto-instrumenter de .mq5."""
from __future__ import annotations

from pathlib import Path

from services.ea_instrumenter import instrument_ea
from services.mq5_parser import parse_mq5, read_mq5_source


def test_parse_mq5_extracts_inputs(sample_mq5):
    ea = parse_mq5(sample_mq5)
    names = [i.name for i in ea.inputs]
    assert "InpLots" in names
    assert "InpStopLoss" in names
    assert "InpTakeProfit" in names
    assert "InpUseTrailing" in names
    # Tipos
    types = {i.name: i.type.value for i in ea.inputs}
    assert types["InpLots"] == "double"
    assert types["InpStopLoss"] == "int"
    assert types["InpUseTrailing"] == "bool"


def test_read_mq5_source_handles_utf8_bom(tmp_path):
    """Arquivos MT5 geralmente vêm com UTF-8 BOM — não devem deixar 0xFEFF no texto."""
    content = "#property strict\ninput int x = 1;"
    p = tmp_path / "bom.mq5"
    p.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))
    text = read_mq5_source(p)
    assert "﻿" not in text
    assert text.startswith("#property")


def test_read_mq5_source_handles_utf16(tmp_path):
    """MetaEditor às vezes salva em UTF-16 LE — deve ser decodificado."""
    content = "#property strict\ninput int x = 1;"
    p = tmp_path / "utf16.mq5"
    p.write_bytes(b"\xff\xfe" + content.encode("utf-16-le"))
    text = read_mq5_source(p)
    assert "﻿" not in text
    assert "#property strict" in text


def test_instrument_ea_creates_aura_file(sample_mq5):
    result = instrument_ea(sample_mq5)
    assert result.output_path.exists()
    assert result.output_path.name == "TesteEA_Aura.mq5"
    # Não deve ter BOM (causava "unknown symbol 0xFEFF" em compilação)
    raw = result.output_path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\xef\xbb\xbf" not in raw


def test_instrument_ea_captures_numeric_inputs(sample_mq5):
    result = instrument_ea(sample_mq5)
    assert "InpLots" in result.inputs_captured
    assert "InpStopLoss" in result.inputs_captured
    assert "InpUseTrailing" in result.inputs_captured
    # String é ignorado (tipo não suportado pelo AuraAddParam)
    assert "InpComment" in result.inputs_skipped


def test_instrument_ea_injects_on_tester(sample_mq5):
    result = instrument_ea(sample_mq5)
    content = result.output_path.read_text(encoding="utf-8")
    assert "double OnTester()" in content
    assert "AuraCollect(_aura_p)" in content
    assert "AURABACKTEST COLLECTOR" in content


def test_instrument_preserves_existing_on_tester(tmp_path):
    """Se o EA já tem OnTester, deve renomear pra _AuraUserOnTester e criar wrapper."""
    content = '''#property strict
input int x = 1;
double OnTester()
{
    return 42.0;
}
'''
    p = tmp_path / "HasTester.mq5"
    p.write_text(content, encoding="utf-8")
    result = instrument_ea(p)
    assert result.had_existing_on_tester
    out = result.output_path.read_text(encoding="utf-8")
    assert "_AuraUserOnTester" in out
    assert "return _AuraUserOnTester()" in out
