import { useMemo, useState, useEffect } from 'react'
import {
  uploadTriageXML, project3D, runSingle, ingestReport, errorMessage,
} from '../services/api'
import { Heatmap2D } from '../components/Heatmap2D'
import { ParallelCoords } from '../components/ParallelCoords'
import { Planet3D } from '../components/Planet3D'
import { InstallationPicker } from '../components/InstallationPicker'
import { ContextualTooltip } from '../components/ContextualTooltip'

// Mesma lista usada na aba "Coleta ao vivo" — mantém critérios consistentes
// entre triagem por vizinhança e ranqueamento de passes.
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

export function TriagePage({ onOpenRun }) {
  const [file, setFile] = useState(null)
  const [scoreKey, setScoreKey] = useState('net_profit')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [data, setData] = useState(null)
  const [minStability, setMinStability] = useState(0.5)
  const [minNeighbors, setMinNeighbors] = useState(1)
  const [xParam, setXParam] = useState('')
  const [yParam, setYParam] = useState('')
  const [vizMetric, setVizMetric] = useState('robust_score')
  const [aggregate, setAggregate] = useState('max')
  const [viewMode, setViewMode] = useState('sphere')
  const [projection, setProjection] = useState(null)
  const [projLoading, setProjLoading] = useState(false)

  // Execução individual de um pass (re-roda backtest com aqueles parâmetros)
  const [selection, setSelection] = useState(null)   // {installation, expert, inputs}
  const [symbol, setSymbol] = useState('')
  const [period, setPeriod] = useState('M1')
  const [fromDate, setFromDate] = useState('2024-01-01')
  const [toDate, setToDate] = useState('2024-01-31')
  const [deposit, setDeposit] = useState(10000)
  const [runningPassIdx, setRunningPassIdx] = useState(null)

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

  const numericParams = useMemo(() => {
    if (!data?.passes?.length) return []
    const p0 = data.passes[0]
    return Object.keys(p0.parameters).filter(k => typeof p0.parameters[k] === 'number')
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
      <div className="card">
        <h2>Triagem de robustez (upload XML do MT5)</h2>
        <p className="muted small">
          Rode a otimização <b>direto no MT5</b> (Strategy Tester → aba Optimization).
          Quando terminar, clique com botão direito na aba <b>Optimization Results</b> → <b>Open XML</b>.
          Faça upload do arquivo aqui para filtrar overfitting via análise de vizinhança.
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

      {data && (
        <div className="card">
          <h2>Execução individual (opcional)</h2>
          <p className="muted small">
            Configure MT5 + EA + período aqui para habilitar o botão <b>Rodar</b>
            em cada linha da tabela abaixo. O AuraBackTest re-executa o backtest
            com os parâmetros daquele pass e abre o resultado na aba <b>Análise</b>
            (com MC, MAE/MFE, stat validation, etc).
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
            <p className="muted small" style={{ marginTop: 8 }}>
              Selecione MT5, EA e informe um símbolo para habilitar a execução individual.
            </p>
          )}
        </div>
      )}

      {data && (
        <div className="card">
          <h2>Resultados ({data.num_passes} passes)</h2>
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

          <h3 style={{ color: 'var(--muted)', fontSize: 13, marginTop: 20 }}>
            Top 50 candidatos robustos
          </h3>
          <table>
            <thead><tr>
              <th>#</th>
              <th>Parâmetros</th>
              <th>Robust Score</th>
              <th>Estabilidade</th>
              <th>Vizinhos</th>
              <th>{scoreKey}</th>
              <th>Média vizinhança</th>
              <th>Desvio</th>
              <th></th>
            </tr></thead>
            <tbody>
              {filtered.slice(0, 50).map((p, i) => (
                <tr key={p.pass_idx}>
                  <td>{i + 1}</td>
                  <td className="small"><code>{JSON.stringify(p.parameters)}</code></td>
                  <td>{p.robust_score?.toFixed(2)}</td>
                  <td>{((p.stability ?? 0) * 100).toFixed(1)}%</td>
                  <td>{p.neighbor_count}</td>
                  <td>{p.metrics[scoreKey]?.toFixed(2) ?? '—'}</td>
                  <td>{p.score_mean?.toFixed(2)}</td>
                  <td>{p.score_std?.toFixed(2)}</td>
                  <td>
                    <ContextualTooltip text="Re-roda individual com estes parâmetros → vai para Análise">
                      <button
                        className="ghost"
                        disabled={!canRunIndividual || runningPassIdx !== null}
                        onClick={() => runSinglePass(p)}
                        title={canRunIndividual ? 'Re-roda o backtest e abre na aba Análise' : 'Configure MT5+EA+símbolo acima'}>
                        {runningPassIdx === p.pass_idx ? 'Rodando…' : 'Rodar'}
                      </button>
                    </ContextualTooltip>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
