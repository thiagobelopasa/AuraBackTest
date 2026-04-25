# Pipeline de implementação — Funcionalidades inspiradas no QuantAnalyzer 4

> Paste este arquivo inteiro numa nova janela do Claude Code (com o projeto AuraBackTest aberto)
> e peça: **"Execute este pipeline fase por fase, confirmando cada fase comigo antes de avançar."**

---

## Contexto do projeto

- **Backend:** FastAPI em `backend/`, serviço de análise em `backend/services/analytics.py`
- **Frontend:** React + Vite em `frontend/src/`, página principal de análise em `frontend/src/pages/AnalysisPage.jsx`
- **Dados de trade:** cada trade tem campos `time_in`, `time_out`, `side` ("buy"/"sell"), `profit`, `volume`, `balance`, `duration_sec`, `entry_price`, `exit_price`
- **Stack de gráficos:** Recharts (já em uso). Não usar Plotly exceto no Planet3D já existente.
- **Estilo:** usar as classes CSS já existentes (`.card`, `.kpi`, `.grid`, `.row`, `.pill`, `.muted`, `.small`, `.errbox`). Não criar novos arquivos CSS.

---

## FASE 1 — P/L por Hora / Weekday / Mês (heat map temporal)

### O que é
Mostra em quais horas do dia, dias da semana e meses do ano a estratégia ganha ou perde. Essencial para detectar "o robô perde toda segunda-feira" ou "só funciona de manhã".

### Backend — adicionar em `backend/services/analytics.py`

Criar função `time_breakdown(trades)` que retorna:
```python
{
  "by_hour":    [ { "hour": 0..23, "net_profit": float, "trades": int, "win_rate": float } ],
  "by_weekday": [ { "weekday": "Mon".."Sun", "weekday_num": 0..6, "net_profit": float, "trades": int, "win_rate": float } ],
  "by_month":   [ { "month": "Jan".."Dec", "month_num": 1..12, "net_profit": float, "trades": int, "win_rate": float } ],
  "by_year":    [ { "year": int, "net_profit": float, "trades": int, "win_rate": float, "max_dd_pct": float, "sharpe_annual": float } ],
}
```

Usar `time_out` do trade para extrair hora, weekday, mês. Agregar profit e contagem.

Adicionar `time_breakdown` ao retorno de `full_analysis()` com chave `"time_breakdown"`.

### Backend — novo endpoint em `backend/routers/analysis.py`

```
GET /analysis/runs/{run_id}/time-breakdown
```
Retorna o `time_breakdown` do `full_analysis` salvo, ou recalcula se necessário.

### Frontend — novo componente `frontend/src/components/TimeBreakdown.jsx`

- Três seções: por Hora (barras 0-23), por Dia da Semana (barras Seg-Dom), por Mês (barras Jan-Dez)
- Cada barra colorida: verde se `net_profit > 0`, vermelho se `< 0`. Intensidade proporcional ao valor.
- Tooltip: Net Profit, Trades, Win Rate
- Usar `BarChart` do Recharts
- Adicionar como nova seção na `AnalysisPage.jsx`, abaixo do gráfico de Drawdown, com título "Análise Temporal"

---

## FASE 2 — MAE / MFE (Maximum Adverse/Favorable Excursion)

### O que é
Scatter plot que mostra para cada trade: quanto o trade foi contra você antes de fechar (MAE = adverse) e quanto ele chegou a seu favor antes de fechar (MFE = favorable). Revela se o SL/TP está bem calibrado.

### Dados disponíveis
Os trades MT5 têm `entry_price` e `exit_price` mas **não têm** MAE/MFE diretamente — o MT5 não exporta isso no relatório HTML padrão. 

**Solução:** Usar o profit como proxy. Calcular:
- `mae_proxy`: para trades perdedores, o loss é o MAE. Para vencedores, estimar 0 (não temos dados intrabar).
- `mfe_proxy`: para trades vencedores, o profit é o MFE. Para perdedores, estimar 0.
- Mostrar scatter de `profit` vs `duration_sec`, colorido por lado (buy/sell).

### Backend — adicionar em `analytics.py`

Criar função `mae_mfe_data(trades)` que retorna lista de pontos para scatter:
```python
[{
  "trade_num": int,
  "profit": float,
  "duration_sec": float,
  "side": "buy" | "sell",
  "is_win": bool,
  "r_multiple": float,  # profit / abs(avg_loss) — normaliza pelo risco médio
}]
```
Adicionar `"mae_mfe": mae_mfe_data(trades)` no retorno de `full_analysis()`.

### Frontend — novo componente `frontend/src/components/MaeMfe.jsx`

