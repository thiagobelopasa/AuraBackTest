# AuraBackTest — Guia Completo para Claude Code

**Objetivo:** Motor de backtesting profissional para estratégias MT5 (MQL5), com análise estatística estilo Renaissance/QuantAnalyzer.
**Stack:** FastAPI (Python 3.11+) + React/Vite + SQLite + Recharts + Polars + SciPy

---

## Arquitetura em 30 segundos

```
backend/            ← FastAPI, porta 8000 (dev) / 8765 (Electron)
  main.py           ← app FastAPI; registra todos os routers
  routers/          ← endpoints por domínio
  services/         ← toda a lógica de negócio (sem dependência de routers)
  models/schemas.py ← Pydantic + dataclasses compartilhados
  aurabacktest.db   ← SQLite (não commitar)

frontend/
  src/
    pages/          ← uma página por aba do app
    components/     ← componentes reutilizáveis
    services/api.js ← TODAS as chamadas Axios estão aqui
  vite.config.js    ← proxy /api → :8000 em dev

electron/           ← wrapper Electron para distribuição desktop
```

---

## Backend — Mapa Completo de Serviços

### `services/analytics.py` — Análise de trades
Função central: `full_analysis(trades, initial_equity)` → devolve dict com TUDO abaixo:

| Chave retornada | Função geradora |
|---|---|
| equity_curve, drawdown_curve | `build_equity_curve()` |
| net_profit, win_rate, sharpe_ratio, sortino_ratio, calmar_ratio, sqn, k_ratio, ulcer_index, payoff_ratio, recovery_factor, expectancy, annual_return_pct, profit_factor, max_drawdown_pct | `basic_trade_stats()` |
| time_breakdown | `time_breakdown(trades)` → {by_hour, by_weekday, by_month, by_year} |
| mae_mfe | `mae_mfe_data(trades)` → lista de {trade_num, profit, duration_sec, side, is_win, r_multiple} |
| direction | `direction_stats(trades)` → {long: {...}, short: {...}} |
| risk_of_ruin | `risk_of_ruin_table(win_rate, payoff_ratio)` → lista por % risco |
| stagnation | `stagnation_stats(eq, trades)` → {max_stagnation_days, avg, pct, stagnation_periods} |

### `services/stat_tests.py` — Validações Simons-style
Entrada: `run_stat_validation(trades, initial)` → scorecard com 6 testes + `suggestion` em cada FAIL:
- t-test (t≥2.5), Ljung-Box (autocorr), Runs test (sequência), Outlier dependency (top 5%), Tail ratio (P95/|P5|), Jarque-Bera (skew>0)
- Funções extras disponíveis (não no scorecard padrão): `variance_ratio()`, `hurst_exponent()`, `edge_stability()`, `sharpe_bootstrap_ci()`, `max_consecutive_losses()`, `profit_gini()`

### `services/robustness.py` — Suite de Robustez Quant
Entrada: `run_suite(trades, initial, runs, seed, ...)` → scorecard com PSR, DSR, MinTRL, MC shuffle/bootstrap/block/skip/noise, regime por ano + `suggestion` em cada FAIL.
- `probabilistic_sharpe(sr, n, skew, kurt)` — Bailey & López de Prado
- `deflated_sharpe(sr, n, skew, kurt, n_trials, var_sr_trials)` — corrige multi-testing
- `minimum_track_record_length(sr, skew, kurt)` — MinTRL em nº de trades

### `services/monte_carlo.py` — MC Sintético (sem ticks)
`monte_carlo(trades, initial, runs, mode, seed)` → `MonteCarloResult`
Modos: `shuffle`, `bootstrap`, `skip`, `noise`

### `services/tick_monte_carlo.py` — MC com Ticks Reais ⭐ NOVO
`run_all_tick_mc(trades, parquet_path, initial, runs, ...)` → 3 testes + scorecard:
1. **entry_jitter_mc**: desloca entrada ±jitter_seconds no tick real → testa timing
2. **spread_slippage_mc**: usa bid/ask real + worst-of-N → testa custo de execução
3. **tick_return_bootstrap_mc**: block bootstrap de log-returns de tick → paths alternativos

