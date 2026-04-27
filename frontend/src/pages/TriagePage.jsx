import { useMemo, useState, useEffect } from 'react'
import {
  uploadTriageXML, project3D, runSingle, ingestReport, errorMessage,
} from '../services/api'
import { Heatmap2D } from '../components/Heatmap2D'
import { ParallelCoords } from '../components/ParallelCoords'
import { Planet3D } from '../components/Planet3D'
import { InstallationPicker } from '../components/InstallationPicker'
import { ContextualTooltip } from '../components/ContextualTooltip'

function computeAuraScore(m = {}) {
  const { sortino_ratio = 0, calmar_ratio = 0, profit_factor = 1, sqn = 0 } = m
  return sortino_ratio * 0.40 + calmar_ratio * 0.30 + (profit_factor - 1) * 0.20 + sqn * 0.10
}

const SCORE_OPTIONS = [
  { value: 'sortino_ratio', label: 'Sortino' },
  { value: 'sharpe_ratio', label: 'Sharpe' },
  { value: 'calmar_ratio', label: 'Calmar' },
  { value: 'net_profit', label: 'Net Profit' },
  { value: 'profit_factor', label: 'Profit Factor' },
  { value: 'recovery_factor', label: 'Recovery Factor' },
  { value: 'sqn', label: 'SQN' },
  { value: 'k_ratio', label: 'K-Ratio' },
  { value: 'expectancy', label: 'Expectancy' },
  { value: 'expected_payoff', label: 'Expected Payoff' },
  { value: 'max_drawdown_pct', label: 'Max DD % (menor=melhor)' },
  { value: 'score', label: 'Custom (OnTester)' },
]

const STORAGE_KEY = 'aura_triage_run_config'

function loadSavedConfig() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') } catch { return {} }
}

function saveConfig(cfg) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(cfg)) } catch {}
}

