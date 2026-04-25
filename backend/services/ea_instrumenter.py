"""Auto-instrumenta um .mq5 para coletar trades de cada pass da otimização.

O cliente não precisa editar o código nem instalar includes: este módulo lê
o .mq5 original, injeta o coletor inline e gera um arquivo novo ao lado
(`<nome>_Aura.mq5`). O cliente usa essa versão no Strategy Tester e o
AuraBackTest captura cada pass em tempo real via `pass_watcher`.

Estratégia:
1. O código do coletor (equivalente ao .mqh em `mql5_include/`) é copiado
   como um bloco inline no topo do arquivo — sem dependência de biblioteca.
2. Se o EA já tem `OnTester()`, ele é renomeado para `_AuraUserOnTester`
   e um wrapper novo é criado que chama `AuraCollect(params)` antes de
   delegar para o original. Preserva qualquer critério customizado.
3. Se não tem `OnTester()`, um novo é criado que grava e retorna
   `TesterStatistics(STAT_COMPLEX_CRITERION)`.
4. Os inputs detectados pelo `mq5_parser` são enumerados no bloco de
   coleta de parâmetros (só tipos numéricos/bool — string/datetime/color
   ficam de fora pra evitar ambiguidade).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from models.schemas import EAInput, MQ5Type
from services.mq5_parser import parse_mq5, read_mq5_source


# Código do coletor inline (espelha mql5_include/AuraBackTestCollector.mqh).
# Qualquer alteração no .mqh precisa ser refletida aqui — ou refatorar depois
# pra ler o .mqh e colar.
_COLLECTOR_INLINE = r"""//+==== AURABACKTEST COLLECTOR (auto-gerado, não editar) ============+
#define AURA_DIR "AuraBackTest"

string AuraBuildPassId()
{
   ulong ms = (ulong)GetMicrosecondCount();
   return StringFormat("%I64u_%d", ms, MathRand());
}

void AuraAddParam(string &buf, string name, double value)
{
   if(StringLen(buf) > 0) buf += ",";
   buf += StringFormat("\"%s\":%.6f", name, value);
}
void AuraAddParam(string &buf, string name, long value)
{
   if(StringLen(buf) > 0) buf += ",";
   buf += StringFormat("\"%s\":%I64d", name, value);
}
void AuraAddParam(string &buf, string name, int value)
{
   if(StringLen(buf) > 0) buf += ",";
   buf += StringFormat("\"%s\":%d", name, value);
}
void AuraAddParam(string &buf, string name, bool value)
{
   if(StringLen(buf) > 0) buf += ",";
   buf += StringFormat("\"%s\":%s", name, value ? "true" : "false");
}