Cada método retorna `suggestion` contextual quando prob_profitable < 0.85.

### `services/tick_mae_mfe.py` — MAE/MFE com Ticks Reais
`compute_mae_mfe(trades, parquet_path, buffer_seconds)` → enriquece trades com:
mae_price, mfe_price, mae_dollars, mfe_dollars, efficiency, entry_efficiency, r_multiple_real

`aggregate_mae_mfe_stats(enriched)` → edge_ratio, pct_mfe_captured, optimal_tp/sl_estimate

### `services/whatif.py`
`apply_whatif(trades, initial, excluded_hours, excluded_weekdays)` → {original, whatif, excluded_trades}

### `services/mm_simulator.py`
`run_scenarios(trades, initial, scenarios)` — tipos: `fixed_lots`, `risk_pct`, `fixed_risk_money`

### `services/equity_control.py`
`apply_equity_control(trades, initial, stop_after_consec_losses, stop_after_dd_pct, restart_after_days)`
→ {controlled_equity, original_equity, skipped_trades, metrics_controlled, metrics_original}

### `services/walk_forward.py`
`split_folds(start, end, folds, oos_pct, anchored)` → lista de Fold
`compute_wfa_score(is_metrics, oos_metrics, score_field)` → {stability_score, consistency, degradation}

### `services/tick_converter.py` — Converte CSV MT5 → Parquet
`convert_mt5_csv_to_parquet(csv_path, output_dir, symbol, partition)` → TickDatasetInfo
- Formato CSV: tab-separated `<DATE> <TIME> <BID> <ASK> <LAST> <VOLUME> <FLAGS>`
- Parquet comprimido zstd, lido via Polars lazy (suporta GB sem RAM)

### `services/storage.py` — SQLite
`init_db()` — cria tabelas: `runs`, `trades`, `analyses`, `monte_carlo_results`, `optimization_passes`
Funções principais: `save_run()`, `save_trades()`, `save_analysis()`, `load_trades()`, `load_analysis()`, `list_runs()`, `get_run()`, `delete_run()`

### `services/ea_instrumenter.py` — Auto-instrumentação de EA ⭐ NOVO
`instrument_ea(source_path, suffix="_Aura")` → `InstrumentationResult`:
- Lê o `.mq5` original do cliente
- Detecta inputs numéricos (int/long/double/bool) via `mq5_parser`
- Injeta o coletor **inline** (sem dependência de include externo)
- Se já existe `OnTester()`, renomeia para `_AuraUserOnTester()` e cria wrapper
- Salva `<nome>_Aura.mq5` ao lado do original

### `services/ea_compiler.py` — Compilação via MetaEditor CLI ⭐ NOVO
`compile_ea(source_path, metaeditor_exe)` → `CompileResult` com log.
`find_metaeditor(terminal_exe)` localiza `metaeditor64.exe` ao lado do terminal.