- ScatterChart do Recharts: eixo X = duração (minutos), eixo Y = profit
- Pontos: verde (wins), vermelho (losses), símbolo diferente para buy vs sell
- Linha horizontal em Y=0
- Tooltip com: Trade #, Profit, Duração, Lado
- Segunda aba com histograma de R-multiple (distribuição dos lucros normalizados)
- Adicionar seção "MAE / MFE" na `AnalysisPage.jsx`

---

## FASE 3 — Long vs Short (breakdown por direção)

### O que é
Métricas separadas para trades comprados (buy) e vendidos (sell). Detecta se o robô só funciona num sentido.

### Backend

Adicionar em `basic_trade_stats()` (ou criar `direction_stats(trades)`) retornando:
```python
{
  "long": { "trades": int, "net_profit": float, "win_rate": float, "avg_win": float, "avg_loss": float, "profit_factor": float },
  "short": { "trades": int, "net_profit": float, "win_rate": float, "avg_win": float, "avg_loss": float, "profit_factor": float },
}
```
Filtrar por `trade["side"] in ("buy", "long")` para long, `("sell", "short")` para short.
Adicionar `"direction": direction_stats(trades)` em `full_analysis()`.

### Frontend

Adicionar seção "Long vs Short" na `AnalysisPage.jsx` com dois cards lado a lado:
- Cada card mostra: Trades, Net Profit, Win Rate, Profit Factor, Avg Win, Avg Loss
- Badge colorido: verde/vermelho para Net Profit de cada lado
- Barra comparativa de Trades (long vs short) usando `BarChart`

---

## FASE 4 — Risk of Ruin table

### O que é
Tabela mostrando, para diferentes tamanhos de capital inicial, qual a probabilidade estatística de ruína (conta vai a zero). Fórmula clássica de Vince/Ryan Jones.

### Backend — adicionar em `backend/services/analytics.py`

```python
def risk_of_ruin_table(win_rate: float, payoff_ratio: float, risk_pct_per_trade: float = 0.02) -> list[dict]:
    """
    Retorna lista de { "risk_pct": float, "ruin_probability": float }
    para diferentes % de risco por trade (0.5%, 1%, 2%, 3%, 5%, 10%).
    
    Fórmula: RoR = ((1 - edge) / (1 + edge)) ^ (capital / risk_per_trade)
    onde edge = win_rate * payoff_ratio - (1 - win_rate)
    """
```

Também calcular `ruin_probability` para o risco atual do usuário.
Adicionar `"risk_of_ruin": risk_of_ruin_table(win_rate, payoff_ratio)` em `full_analysis()`.

### Frontend

Adicionar seção "Risk of Ruin" na `AnalysisPage.jsx`:
- Tabela com colunas: % Risco por Trade | Prob. de Ruína
- Colorir fundo: verde (<5%), amarelo (5-20%), vermelho (>20%)
- Texto explicativo: "Probabilidade de perder todo o capital com N trades consecutivos"

---

## FASE 5 — What-If Analysis

### O que é
Simula como seria a performance se você NÃO tivesse operado em certas horas ou dias da semana. Útil para otimizar horário de trading sem re-rodar o backtest.

### Backend — novo arquivo `backend/services/whatif.py`

```python
def apply_whatif(trades: list[dict], excluded_hours: list[int] = [], excluded_weekdays: list[int] = []) -> dict:
    """
    Filtra trades que abriram em horas/dias excluídos e recalcula full_analysis.
    Retorna { "original": metrics, "whatif": metrics, "excluded_trades": int }
    """
```

### Backend — novo endpoint em `backend/routers/analysis.py`

```
POST /analysis/runs/{run_id}/whatif
Body: { "excluded_hours": [0,1,2], "excluded_weekdays": [0,5,6] }  # 0=Monday, 6=Sunday
Response: { "original": {...metrics}, "whatif": {...metrics}, "excluded_trades": int }
```

### Frontend — nova página `frontend/src/pages/WhatIfPage.jsx`

- Selector de run (igual AnalysisPage)
- Grid de checkboxes de horas (0-23) — marcado = excluído
- Grid de checkboxes dias da semana — marcado = excluído
- Botão "Simular"
- Resultado: dois cards lado a lado (Original vs What-If) com KPIs principais: Net Profit, Sharpe, DD%, Win Rate, Trades
- Setas coloridas indicando melhora/piora
- Adicionar aba "What-If" na navegação do `App.jsx`

---

## FASE 6 — Money Management Simulator

### O que é
Simula como a mesma estratégia teria performado com diferentes regras de dimensionamento de posição. Compara "Fixed Lots" vs "Risk X% do capital por trade" lado a lado.

### Backend — novo arquivo `backend/services/mm_simulator.py`