void AuraCollect(string parameters_json)
{
   string pass_id = AuraBuildPassId();
   string filename = AURA_DIR + "\\pass_" + pass_id + ".json";
   int h = FileOpen(filename, FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(h == INVALID_HANDLE)
   {
      PrintFormat("[AuraCollect] falha %s err=%d", filename, GetLastError());
      return;
   }
   FileWriteString(h, "{\n");
   FileWriteString(h, StringFormat("  \"pass_id\":\"%s\",\n", pass_id));
   FileWriteString(h, StringFormat("  \"timestamp\":\"%s\",\n",
      TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS)));
   FileWriteString(h, StringFormat("  \"symbol\":\"%s\",\n", _Symbol));
   FileWriteString(h, StringFormat("  \"period\":%d,\n", (int)_Period));
   FileWriteString(h, StringFormat("  \"initial_deposit\":%.2f,\n",
      TesterStatistics(STAT_INITIAL_DEPOSIT)));
   FileWriteString(h, StringFormat("  \"parameters\":{%s},\n", parameters_json));
   FileWriteString(h, StringFormat("  \"net_profit\":%.2f,\n", TesterStatistics(STAT_PROFIT)));
   FileWriteString(h, StringFormat("  \"profit_factor\":%.4f,\n",
      TesterStatistics(STAT_PROFIT_FACTOR)));
   FileWriteString(h, StringFormat("  \"expected_payoff\":%.4f,\n",
      TesterStatistics(STAT_EXPECTED_PAYOFF)));
   FileWriteString(h, StringFormat("  \"sharpe_ratio\":%.4f,\n",
      TesterStatistics(STAT_SHARPE_RATIO)));
   FileWriteString(h, StringFormat("  \"trades_count\":%d,\n",
      (int)TesterStatistics(STAT_TRADES)));
   HistorySelect(0, TimeCurrent());
   int total = HistoryDealsTotal();
   FileWriteString(h, "  \"deals\":[\n");
   bool first = true;
   for(int i=0; i<total; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY) continue;
      datetime t = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
      long type = HistoryDealGetInteger(ticket, DEAL_TYPE);
      double price = HistoryDealGetDouble(ticket, DEAL_PRICE);
      double volume = HistoryDealGetDouble(ticket, DEAL_VOLUME);
      double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
      double swap = HistoryDealGetDouble(ticket, DEAL_SWAP);
      double comm = HistoryDealGetDouble(ticket, DEAL_COMMISSION);
      if(!first) FileWriteString(h, ",\n");
      FileWriteString(h, StringFormat(
         "    {\"time\":\"%s\",\"type\":%d,\"price\":%.5f,\"volume\":%.2f,\"profit\":%.2f,\"swap\":%.2f,\"commission\":%.2f}",
         TimeToString(t, TIME_DATE|TIME_SECONDS), (int)type, price, volume, profit, swap, comm));
      first = false;
   }
   FileWriteString(h, "\n  ]\n}\n");
   FileClose(h);
}
//+==== FIM AURABACKTEST COLLECTOR =================================+
"""


@dataclass
class InstrumentationResult:
    source_path: Path
    output_path: Path
    output_name: str           # nome do EA como aparece no Navigator do MT5
    had_existing_on_tester: bool
    inputs_captured: list[str]
    inputs_skipped: list[str]  # tipos não suportados (string/datetime/color)


_SUPPORTED_TYPES = {MQ5Type.INT, MQ5Type.LONG, MQ5Type.DOUBLE, MQ5Type.BOOL}

# Detecta a assinatura "double OnTester()" mesmo com espaços/comentários inline.
_ON_TESTER_RE = re.compile(
    r"^\s*double\s+OnTester\s*\(\s*\)", re.MULTILINE
)


def instrument_ea(source_path: str | Path, suffix: str = "_Aura") -> InstrumentationResult:
    """Lê um .mq5 e gera uma cópia auto-instrumentada ao lado.

    Retorna os caminhos e quais inputs foram capturados. O arquivo de saída
    fica pronto pra ser compilado via `MetaEditor.exe /compile:`.
    """
    src = Path(source_path)
    if not src.exists():
        raise FileNotFoundError(f"EA não encontrado: {src}")
    if src.suffix.lower() != ".mq5":
        raise ValueError(f"Esperado .mq5, recebido: {src.suffix}")

    out_name = f"{src.stem}{suffix}"
    out_path = src.with_name(f"{out_name}.mq5")

    source = read_mq5_source(src)

    # Detecta inputs
    ea_def = parse_mq5(src)
    captured: list[EAInput] = []
    skipped: list[str] = []
    for inp in ea_def.inputs:
        if inp.type in _SUPPORTED_TYPES:
            captured.append(inp)
        else:
            skipped.append(inp.name)

    had_on_tester = bool(_ON_TESTER_RE.search(source))

    # Gera o bloco de chamadas AuraAddParam pra cada input suportado
    param_lines = "\n".join(
        f'   AuraAddParam(_aura_p, "{i.name}", {i.name});' for i in captured
    )
    if not param_lines:
        param_lines = "   // (nenhum input numérico detectado)"

    if had_on_tester:
        # Renomeia OnTester existente para _AuraUserOnTester e adiciona wrapper
        instrumented_source = _ON_TESTER_RE.sub(
            "double _AuraUserOnTester()", source, count=1
        )
        wrapper = f"""
//+==== AURABACKTEST OnTester wrapper (auto-gerado) =================+
double OnTester()
{{
   string _aura_p = "";
{param_lines}
   AuraCollect(_aura_p);
   return _AuraUserOnTester();
}}
//+==== FIM wrapper =================================================+
"""
    else:
        instrumented_source = source
        wrapper = f"""
//+==== AURABACKTEST OnTester (auto-gerado) =========================+
double OnTester()
{{
   string _aura_p = "";
{param_lines}
   AuraCollect(_aura_p);
   return TesterStatistics(STAT_COMPLEX_CRITERION);
}}
//+==== FIM OnTester ================================================+
"""

    # Monta o arquivo final: #property do original (header) + coletor + código + wrapper
    final = _inject_after_header(instrumented_source, _COLLECTOR_INLINE) + "\n" + wrapper

    # Remove qualquer BOM residual (defesa em profundidade) e garante UTF-8 sem BOM
    final = final.replace("﻿", "")
    out_path.write_bytes(final.encode("utf-8"))

    return InstrumentationResult(
        source_path=src,
        output_path=out_path,
        output_name=out_name,
        had_existing_on_tester=had_on_tester,
        inputs_captured=[i.name for i in captured],
        inputs_skipped=skipped,
    )


def _inject_after_header(source: str, block: str) -> str:
    """Insere `block` após o último #property/#include inicial do arquivo.

    Isso preserva metadados (`#property copyright`, `#property version`, etc)
    que o MetaEditor usa para exibir o EA no Navigator.
    """
    lines = source.splitlines(keepends=True)
    last_header_idx = -1
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("#property") or stripped.startswith("#include") or stripped.startswith("#import"):
            last_header_idx = i
        elif stripped.startswith("//") or stripped.startswith("/*") or stripped.strip() == "":
            # comentário ou linha vazia — aceita
            continue
        else:
            # primeira linha de código efetivo — para
            break
    insert_at = last_header_idx + 1 if last_header_idx >= 0 else 0
    return "".join(lines[:insert_at]) + "\n" + block + "\n" + "".join(lines[insert_at:])