### `services/pass_watcher.py` — Coleta ao vivo durante otimização MT5 ⭐ NOVO
Watcher de diretório (polling 1s) que monitora `%APPDATA%\MetaQuotes\Terminal\Common\Files\AuraBackTest\`.
O EA do cliente grava um JSON por pass via include `mql5_include/AuraBackTestCollector.mqh`
(chamando `AuraCollect()` dentro de `OnTester()`). Cada JSON é convertido em
`{pass_id, parameters, computed_metrics, native_metrics, num_trades}` rodando
`analytics.full_analysis()` automaticamente. Singleton `watcher` exposto;
eventos publicados via `asyncio.Queue` para fan-out WebSocket.

### `services/optimizer.py` / `mt5_runner.py` / `mt5_report.py`
- `mt5_runner.prepare_and_run()` → gera .set/.ini → executa `terminal64.exe /config:ini` → localiza relatório
- `mt5_report.parse_report_htm()` + `extract_deals_htm()` + `deals_to_trades()`
- `optimizer.parse_optimization_xml(xml_path, criterion)` → rankeia passes

---

## Routers — Todos os Endpoints

### `/analysis` (routers/analysis.py)
| Método | Path | Descrição |
|---|---|---|
| POST | /analysis/ingest | Parse HTM por path, salva tudo |
| POST | /analysis/ingest-upload | Upload HTM multipart |
| POST | /analysis/analyze | Recalcula full_analysis de run já salvo |
| POST | /analysis/monte-carlo | MC sintético (shuffle/bootstrap/skip/noise) |
| POST | /analysis/robustness-suite | Suite completa (PSR/DSR/MinTRL/MC/regime) |
| POST | /analysis/wfa/split | Calcula folds WFA |
| POST | /analysis/wfa/score | Scorecard IS vs OOS |
| GET | /analysis/runs | Lista runs (param: limit, kind) |
| GET | /analysis/runs/{id} | Detalhe: run + analysis + mc_runs |
| GET | /analysis/runs/{id}/trades | Lista trades do run |
| PATCH | /analysis/runs/{id}/label | Renomeia run |
| DELETE | /analysis/runs/{id} | Apaga run + trades + analyses |
| GET | /analysis/runs/{id}/time-breakdown | Análise temporal (usa cache) |
| POST | /analysis/runs/{id}/whatif | What-If (excluded_hours, excluded_weekdays) |
| POST | /analysis/runs/{id}/mm-simulate | Money Management scenarios |
| POST | /analysis/runs/{id}/equity-control | Aplica regras stop/restart |
| GET | /analysis/runs/{id}/stat-validation | Validações Simons (t-test, LB, Runs...) |
| POST | /analysis/runs/{id}/mae-mfe-ticks | MAE/MFE real via parquet |
| POST | /analysis/runs/{id}/tick-monte-carlo | MC com ticks reais (entry jitter, spread, bootstrap) |

### `/live-optimization` (routers/live_optimization.py) ⭐ NOVO
| Método | Path | Descrição |
|---|---|---|
| POST | /live-optimization/start | Inicia watcher no dir comum do MT5 |
| POST | /live-optimization/stop | Para watcher |
| POST | /live-optimization/clear | Limpa buffer de passes (watcher segue ativo) |
| GET | /live-optimization/snapshot | Retorna todos os passes já coletados |
| WS | /live-optimization/ws | Stream de eventos `{event: 'pass'\|'snapshot', data}` |

### `/mt5`, `/ea`, `/ticks`, `/optimization`, `/triage`, `/portfolio`
- `/mt5/installations` — auto-detect instâncias MT5
- `/mt5/experts?data_folder=` — lista EAs (.mq5/.ex5)
- `/mt5/run-single` — roda backtest único
- `/mt5/report/parse` — parseia HTM por path
- `/ea/parse` — extrai parâmetros do .mq5
- `/ea/instrument` — auto-instrumenta .mq5 + compila via MetaEditor ⭐ NOVO
- `/ticks/inspect` — preview CSV
- `/ticks/convert` — CSV → Parquet
- `/optimization/run` — dispara otimizador MT5, bloqueia, retorna top10
- `/optimization/parse` — parseia XML de otimização
- `/optimization/runs/{id}/passes` — lista passes salvos

---

## Frontend — Mapa Completo

### Páginas (`src/pages/`)
| Arquivo | Aba | O que faz |
|---|---|---|
| BacktestPage.jsx | Backtest | InstallationPicker → run único → carregar relatório |
| AnalysisPage.jsx | Análise | KPIs + equity + drawdown + TimeBreakdown + MAE/MFE + Long/Short + RoR + Stagnation + Equity Control + StatValidation + TickMonteCarlo + Suite + MC |
| WhatIfPage.jsx | What-If | Checkboxes de horas/dias → simular exclusão |
| MMSimPage.jsx | MM Sim | Cenários de sizing → equity comparativa |
| OptimizationPage.jsx | Otimização | Ranges table → rodar → top10 |
| HistoryPage.jsx | Histórico | Lista runs, filtro por tipo, deletar, reabrir |
| PortfolioPage.jsx | Portfolio | Análise de múltiplos robôs combinados |
| TriagePage.jsx | Triagem | Análise automática de lote de backtest results |
| LiveOptPage.jsx | Coleta ao vivo | WebSocket que escuta passes gravados pelo EA durante otimização MT5, ranqueia por Sortino/Sharpe/etc em tempo real |

### Componentes reutilizáveis (`src/components/`)
| Componente | Props principais | O que faz |
|---|---|---|
| Kpi.jsx | label, value, format, colored, gradeKey | KPI card com coloração |
| EquityChart.jsx | values | Curva de equity (+ DrawdownChart, HistogramChart) |
| TimeBreakdown.jsx | data | Barras por hora/dia/mês/ano |
| MaeMfe.jsx | data, runId | Scatter profit×duração + histograma R-múltiplo + TickLoader |
| StagnationChart.jsx | values, periods | Equity com faixas de estagnação |
| StatValidation.jsx | runId | 6 testes Simons + sugestões ao expandir FAIL |
| TickMonteCarlo.jsx | runId | MC com ticks reais (3 métodos) + scorecard + sugestões |
| InstallationPicker.jsx | onSelect | Dropdown de instâncias MT5 |
| Heatmap2D.jsx | — | Heatmap 2D para visualização de otimização |
| Planet3D.jsx | — | 3D scatter de passes de otimização |
| ParallelCoords.jsx | — | Parallel coordinates de passes |
| TrialBanner.jsx | — | Banner de trial/licença |

### `src/services/api.js` — TODAS as chamadas HTTP
Qualquer nova chamada ao backend DEVE ser adicionada aqui. Funções exportadas:
`listInstallations`, `listExperts`, `parseEA`, `inspectTicks`, `convertTicks`,
`runSingle`, `parseReport`, `ingestReport`, `uploadReport`, `updateRunLabel`,
`analyze`, `runMonteCarlo`, `runRobustnessSuite`, `splitWFA`, `listRuns`,
`getRunDetail`, `getRunTrades`, `deleteRun`, `getTimeBreakdown`, `runWhatIf`,
`runMMSimulate`, `runEquityControl`, `getStatValidation`, `getMaeMfeTicks`,
`runTickMonteCarlo`, `runOptimization`, `parseOptReport`, `listPasses`,
`uploadTriageXML`, `project3D`, `startLiveOpt`, `stopLiveOpt`,
`clearLiveOpt`, `liveOptSnapshot`, `openLiveOptStream`

---

## Regras Críticas

### Python
- `full_analysis()` é a função mestra — nunca alterar assinatura, só acrescentar chaves
- Todos os serviços são funções puras; sem estado global
- `storage.py` não pode ser editado sem cuidado — gerencia o SQLite
- `tick_mae_mfe.py` e `tick_monte_carlo.py` usam Polars lazy — não usar pandas nesses arquivos

### React / Frontend
- **Sem novos arquivos CSS** — usar classes: `.card`, `.kpi`, `.grid`, `.cols-2/3/4`, `.row`, `.fit`, `.pill`, `.pos/.neg`, `.muted`, `.small`, `.errbox`
- **Recharts apenas** — não instalar Plotly ou outras libs de gráfico
- Toda chamada HTTP passa por `src/services/api.js`
- Timeout do Axios é 6h (backtest pode demorar) — não reduzir

### MT5 / .ini
- Arquivos .ini gerados devem ser **UTF-16 LE com BOM**
- Expert path usa **backslash** dentro do .ini: `RPAlgo\Big-Small`
- Relatórios: `MT5_Report_*.htm` (backtest) e `MT5_Optim_*.xml` (otimização)

### DB
- `storage.init_db()` é idempotente — chamar a cada startup
- Nunca fazer DELETE sem passar pelo `storage.delete_run()` — limpa trades + analyses em cascata

---

## Fluxo de Dados Tick (para MAE/MFE e MC com ticks)

```
MT5 exporta CSV  →  /ticks/convert  →  ticks.parquet (Polars zstd)
                                              ↓
                          /mae-mfe-ticks → tick_mae_mfe.compute_mae_mfe()
                          /tick-monte-carlo → tick_monte_carlo.run_all_tick_mc()