```python
def simulate_mm(trades: list[dict], initial_equity: float, mm_type: str, param: float) -> dict:
    """
    mm_type: "fixed_lots" | "risk_pct" | "fixed_risk_money"
    param: 
      - fixed_lots: número de lotes (multipla o profit proporcionalmente)
      - risk_pct: % do capital (ex: 0.02 = 2%)
      - fixed_risk_money: valor fixo em $ por trade
    
    Recalcula equity aplicando o MM e retorna full_analysis com equity_curve.
    """
```

### Backend — novo endpoint

```
POST /analysis/runs/{run_id}/mm-simulate
Body: { "scenarios": [ {"name": "2% Risk", "mm_type": "risk_pct", "param": 0.02}, ... ] }
Response: { "scenarios": [ {"name": str, "metrics": {...}, "equity_curve": [...] } ] }
```

### Frontend — nova página `frontend/src/pages/MMSimPage.jsx`

- Selector de run
- Tabela de cenários: cada linha tem nome, tipo (dropdown), parâmetro (input), botão remover
- Botão "Adicionar cenário", botão "Simular"
- Resultado: gráfico de equity com uma linha por cenário (cores diferentes)
- Tabela comparativa de KPIs (Net Profit, Sharpe, DD%, CAGR)
- Adicionar aba "MM Sim" na navegação do `App.jsx`

---

## FASE 7 — Equity Control

### O que é
Aplica regras de stop retroativamente: "pare de operar depois de 3 perdas consecutivas", "pare depois de 10% de DD", "reinicie depois de 20 dias parado". Mostra equity controlada vs original.

### Backend — novo arquivo `backend/services/equity_control.py`

```python
def apply_equity_control(
    trades: list[dict],
    initial_equity: float,
    stop_after_consec_losses: int | None = None,   # ex: 3
    stop_after_dd_pct: float | None = None,          # ex: 0.10
    restart_after_days: int | None = None,           # ex: 20
) -> dict:
    """
    Percorre trades em ordem. Quando condição de stop é atingida, marca
    os trades seguintes como "skipped" até condição de restart.
    Retorna { "controlled_equity": [...], "original_equity": [...], "skipped_trades": int, "metrics_controlled": {...} }
    """
```

### Backend — novo endpoint

```
POST /analysis/runs/{run_id}/equity-control
Body: { "stop_after_consec_losses": 3, "stop_after_dd_pct": 0.10, "restart_after_days": 20 }
Response: { "controlled_equity": [...], "original_equity": [...], "skipped_trades": int, "metrics_controlled": {...} }
```

### Frontend — adicionar seção "Equity Control" na `AnalysisPage.jsx`

- Três inputs: "Parar após X perdas consecutivas", "Parar após DD de X%", "Reiniciar após X dias"
- Botão "Aplicar"
- Gráfico sobreposto: linha original (cinza) + linha controlada (azul)
- KPIs comparativos: Original vs Controlado
- Badge: "X trades pausados" 

---

## FASE 8 — Stagnation visual + métricas

### O que é
Período em que a equity fica abaixo do pico anterior (não necessariamente em drawdown ativo). Mostra quanto tempo o robô ficou "estagnado" sem bater novo máximo.

### Backend — adicionar em `analytics.py`

```python
def stagnation_stats(eq: EquityCurve, trades: list[dict]) -> dict:
    """
    Calcula períodos de estagnação (equity abaixo do pico anterior).
    Retorna:
    {
      "max_stagnation_days": int,
      "avg_stagnation_days": float,
      "stagnation_pct_of_period": float,  # % do período total em estagnação
      "stagnation_periods": [ {"start_idx": int, "end_idx": int, "days": int} ]
    }
    """
```

Adicionar ao retorno de `full_analysis()`.

### Frontend

- Adicionar ao card de KPIs principais: "Estagnação máx." e "% tempo estagnado"
- No gráfico de Equity: opção de mostrar faixas sombreadas nos períodos de estagnação (fundo levemente vermelho nas regiões onde equity < pico)

---

## Instruções gerais para implementação

1. **Sempre rodar `full_analysis` side-effect-free:** não alterar a assinatura existente, só acrescentar chaves ao dict retornado.
2. **Recharts apenas:** não instalar novos pacotes de gráfico.
3. **Sem novos arquivos CSS:** usar classes existentes no `App.css`/`index.css`.
4. **Cada fase deve ser testável isoladamente:** backend via `curl` / frontend via `npm run dev`.
5. **Após cada fase:** atualizar `frontend/src/App.jsx` se nova aba for adicionada.
6. **Não alterar:** `backend/services/storage.py`, `backend/services/monte_carlo.py`, nem os componentes `Kpi.jsx`, `EquityChart.jsx`.
7. **Tratamento de dados faltantes:** se `time_in`/`time_out` não forem parseáveis, retornar `null` graciosamente — não quebrar a análise.
