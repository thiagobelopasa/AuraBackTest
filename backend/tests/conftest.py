"""Fixtures compartilhadas dos testes."""
from __future__ import annotations

import sys
from pathlib import Path

# Permite importar services.* e routers.* nos testes sem precisar instalar o pacote
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import pytest


@pytest.fixture
def sample_trades() -> list[dict]:
    """Lista fixa de trades realistas pra testar analytics/robustness/pbo."""
    return [
        {"time_in": "2024-01-01 10:00:00", "time_out": "2024-01-01 11:00:00",
         "side": "buy", "volume": 0.1, "entry_price": 1.08, "exit_price": 1.085,
         "profit": 50.0, "balance": 10050.0, "duration_sec": 3600},
        {"time_in": "2024-01-02 10:00:00", "time_out": "2024-01-02 12:00:00",
         "side": "sell", "volume": 0.1, "entry_price": 1.09, "exit_price": 1.088,
         "profit": 20.0, "balance": 10070.0, "duration_sec": 7200},
        {"time_in": "2024-01-03 10:00:00", "time_out": "2024-01-03 11:00:00",
         "side": "buy", "volume": 0.1, "entry_price": 1.085, "exit_price": 1.080,
         "profit": -50.0, "balance": 10020.0, "duration_sec": 3600},
        {"time_in": "2024-01-04 10:00:00", "time_out": "2024-01-04 11:00:00",
         "side": "buy", "volume": 0.1, "entry_price": 1.080, "exit_price": 1.090,
         "profit": 100.0, "balance": 10120.0, "duration_sec": 3600},
        {"time_in": "2024-01-05 10:00:00", "time_out": "2024-01-05 11:00:00",
         "side": "sell", "volume": 0.1, "entry_price": 1.090, "exit_price": 1.100,
         "profit": -100.0, "balance": 10020.0, "duration_sec": 3600},
        {"time_in": "2024-01-06 10:00:00", "time_out": "2024-01-06 11:00:00",
         "side": "buy", "volume": 0.1, "entry_price": 1.100, "exit_price": 1.110,
         "profit": 100.0, "balance": 10120.0, "duration_sec": 3600},
        {"time_in": "2024-01-07 10:00:00", "time_out": "2024-01-07 11:00:00",
         "side": "buy", "volume": 0.1, "entry_price": 1.110, "exit_price": 1.115,
         "profit": 50.0, "balance": 10170.0, "duration_sec": 3600},
    ]


@pytest.fixture
def sample_mq5(tmp_path) -> Path:
    """Cria um arquivo .mq5 mínimo pra testar parser e instrumenter."""
    content = '''//+------------------------------------------------------------------+
//|                                                      TesteEA.mq5 |
//+------------------------------------------------------------------+
#property strict
#property version   "1.00"

input double InpLots = 0.1;           // Tamanho do lote
input int    InpStopLoss = 50;        // Stop Loss em pontos
input int    InpTakeProfit = 100;     // Take Profit em pontos
input bool   InpUseTrailing = true;   // Ativar trailing
input string InpComment = "teste";    // Comentário

int OnInit() { return INIT_SUCCEEDED; }
void OnTick() { }
void OnDeinit(const int reason) { }
'''
    p = tmp_path / "TesteEA.mq5"
    p.write_text(content, encoding="utf-8")
    return p