```

O parquet pode ser:
- Arquivo único: `ticks.parquet`
- Diretório particionado: `ticks/year=2024/month=01/*.parquet` (auto-detectado)

Colunas obrigatórias: `timestamp` (ou `ts`/`datetime`/`time`) + preço (`mid_price`/`last`/`bid`/`ask`)

---

## Como rodar o projeto

```bash
# Backend (porta 8000)
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend (porta 5173, proxy → :8000)
cd frontend
npm install
npm run dev

# Electron (distribução desktop, backend sobe em :8765)
cd electron
npm install
npm start
```

---

## Distribuição — Instalador e Página de Download

### Página de download (GitHub Pages)
`docs/index.html` — landing page hospedada em `https://thiagobelopasa.github.io/AuraBackTest/`
- Consulta a GitHub API para obter a versão mais recente automaticamente
- Download do `.exe` começa após 1.2s sem clicar em nada
- Exibe versão, tamanho e data do release em tempo real
- Workflow: `.github/workflows/pages.yml` publica quando `docs/` muda no `main`

**Para ativar GitHub Pages:**
1. Vá em `Settings → Pages` no repositório GitHub
2. Source: `GitHub Actions`
3. Faça push do `docs/index.html` — o workflow cuida do resto

### Auto-update (Electron)
- `electron-updater` verifica a cada 30 min e ao abrir o app
- `autoDownload: true` — baixa silenciosamente em background
- `autoInstallOnAppQuit: true` — instala ao fechar o app
- `quitAndInstall(true, true)` — silencioso + reabre o app
- `latest.yml` gerado automaticamente pelo `electron-builder --publish always`
- O app exibe `UpdateBanner.jsx` quando há versão disponível

### Web ZIP (Python direto)
`AuraBackTest-Web.bat` — launcher que verifica e instala Python automaticamente:
1. Testa `python --version` e `py -3.11` — aceita qualquer 3.11+
2. Se não encontrar: usa `winget install Python.Python.3.11` (silencioso)
3. Relocaliza o executável após instalação (resolve problema de PATH na mesma sessão)
4. Fallback manual: abre `python.org/downloads/` no browser
5. Cria venv e instala `requirements.txt` na primeira execução

### Build local (sem publicar)
```powershell
.\scripts\build-local.ps1
# Gera: release/AuraBackTest-Setup-<versao>.exe
```

### Release para produção
```bash
git tag v0.5.1
git push origin v0.5.1
# GitHub Actions faz o build e publica automaticamente
```

---

## O que está PENDENTE / ideias futuras

- **PBO via CSCV** (Probability of Backtest Overfitting) — exige matriz N_candidatos × N_subperíodos
- **Capacity / slippage curve** — exige modelo de market impact por volume
- **Walk-Forward automático ponta-a-ponta** — rodar MT5 N vezes nos folds (infraestrutura existe, falta orquestrador)
- **Multi-símbolo correlação** em portfolio (PortfolioPage existe, pode ser expandida)
- **Notificações** quando otimização longa termina (webhook / toast)

---

## Decisões de design importantes

1. **Por que Polars em vez de Pandas para ticks?** — arquivos de GB; Polars lazy não carrega na RAM
2. **Por que SQLite e não Postgres?** — app desktop, single-user; sem servidor externo
3. **Por que MC sintético E MC com ticks?** — sintético é rápido (sem arquivo externo); ticks dá realismo
4. **Por que sugestões no scorecard?** — usuário vê FAIL → sabe exatamente o que fazer, sem precisar pesquisar
5. **Por que o timeout do Axios é 6h?** — otimização MT5 pode levar horas; não pode timeout