export function TriagePage({ onOpenRun, preloadedData, onClearPreload }) {
  const [file, setFile] = useState(null)
  const [scoreKey, setScoreKey] = useState('net_profit')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [data, setData] = useState(preloadedData || null)
  const [minStability, setMinStability] = useState(0.5)
  const [minNeighbors, setMinNeighbors] = useState(1)
  const [xParam, setXParam] = useState('')
  const [yParam, setYParam] = useState('')
  const [vizMetric, setVizMetric] = useState('robust_score')
  const [aggregate, setAggregate] = useState('max')
  const [viewMode, setViewMode] = useState('sphere')
  const [projection, setProjection] = useState(null)
  const [projLoading, setProjLoading] = useState(false)

  // Execução individual — inicializa do localStorage (lazy para evitar leitura em todo render)
  const [selection, setSelection] = useState(null)
  const [symbol, setSymbol] = useState(() => loadSavedConfig().symbol || '')
  const [period, setPeriod] = useState(() => loadSavedConfig().period || 'M1')
  const [fromDate, setFromDate] = useState(() => loadSavedConfig().fromDate || '2024-01-01')
  const [toDate, setToDate] = useState(() => loadSavedConfig().toDate || '2024-01-31')
  const [deposit, setDeposit] = useState(() => loadSavedConfig().deposit || 10000)
  const [runningPassIdx, setRunningPassIdx] = useState(null)

  // Quando vêm dados da coleta ao vivo, pré-preenche símbolo/TF/depósito da session
  useEffect(() => {
    if (!preloadedData?.session) return
    const s = preloadedData.session
    if (s.symbol) setSymbol(s.symbol)
    if (s.timeframe) setPeriod(s.timeframe)
    if (s.initial_deposit) setDeposit(s.initial_deposit)
  }, [preloadedData])

  const upload = async () => {
    if (!file) { setError('Selecione o XML'); return }
    setError(''); setLoading(true); setData(null)
    try {
      const d = await uploadTriageXML(file, scoreKey)
      setData(d)
    } catch (e) {
      setError(`Erro: ${errorMessage(e)}`)
    } finally { setLoading(false) }
  }

  const filtered = useMemo(() => {
    if (!data) return []
    return data.passes.filter(p =>
      (p.stability ?? 0) >= minStability &&
      (p.neighbor_count ?? 0) >= minNeighbors
    )
  }, [data, minStability, minNeighbors])

  const passFilter = (p) =>
    (p.stability ?? 0) >= minStability && (p.neighbor_count ?? 0) >= minNeighbors

  // Persiste configuração de execução individual no localStorage
  useEffect(() => {
    saveConfig({ symbol, period, fromDate, toDate, deposit })
  }, [symbol, period, fromDate, toDate, deposit])

  // Robust Score normalizado: 100% = melhor pass da lista
  const maxRobustScore = useMemo(() => {
    if (!data?.passes?.length) return 1
    return Math.max(...data.passes.map(p => p.robust_score ?? 0), 0.001)
  }, [data])

  const numericParams = useMemo(() => {
    if (!data?.passes?.length) return []
    const p0 = data.passes[0]
    return Object.keys(p0.parameters).filter(k => typeof p0.parameters[k] === 'number')
  }, [data])

  // Só inclui parâmetros que estão sendo otimizados (valor varia entre passes).
  // Parâmetros fixos poluem a tabela e não ajudam na análise.
  const varyingParamKeys = useMemo(() => {
    if (!data?.passes?.length) return []
    const valuesByKey = new Map()
    for (const p of data.passes) {
      for (const [k, v] of Object.entries(p.parameters || {})) {
        if (!valuesByKey.has(k)) valuesByKey.set(k, new Set())
        valuesByKey.get(k).add(String(v))
      }
    }
    return Array.from(valuesByKey.entries())
      .filter(([, vs]) => vs.size > 1)
      .map(([k]) => k)
  }, [data])

  useEffect(() => {
    if (numericParams.length >= 2 && !xParam) {
      setXParam(numericParams[0])
      setYParam(numericParams[1])
    }
  }, [numericParams, xParam])

  const metricOptions = useMemo(() => {
    const base = ['robust_score', 'stability']
    return [...base, ...(data?.available_metrics || [])]
  }, [data])

  const loadProjection = async () => {
    if (!data?.passes || !numericParams.length) return
    setProjLoading(true)
    try {
      const d = await project3D({
        passes: data.passes,
        params: numericParams,
        metric_key: vizMetric,
        mode: viewMode,
      })
      setProjection(d)
    } catch (e) {
      setError(`Erro projeção 3D: ${errorMessage(e)}`)
    } finally { setProjLoading(false) }
  }

  useEffect(() => { setProjection(null) }, [data, vizMetric, viewMode])

  useEffect(() => {
    if (preloadedData) {
      setData(preloadedData)
      if (preloadedData.score_key) setScoreKey(preloadedData.score_key)
      setXParam(''); setYParam('')
    }
  }, [preloadedData])

  const runSinglePass = async (pass) => {
    if (!selection?.installation || !selection?.expert) {
      setError('Configure MT5 + EA na seção "Execução individual" antes.')
      return
    }
    if (!symbol) { setError('Informe o símbolo.'); return }
    setError(''); setRunningPassIdx(pass.pass_idx)
    try {
      // Merge: defaults do EA + parâmetros do pass (pass sobrescreve)
      const defaults = {}
      selection.inputs.forEach(i => { defaults[i.name] = i.default })
      const ea_inputs_defaults = { ...defaults, ...pass.parameters }

      const label = `Triagem pass #${pass.pass_idx}`
      const res = await runSingle({
        terminal_exe: selection.installation.terminal_exe,
        data_folder: selection.installation.data_folder,
        ea_relative_path: selection.expert.relative_path,
        ea_inputs_defaults,
        ranges: [],
        symbol, period,
        from_date: fromDate, to_date: toDate,
        deposit,
      })
      if (!res.report_path) {
        setError('Backtest rodou mas sem report (verifique stdout).')
        return
      }
      const ingest = await ingestReport({
        run_id: res.run_id,
        report_path: res.report_path,
        ea_path: selection.expert.relative_path,
        symbol, timeframe: period,
        from_date: fromDate, to_date: toDate,
        deposit,
        parameters: ea_inputs_defaults,
        label,
      })
      if (onOpenRun) onOpenRun(ingest.run_id)
    } catch (e) {
      setError(`Erro no backtest individual: ${errorMessage(e)}`)
    } finally { setRunningPassIdx(null) }
  }

  const canRunIndividual = selection?.installation && selection?.expert && symbol

  return (
    <div>
      {preloadedData && data ? (
        <div className="card" style={{ borderColor: 'var(--accent)', borderWidth: 2 }}>
          <div className="row" style={{ alignItems: 'center', gap: 12 }}>
            <div style={{ flex: 1 }}>
              <h2 style={{ margin: 0 }}>
                Análise de Otimização
                <span className="pill" style={{ marginLeft: 10, background: 'var(--accent)', color: '#fff', verticalAlign: 'middle' }}>
                  Coleta ao vivo
                </span>
              </h2>
              <p className="muted small" style={{ margin: '4px 0 0' }}>
                {data.num_passes} passes carregados da sessão de coleta ao vivo,
                ordenados por <b>{data.score_key}</b> com análise de vizinhança aplicada.
              </p>
            </div>
            <button className="ghost small" onClick={() => { setData(null); onClearPreload && onClearPreload() }}>
              Limpar / Carregar XML
            </button>
          </div>
          {error && <div className="errbox" style={{ marginTop: 10 }}>{error}</div>}
        </div>
      ) : (
        <div className="card">
          <h2>Análise de Otimização (upload XML do MT5)</h2>
          <p className="muted small">
            Rode a otimização <b>direto no MT5</b> (Strategy Tester → aba Optimization).
            Quando terminar, clique com botão direito na aba <b>Optimization Results</b> → <b>Open XML</b>.
            Faça upload do arquivo aqui para filtrar overfitting via análise de vizinhança.
            <br />
            <b>Ou acesse pela aba "Otimização ao vivo" para carregar os dados automaticamente.</b>
          </p>
          <div className="row">
            <div style={{ flex: 2 }}>
              <label>Arquivo XML</label>
              <input type="file" accept=".xml"
                onChange={e => setFile(e.target.files?.[0] || null)} />
            </div>
            <div>
              <label>Métrica de ranking</label>
              <select value={scoreKey} onChange={e => setScoreKey(e.target.value)}>
                {SCORE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div className="fit" style={{ paddingBottom: 6, display: 'flex', alignItems: 'flex-end' }}>
              <ContextualTooltip text="Processa passes, detecta overfitting por análise de vizinhança">
                <button disabled={!file || loading} onClick={upload}>
                  {loading ? 'Analisando...' : 'Analisar'}
                </button>
              </ContextualTooltip>
            </div>
          </div>
          {error && <div className="errbox" style={{ marginTop: 10 }}>{error}</div>}
        </div>
      )}

      <div className="card">
        <h2>Execução individual — re-rodar pass no MT5</h2>
        <p className="muted small">
          Preencha aqui para habilitar o botão <b>Rodar</b> em cada linha abaixo.
          O AuraBackTest executa o backtest com os parâmetros daquele pass e abre o resultado
          na aba <b>Análise Individual</b> (com MC, MAE/MFE, stat validation, etc).
        </p>
        <InstallationPicker onSelection={setSelection} />
        <div className="row" style={{ marginTop: 10 }}>
          <div><label>Símbolo</label>
            <input value={symbol} onChange={e => setSymbol(e.target.value)} placeholder="US100.cash" /></div>
          <div><label>Timeframe</label>
            <select value={period} onChange={e => setPeriod(e.target.value)}>
              {['M1','M5','M15','M30','H1','H4','D1'].map(p => <option key={p} value={p}>{p}</option>)}
            </select></div>
          <div><label>De</label>
            <input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)} /></div>
          <div><label>Até</label>
            <input type="date" value={toDate} onChange={e => setToDate(e.target.value)} /></div>
          <div><label>Depósito</label>
            <input type="number" value={deposit} onChange={e => setDeposit(+e.target.value)} /></div>
        </div>
        {!canRunIndividual && (
          <p className="muted small" style={{ marginTop: 8, color: 'var(--warning, #d29922)' }}>
            ⚠ Selecione MT5, EA e informe símbolo para habilitar o botão Rodar.
          </p>
        )}
        {canRunIndividual && (
          <p className="muted small" style={{ marginTop: 8, color: '#3fb950' }}>
            ✓ Pronto — botão Rodar ativo na tabela abaixo.
          </p>
        )}
      </div>

      {data && (
        <div className="card">
          <h2>Resultados ({data.num_passes} passes)</h2>

          {/* Legenda rápida das duas métricas-chave */}
          <div className="grid cols-2" style={{ marginBottom: 16, gap: 10 }}>
            <div style={{ padding: '10px 14px', background: 'var(--panel-2)', borderRadius: 8, borderLeft: '3px solid #D4AF5F' }}>
              <div style={{ fontWeight: 700, fontSize: 13, color: '#D4AF5F', marginBottom: 4 }}>★ Aura Score — QUANTO rende</div>
              <div className="small muted">
                Combinação ponderada: 40% Sortino + 30% Calmar + 20% (PF-1) + 10% SQN.
                Mede a qualidade absoluta do retorno ajustado ao risco deste pass específico.
                <b style={{ color: 'var(--fg)' }}> Use para escolher qual parâmetro é melhor.</b>
              </div>
            </div>
            <div style={{ padding: '10px 14px', background: 'var(--panel-2)', borderRadius: 8, borderLeft: '3px solid #58a6ff' }}>
              <div style={{ fontWeight: 700, fontSize: 13, color: '#58a6ff', marginBottom: 4 }}>⬡ Robust % — QUÃO CONFIÁVEL é</div>
              <div className="small muted">
                100% = o melhor pass desta lista em robustez. Mede se parâmetros vizinhos também performam bem.
                Alto % = platô largo = menos risco de overfit. Baixo % = pico isolado = suspeita de curva-fitting.
                <b style={{ color: 'var(--fg)' }}> Use para filtrar. Idealmente acima de 70%.</b>
              </div>
            </div>
          </div>
          <div className="small muted" style={{ marginBottom: 14, padding: '8px 12px', background: 'var(--panel-2)', borderRadius: 6 }}>
            <b>Estratégia ideal:</b> filtre primeiro por Robust Score alto (coluna azul) → depois ordene por Aura Score (coluna dourada) → use "Rodar" nos candidatos no topo.
          </div>

          <div className="row">
            <div>
              <label>Estabilidade mínima ({(minStability * 100).toFixed(0)}%)</label>
              <input type="range" min="0" max="1" step="0.05"
                value={minStability}
                onChange={e => setMinStability(+e.target.value)} />
            </div>
            <div>
              <label>Vizinhos mínimos</label>
              <input type="number" min="0" max="20" value={minNeighbors}
                onChange={e => setMinNeighbors(+e.target.value)} />
            </div>
            <div className="fit" style={{ paddingBottom: 6 }}>
              <div className="kpi">
                <div className="label">Sobreviventes</div>
                <div className="value">{filtered.length}</div>
              </div>
            </div>
          </div>

          <div style={{ overflowX: 'auto', marginTop: 16 }}>
            <table>
              <thead><tr>
                <th></th>
                <th style={{ width: 32 }}>#</th>
                <th style={{ color: '#58a6ff', cursor: 'help' }}
                  title="Robust Score % = (score do pass × estabilidade) / melhor da lista × 100. 100% = o melhor candidato desta lista. Baixo = pico isolado = suspeita de overfit.">
                  ⬡ Robust % (?)
                </th>
                <th style={{ cursor: 'help' }}
                  title="% de vizinhos que também passam no critério de qualidade. 90%+ = muito estável. Abaixo de 60% = frágil.">
                  Estab. (?)
                </th>
                <th>Vizinhos</th>
                <th style={{ color: '#D4AF5F', cursor: 'help' }}
                  title="Aura Score = 40% Sortino + 30% Calmar + 20% (PF-1) + 10% SQN. Mede a qualidade absoluta deste pass. Use este para comparar qual é melhor.">
                  ★ Aura (?)
                </th>
                <th>Sortino</th>
                <th>Calmar</th>
                <th>Net Profit</th>
                <th>PF</th>
                <th>DD %</th>
                <th style={{ cursor: 'help' }}
                  title="Média da métrica de ranking entre os vizinhos. Se for próxima do valor do próprio pass = platô real.">
                  Média viz. (?)
                </th>
                <th style={{ cursor: 'help' }}
                  title="Desvio padrão da métrica entre vizinhos. Baixo = platô consistente. Alto = ambiente irregular ao redor.">
                  Desvio (?)
                </th>
                {varyingParamKeys.map(k => <th key={k}>{k}</th>)}
              </tr></thead>
              <tbody>
                {filtered.slice(0, 50).map((p, i) => {
                  const m = p.metrics || {}
                  const aura = computeAuraScore(m)
                  const auraColor = aura > 1.5 ? '#3fb950' : aura > 0.5 ? '#d29922' : '#f85149'
                  const rsPct = ((p.robust_score ?? 0) / maxRobustScore) * 100
                  const rsColor = rsPct >= 70 ? '#58a6ff' : rsPct >= 40 ? '#8b949e' : '#f85149'
                  const stab = (p.stability ?? 0) * 100
                  const stabColor = stab >= 80 ? '#3fb950' : stab >= 60 ? '#d29922' : '#f85149'
                  return (
                    <tr key={p.pass_idx}>
                      <td>
                        <ContextualTooltip text={canRunIndividual
                          ? 'Re-roda este pass no MT5 e abre na aba Análise Individual'
                          : 'Preencha MT5 + EA + Símbolo na seção acima para habilitar'}>
                          <button
                            className={canRunIndividual ? '' : 'ghost'}
                            disabled={!canRunIndividual || runningPassIdx !== null}
                            onClick={() => runSinglePass(p)}>
                            {runningPassIdx === p.pass_idx ? 'Rodando…' : 'Rodar'}
                          </button>
                        </ContextualTooltip>
                      </td>
                      <td>{i + 1}</td>
                      <td style={{ fontWeight: 700, color: rsColor }}>{rsPct.toFixed(1)}%</td>
                      <td style={{ color: stabColor }}>{stab.toFixed(1)}%</td>
                      <td>{p.neighbor_count}</td>
                      <td style={{ fontWeight: 700, color: auraColor }}>{isNaN(aura) ? '—' : aura.toFixed(3)}</td>
                      <td>{m.sortino_ratio?.toFixed(3) ?? '—'}</td>
                      <td>{m.calmar_ratio?.toFixed(3) ?? '—'}</td>
                      <td>{m.net_profit?.toFixed(2) ?? '—'}</td>
                      <td>{m.profit_factor?.toFixed(3) ?? '—'}</td>
                      <td>{m.max_drawdown_pct?.toFixed(2) ?? '—'}</td>
                      <td className="muted">{p.score_mean?.toFixed(2) ?? '—'}</td>
                      <td className="muted">{p.score_std?.toFixed(2) ?? '—'}</td>
                      {varyingParamKeys.map(k => (
                        <td key={k} className="small">{String(p.parameters?.[k] ?? '—')}</td>
                      ))}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          {filtered.length === 0 && (
            <p className="muted small">Nenhum pass passou nos filtros. Afrouxe os critérios acima.</p>
          )}
        </div>
      )}

      {data && numericParams.length >= 2 && (
        <div className="card">
          <h2>Heatmap 2D — mapa de "montanhas"</h2>
          <p className="muted small">
            Visualiza a métrica em função de 2 parâmetros. Montanhas largas (regiões contínuas
            de cor alta) = robustas. Picos isolados = overfit. Células esmaecidas foram
            excluídas pelos filtros acima.
          </p>
          <div className="row">
            <div>
              <label>Eixo X</label>
              <select value={xParam} onChange={e => setXParam(e.target.value)}>
                {numericParams.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label>Eixo Y</label>
              <select value={yParam} onChange={e => setYParam(e.target.value)}>
                {numericParams.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label>Métrica (cor)</label>
              <select value={vizMetric} onChange={e => setVizMetric(e.target.value)}>
                {metricOptions.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div>
              <label>Agregação</label>
              <select value={aggregate} onChange={e => setAggregate(e.target.value)}>
                <option value="max">máximo</option>
                <option value="mean">média</option>
              </select>
            </div>
          </div>
          <div style={{ marginTop: 14 }}>
            <Heatmap2D
              passes={data.passes}
              xParam={xParam} yParam={yParam}
              metricKey={vizMetric}
              filter={passFilter}
              aggregate={aggregate}
            />
          </div>
        </div>
      )}

      {data && numericParams.length >= 2 && (
        <div className="card">
          <h2>Planeta 3D — espaço de parâmetros inteiro</h2>
          <p className="muted small">
            Reduz os {numericParams.length} parâmetros a 3D via PCA.
            No modo <b>esfera</b>: posição = semelhança entre candidatos, altura = métrica
            (montanhas largas e altas = clusters robustos e lucrativos).
            No modo <b>scatter</b>: XYZ = 3 principais componentes, cor = métrica.
            Pontos esmaecidos = excluídos pelos filtros acima.
          </p>
          <div className="row">
            <div>
              <label>Modo</label>
              <select value={viewMode} onChange={e => setViewMode(e.target.value)}>
                <option value="sphere">Esfera (montanhas)</option>
                <option value="scatter">Scatter PCA</option>
              </select>
            </div>
            <div className="fit" style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button disabled={projLoading} onClick={loadProjection}>
                {projLoading ? 'Projetando...' : (projection ? 'Atualizar 3D' : 'Gerar 3D')}
              </button>
            </div>
          </div>
          {projection && (
            <div style={{ marginTop: 14 }}>
              <Planet3D
                projection={projection}
                passes={data.passes}
                filter={passFilter}
                mode={viewMode}
              />
              <p className="muted small" style={{ marginTop: 6 }}>
                Arraste pra rotacionar · scroll pra zoom · hover em cada ponto mostra os parâmetros.
              </p>
            </div>
          )}
        </div>
      )}

      {data && numericParams.length >= 2 && (
        <div className="card">
          <h2>Parallel Coordinates — todos os parâmetros</h2>
          <p className="muted small">
            Cada linha = um candidato atravessando os parâmetros.
            <b> Feixes grossos</b> de cor alta = regiões robustas (vários candidatos semelhantes performam bem).
            Linhas solitárias no topo = picos isolados (suspeita de overfit).
            Excluídos pelos filtros aparecem esmaecidos.
          </p>
          <ParallelCoords
            passes={data.passes}
            params={numericParams}
            metricKey={vizMetric}
            filter={passFilter}
          />
        </div>
      )}
    </div>
  )
}
