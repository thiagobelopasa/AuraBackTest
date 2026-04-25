import { useEffect, useMemo, useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  Tooltip, CartesianGrid, Legend,
} from 'recharts'
import {
  getRunDetail, runMonteCarlo, runRobustnessSuite, analyze, listRuns,
  runEquityControl, uploadReport, runWhatIf, runMMSimulate, errorMessage,
} from '../services/api'
import { Kpi } from '../components/Kpi'
import { EquityChart, DrawdownChart, HistogramChart } from '../components/EquityChart'
import { TimeBreakdown } from '../components/TimeBreakdown'
import { MaeMfe } from '../components/MaeMfe'
import { StagnationChart } from '../components/StagnationChart'
import { StatValidation } from '../components/StatValidation'
import { TickMonteCarlo } from '../components/TickMonteCarlo'
import { runOptionText } from '../services/runLabel'
import { ContextualTooltip } from '../components/ContextualTooltip'

const axisProps = { stroke: '#8b98a5', tick: { fontSize: 11 } }
const tooltipStyle = { contentStyle: { background: '#0b0f14', border: '1px solid #1f2a37', fontSize: 12 } }

const METRICS_LAYOUT = [
  { label: 'Net Profit', key: 'net_profit', format: 'money', colored: true },
  { label: 'Net Profit %', key: 'net_profit_pct', format: 'pct', colored: true },
  { label: 'Annual Return', key: 'annual_return_pct', format: 'pct', colored: true },
  { label: 'Max Drawdown %', key: 'max_drawdown_pct', format: 'pct' },
  { label: 'Profit Factor', key: 'profit_factor' },
  { label: 'Expectancy', key: 'expectancy', format: 'money' },
  { label: 'Payoff Ratio', key: 'payoff_ratio' },
  { label: 'Win Rate', key: 'win_rate', format: 'pct', digits: 1 },
  { label: 'Sharpe', key: 'sharpe_ratio', digits: 3 },
  { label: 'Sortino', key: 'sortino_ratio', digits: 3 },
  { label: 'SQN (Van Tharp)', key: 'sqn', digits: 3 },
  { label: 'K-Ratio', key: 'k_ratio', digits: 3 },
  { label: 'Recovery Factor', key: 'recovery_factor', digits: 3 },
  { label: 'Ulcer Index', key: 'ulcer_index', digits: 3 },
  { label: 'Calmar', key: 'calmar_ratio', digits: 3 },
  { label: 'Total Trades', key: 'total', format: 'num', digits: 0 },
]

// ─── What-If helpers ────────────────────────────────────────────────────────
const HOURS = Array.from({ length: 24 }, (_, i) => i)
const WEEKDAYS = [
  { num: 0, label: 'Seg' }, { num: 1, label: 'Ter' }, { num: 2, label: 'Qua' },
  { num: 3, label: 'Qui' }, { num: 4, label: 'Sex' }, { num: 5, label: 'Sáb' }, { num: 6, label: 'Dom' },
]
const WI_KEYS = [
  { label: 'Net Profit', key: 'net_profit', format: 'money', colored: true },
  { label: 'Net Profit %', key: 'net_profit_pct', format: 'pct', colored: true },
  { label: 'Sharpe', key: 'sharpe_ratio', digits: 3 },
  { label: 'Max DD %', key: 'max_drawdown_pct', format: 'pct' },
  { label: 'Win Rate', key: 'win_rate', format: 'pct', mult: 100, digits: 1 },
  { label: 'Total Trades', key: 'total', format: 'num', digits: 0 },
]
function DeltaBadge({ orig, val, higherBetter = true }) {
  if (orig == null || val == null) return null
  const diff = val - orig
  const pct = orig !== 0 ? (diff / Math.abs(orig)) * 100 : 0
  const better = higherBetter ? diff > 0 : diff < 0
  const color = diff === 0 ? '#8b98a5' : better ? '#3fb950' : '#f85149'
  const sign = diff > 0 ? '+' : ''
  return <span style={{ fontSize: 11, color, marginLeft: 6 }}>{sign}{pct.toFixed(1)}%</span>
}

// ─── MM Sim helpers ──────────────────────────────────────────────────────────
const COLORS = ['#58a6ff', '#3fb950', '#d29922', '#f85149', '#bc8cff', '#79c0ff']
const MM_TYPES = [
  { value: 'fixed_lots', label: 'Fixed Lots' },
  { value: 'risk_pct', label: '% do Capital' },
  { value: 'fixed_risk_money', label: 'Valor Fixo $' },
]
const MM_KPI_KEYS = [
  { label: 'Net Profit', key: 'net_profit', format: 'money', colored: true },
  { label: 'Net Profit %', key: 'net_profit_pct', format: 'pct', colored: true },
  { label: 'Sharpe', key: 'sharpe_ratio', digits: 3 },
  { label: 'Max DD %', key: 'max_drawdown_pct', format: 'pct' },
  { label: 'Annual Return %', key: 'annual_return_pct', format: 'pct', colored: true },
]
let _idCtr = 0
const uid = () => ++_idCtr

export function AnalysisPage({ currentRunId, onRunIdChange }) {
  const [runs, setRuns] = useState([])
  const [runId, setRunId] = useState(currentRunId || '')
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // ─── HTM upload ─────────────────────────────────────────────────────────
  const [htmFile, setHtmFile] = useState(null)
  const [htmLabel, setHtmLabel] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadMsg, setUploadMsg] = useState('')

  const doUpload = async () => {
    if (!htmFile) return
    setUploading(true); setUploadMsg('')
    try {
      const r = await uploadReport(htmFile, { label: htmLabel || undefined })
      setUploadMsg(`${r.num_trades} trades importados. ID: ${r.run_id}`)
      await listRuns({ limit: 50 }).then(setRuns).catch(() => {})
      loadRun(r.run_id)
    } catch (e) {
      setUploadMsg(`Erro: ${errorMessage(e)}`)
    } finally { setUploading(false) }
  }

  // ─── MC state ───────────────────────────────────────────────────────────
  const [mcRuns, setMcRuns] = useState(2000)
  const [mcMode, setMcMode] = useState('shuffle')
  const [mcSeed, setMcSeed] = useState(42)
  const [mcSkipPct, setMcSkipPct] = useState(0.1)
  const [mcNoisePct, setMcNoisePct] = useState(0.1)
  const [mcResult, setMcResult] = useState(null)
  const [mcLoading, setMcLoading] = useState(false)

  // ─── Equity Control state ────────────────────────────────────────────────
  const [ecConsecLosses, setEcConsecLosses] = useState('')
  const [ecDdPct, setEcDdPct] = useState('')
  const [ecRestartDays, setEcRestartDays] = useState('')
  const [ecResult, setEcResult] = useState(null)
  const [ecLoading, setEcLoading] = useState(false)

  // ─── Robustness suite state ──────────────────────────────────────────────
  const [suiteLoading, setSuiteLoading] = useState(false)
  const [suite, setSuite] = useState(null)
  const [nTrials, setNTrials] = useState(1)
  const [varSrTrials, setVarSrTrials] = useState(0)

  // ─── What-If state ───────────────────────────────────────────────────────
  const [wiOpen, setWiOpen] = useState(false)
  const [excludedHours, setExcludedHours] = useState(new Set())
  const [excludedWeekdays, setExcludedWeekdays] = useState(new Set())
  const [wiResult, setWiResult] = useState(null)
  const [wiLoading, setWiLoading] = useState(false)

  // ─── MM Sim state ────────────────────────────────────────────────────────
  const [mmOpen, setMmOpen] = useState(false)
  const [mmScenarios, setMmScenarios] = useState([
    { id: uid(), name: 'Fixed 1 lot', mm_type: 'fixed_lots', param: 1 },
    { id: uid(), name: '2% Risk', mm_type: 'risk_pct', param: 0.02 },
  ])
  const [mmResult, setMmResult] = useState(null)
  const [mmLoading, setMmLoading] = useState(false)

  useEffect(() => {
    listRuns({ limit: 50 }).then(setRuns).catch(() => {})
  }, [])

  useEffect(() => { if (currentRunId) setRunId(currentRunId) }, [currentRunId])

  const loadRun = async (id) => {
    if (!id) return
    setLoading(true); setError(''); setMcResult(null); setEcResult(null)
    setWiResult(null); setMmResult(null); setSuite(null)
    try {
      const d = await getRunDetail(id)
      if (!d.analysis) {
        await analyze(id, d.run.deposit || 10000)
        const d2 = await getRunDetail(id)
        setDetail(d2)
      } else {
        setDetail(d)
      }
      setRunId(id)
      if (onRunIdChange) onRunIdChange(id)
    } catch (e) {
      setError(`Erro: ${e.response?.data?.detail || e.message}`)
    } finally { setLoading(false) }
  }

  // ─── What-If handlers ────────────────────────────────────────────────────
  const toggleHour = (h) => setExcludedHours(prev => {
    const next = new Set(prev); next.has(h) ? next.delete(h) : next.add(h); return next
  })
  const toggleWeekday = (d) => setExcludedWeekdays(prev => {
    const next = new Set(prev); next.has(d) ? next.delete(d) : next.add(d); return next
  })
  const doWhatIf = async () => {
    setWiLoading(true)
    try {
      const r = await runWhatIf(runId, {
        excluded_hours: [...excludedHours],
        excluded_weekdays: [...excludedWeekdays],
      })
      setWiResult(r)
    } catch (e) {
      setError(`Erro What-If: ${e.response?.data?.detail || e.message}`)
    } finally { setWiLoading(false) }
  }

  // ─── MM Sim handlers ─────────────────────────────────────────────────────
  const addScenario = () => setMmScenarios(prev => [...prev, { id: uid(), name: `Cenário ${prev.length + 1}`, mm_type: 'risk_pct', param: 0.01 }])
  const updateScenario = (id, field, value) => setMmScenarios(prev => prev.map(s => s.id === id ? { ...s, [field]: value } : s))
  const removeScenario = (id) => setMmScenarios(prev => prev.filter(s => s.id !== id))

  const doMMSim = async () => {
    setMmLoading(true)
    try {
      const r = await runMMSimulate(runId, {
        scenarios: mmScenarios.map(({ name, mm_type, param }) => ({ name, mm_type, param: +param })),
      })
      setMmResult(r)
    } catch (e) {
      setError(`Erro MM Sim: ${e.response?.data?.detail || e.message}`)
    } finally { setMmLoading(false) }
  }

  const mmChartData = useMemo(() => {
    if (!mmResult) return []
    const maxLen = Math.max(...mmResult.scenarios.map(s => s.equity_curve?.length || 0))
    return Array.from({ length: maxLen }, (_, i) => {
      const row = { i }
      mmResult.scenarios.forEach(s => { row[s.name] = s.equity_curve?.[i] ?? null })
      return row
    })
  }, [mmResult])

  // ─── Other handlers ──────────────────────────────────────────────────────
  const doMC = async () => {
    setMcLoading(true); setError('')
    try {
      const r = await runMonteCarlo({
        run_id: runId, runs: mcRuns, mode: mcMode, seed: mcSeed,
        skip_pct: mcSkipPct, noise_pct: mcNoisePct,
        initial_equity: detail?.run?.deposit || 10000,
      })
      setMcResult(r)
    } catch (e) {
      setError(`Erro MC: ${e.response?.data?.detail || e.message}`)
    } finally { setMcLoading(false) }
  }

  const doEquityControl = async () => {
    setEcLoading(true)
    try {
      const r = await runEquityControl(runId, {
        stop_after_consec_losses: ecConsecLosses ? +ecConsecLosses : null,
        stop_after_dd_pct: ecDdPct ? +ecDdPct / 100 : null,
        restart_after_days: ecRestartDays ? +ecRestartDays : null,
        initial_equity: detail?.run?.deposit || 10000,
      })
      setEcResult(r)
    } catch (e) {
      setError(`Erro equity control: ${e.response?.data?.detail || e.message}`)
    } finally { setEcLoading(false) }
  }

  const doSuite = async () => {
    setSuiteLoading(true); setError('')
    try {
      const r = await runRobustnessSuite({
        run_id: runId, initial_equity: detail?.run?.deposit || 10000,
        n_trials: nTrials, var_sr_trials: varSrTrials,
      })
      setSuite(r)
    } catch (e) {
      setError(`Erro suite: ${e.response?.data?.detail || e.message}`)
    } finally { setSuiteLoading(false) }
  }

  const analysis = detail?.analysis
  const ticksPath = detail?.run?.ticks_parquet_path || ''

  return (
    <div>
      {/* ── Importar HTM ── */}
      <div className="card">
        <h2>Importar report HTM do MT5</h2>
        <p className="muted small">
          Já rodou o backtest no MT5? Botão direito na aba <b>Back Testing</b> →
          <b> Save Report</b> (formato HTML) e faça upload aqui — vai direto pra análise.
        </p>
        <div className="row">
          <div style={{ flex: 2 }}>
            <label>Arquivo .htm</label>
            <input type="file" accept=".htm,.html"
              onChange={e => setHtmFile(e.target.files?.[0] || null)} />
          </div>
          <div style={{ flex: 2 }}>
            <label>Nome do robô / versão <span className="muted">(para comparar)</span></label>
            <input value={htmLabel} onChange={e => setHtmLabel(e.target.value)}
              placeholder="Ex: Big-Small v2 — agressivo" />
          </div>
          <div className="fit" style={{ display: 'flex', alignItems: 'flex-end' }}>
            <button disabled={!htmFile || uploading} onClick={doUpload}>
              {uploading ? 'Importando...' : 'Importar e analisar'}
            </button>
          </div>
        </div>
        {uploadMsg && (
          <div className={uploadMsg.startsWith('Erro') ? 'errbox' : 'small'}
            style={{ marginTop: 8 }}>{uploadMsg}</div>
        )}
      </div>

      {/* ── Selecionar Run existente ── */}
      <div className="card">
        <h2>Selecionar Run</h2>
        <div className="row">
          <div style={{ flex: 4 }}>
            <label>Run do histórico</label>
            <select value={runId} onChange={e => setRunId(e.target.value)}>
              <option value="">-- selecione --</option>
              {runs.map(r => (
                <option key={r.id} value={r.id}>{runOptionText(r)}</option>
              ))}
            </select>
          </div>
          <div className="fit">
            <button disabled={!runId || loading} onClick={() => loadRun(runId)}>
              {loading ? 'Carregando...' : 'Analisar'}
            </button>
          </div>
        </div>
        {error && <div className="errbox">{error}</div>}
      </div>

      {analysis && (
        <>
          {/* ── KPIs ── */}
          <div className="card">
            <h2>KPIs principais</h2>
            <div className="grid cols-4">
              {METRICS_LAYOUT.map(m => (
                <Kpi key={m.key} label={m.label}
                  value={m.key === 'win_rate' ? analysis[m.key] * 100 : analysis[m.key]}
                  format={m.format} digits={m.digits ?? 2}
                  colored={m.colored} gradeKey={m.key === 'win_rate' ? null : m.key} />
              ))}
            </div>
          </div>

          <div className="card">
            <h2>Curva de Equity</h2>
            <EquityChart values={analysis.equity_curve} />
          </div>

          <div className="card">
            <h2>Drawdown (%)</h2>
            <DrawdownChart values={analysis.drawdown_curve} />
          </div>

          <TimeBreakdown data={analysis.time_breakdown} />
          <MaeMfe data={analysis.mae_mfe} runId={runId} ticksPath={ticksPath} />

          {/* ── Long vs Short ── */}
          {analysis.direction && (
            <div className="card">
              <h2>Long vs Short</h2>
              <div className="grid cols-2" style={{ gap: 20 }}>
                {[
                  { side: 'Long (Buy)', key: 'long', color: '#3fb950' },
                  { side: 'Short (Sell)', key: 'short', color: '#f85149' },
                ].map(({ side, key, color }) => {
                  const d = analysis.direction[key]
                  if (!d) return null
                  return (
                    <div key={key} className="card" style={{ border: `1px solid ${color}33`, margin: 0 }}>
                      <div style={{ fontWeight: 600, color, marginBottom: 10 }}>{side}</div>
                      <div className="grid cols-2">
                        <Kpi label="Trades" value={d.trades} format="num" digits={0} />
                        <Kpi label="Net Profit" value={d.net_profit} format="money" colored />
                        <Kpi label="Win Rate" value={d.win_rate * 100} format="pct" digits={1} />
                        <Kpi label="Profit Factor" value={d.profit_factor} digits={2} />
                        <Kpi label="Avg Win" value={d.avg_win} format="money" colored />
                        <Kpi label="Avg Loss" value={d.avg_loss} format="money" colored />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* ── Risk of Ruin ── */}
          {analysis.risk_of_ruin?.length > 0 && (
            <div className="card">
              <h2>Risk of Ruin</h2>
              <p className="muted small">Probabilidade de perder todo o capital para diferentes % de risco por trade.</p>
              <table>
                <thead><tr><th>% Risco / Trade</th><th>Prob. de Ruína</th><th></th></tr></thead>
                <tbody>
                  {analysis.risk_of_ruin.map(row => {
                    const pct = row.ruin_probability * 100
                    const bg = pct < 5 ? 'rgba(56,139,56,0.12)' : pct <= 20 ? 'rgba(210,153,34,0.12)' : 'rgba(248,81,73,0.12)'
                    const color = pct < 5 ? '#3fb950' : pct <= 20 ? '#d29922' : '#f85149'
                    return (
                      <tr key={row.risk_pct_label} style={{ background: bg }}>
                        <td>{row.risk_pct_label}</td>
                        <td style={{ color, fontWeight: 600 }}>{pct.toFixed(1)}%</td>
                        <td className="small muted">{pct < 5 ? 'Baixo risco' : pct <= 20 ? 'Atenção' : 'Alto risco'}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* ── Estagnação ── */}
          {analysis.stagnation && (
            <div className="card">
              <h2>Estagnação</h2>
              <p className="muted small">Períodos em que a equity ficou abaixo do pico anterior.</p>
              <div className="grid cols-4" style={{ marginBottom: 16 }}>
                <Kpi label="Estagnação máx." value={analysis.stagnation.max_stagnation_days} format="num" digits={0} />
                <Kpi label="Estagnação média" value={analysis.stagnation.avg_stagnation_days} digits={1} />
                <Kpi label="% período estagnado" value={analysis.stagnation.stagnation_pct_of_period * 100} format="pct" digits={1} />
                <Kpi label="Períodos" value={analysis.stagnation.stagnation_periods?.length || 0} format="num" digits={0} />
              </div>
              <StagnationChart values={analysis.equity_curve} periods={analysis.stagnation.stagnation_periods || []} />
            </div>
          )}

          {/* ── What-If ── */}
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
              onClick={() => setWiOpen(o => !o)}>
              <h2 style={{ margin: 0 }}>What-If Analysis</h2>
              <span className="muted" style={{ fontSize: 18 }}>{wiOpen ? '▲' : '▼'}</span>
            </div>
            {wiOpen && (
              <>
                <p className="muted small" style={{ marginTop: 8 }}>
                  Simula a performance excluindo certas horas ou dias da semana.
                </p>
                <div style={{ marginTop: 12 }}>
                  <div className="muted small" style={{ marginBottom: 6 }}>Horas a excluir (marcado = excluído)</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {HOURS.map(h => (
                      <label key={h} style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer', fontSize: 12 }}>
                        <input type="checkbox" checked={excludedHours.has(h)} onChange={() => toggleHour(h)} />
                        {String(h).padStart(2, '0')}h
                      </label>
                    ))}
                  </div>
                </div>
                <div style={{ marginTop: 12 }}>
                  <div className="muted small" style={{ marginBottom: 6 }}>Dias a excluir</div>
                  <div style={{ display: 'flex', gap: 12 }}>
                    {WEEKDAYS.map(d => (
                      <label key={d.num} style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer', fontSize: 13 }}>
                        <input type="checkbox" checked={excludedWeekdays.has(d.num)} onChange={() => toggleWeekday(d.num)} />
                        {d.label}
                      </label>
                    ))}
                  </div>
                </div>
                <div style={{ marginTop: 14 }}>
                  <ContextualTooltip text="Vê como ficaria o resultado sem essas horas/dias">
                    <button disabled={wiLoading} onClick={doWhatIf}>
                      {wiLoading ? 'Simulando...' : 'Simular'}
                    </button>
                  </ContextualTooltip>
                </div>
                {wiResult && wiResult.original && wiResult.whatif && (
                  <div style={{ marginTop: 14 }}>
                    <div className="muted small" style={{ marginBottom: 10 }}>
                      {wiResult.excluded_trades} trades excluídos · {wiResult.remaining_trades} trades restantes
                    </div>
                    <div className="grid cols-2" style={{ gap: 20 }}>
                      <div>
                        <div style={{ fontWeight: 600, marginBottom: 10, color: '#8b98a5' }}>
                          Original ({wiResult.original.total} trades)
                        </div>
                        <div className="grid cols-2">
                          {WI_KEYS.map(m => {
                            const v = m.mult ? (wiResult.original[m.key] || 0) * m.mult : (wiResult.original[m.key] || 0)
                            return <Kpi key={m.key} label={m.label} value={v} format={m.format} digits={m.digits ?? 2} colored={m.colored} />
                          })}
                        </div>
                      </div>
                      <div>
                        <div style={{ fontWeight: 600, marginBottom: 10, color: '#58a6ff' }}>
                          What-If ({wiResult.whatif.total} trades)
                        </div>
                        <div className="grid cols-2">
                          {WI_KEYS.map(m => {
                            const wi = m.mult ? (wiResult.whatif[m.key] || 0) * m.mult : (wiResult.whatif[m.key] || 0)
                            const orig = m.mult ? (wiResult.original[m.key] || 0) * m.mult : (wiResult.original[m.key] || 0)
                            return (
                              <div key={m.key}>
                                <Kpi label={m.label} value={wi} format={m.format} digits={m.digits ?? 2} colored={m.colored} />
                                <DeltaBadge orig={orig} val={wi} higherBetter={m.key !== 'max_drawdown_pct'} />
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>

          {/* ── MM Simulator ── */}
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
              onClick={() => setMmOpen(o => !o)}>
              <h2 style={{ margin: 0 }}>Money Management Simulator</h2>
              <span className="muted" style={{ fontSize: 18 }}>{mmOpen ? '▲' : '▼'}</span>
            </div>
            {mmOpen && (
              <>
                <p className="muted small" style={{ marginTop: 8 }}>
                  Compara como a mesma estratégia teria performado com diferentes regras de sizing.
                </p>
                <table style={{ marginTop: 12 }}>
                  <thead><tr><th>Nome</th><th>Tipo</th><th>Parâmetro</th><th></th></tr></thead>
                  <tbody>
                    {mmScenarios.map(s => (
                      <tr key={s.id}>
                        <td><input value={s.name} onChange={e => updateScenario(s.id, 'name', e.target.value)} style={{ width: '100%' }} /></td>
                        <td>
                          <select value={s.mm_type} onChange={e => updateScenario(s.id, 'mm_type', e.target.value)}>
                            {MM_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                          </select>
                        </td>
                        <td>
                          <input type="number" step="0.001" value={s.param}
                            onChange={e => updateScenario(s.id, 'param', e.target.value)} style={{ width: 90 }} />
                          <span className="muted small" style={{ marginLeft: 4 }}>
                            {s.mm_type === 'risk_pct' ? '(ex: 0.02 = 2%)' : s.mm_type === 'fixed_lots' ? 'lotes' : '$'}
                          </span>
                        </td>
                        <td><button onClick={() => removeScenario(s.id)} style={{ padding: '2px 8px', fontSize: 12 }}>✕</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="row" style={{ marginTop: 12, gap: 8 }}>
                  <button onClick={addScenario} style={{ fontSize: 12 }}>+ Cenário</button>
                  <ContextualTooltip text="Compara curvas de equity com diferentes tamanhos de posição">
                    <button disabled={mmLoading || !mmScenarios.length} onClick={doMMSim}>
                      {mmLoading ? 'Simulando...' : 'Simular'}
                    </button>
                  </ContextualTooltip>
                </div>
                {mmResult && (
                  <>
                    <div style={{ marginTop: 14 }}>
                      <div className="muted small" style={{ marginBottom: 6 }}>Curvas de Equity comparativas</div>
                      <ResponsiveContainer width="100%" height={260}>
                        <LineChart data={mmChartData}>
                          <CartesianGrid stroke="#1f2a37" strokeDasharray="3 3" />
                          <XAxis dataKey="i" {...axisProps} />
                          <YAxis {...axisProps} domain={['auto', 'auto']} />
                          <Tooltip contentStyle={tooltipStyle.contentStyle} />
                          <Legend wrapperStyle={{ fontSize: 12 }} />
                          {mmResult.scenarios.map((s, i) => (
                            <Line key={s.name} type="monotone" dataKey={s.name}
                              stroke={COLORS[i % COLORS.length]} dot={false} strokeWidth={2} connectNulls />
                          ))}
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                    <table style={{ marginTop: 12 }}>
                      <thead>
                        <tr><th>Cenário</th>{MM_KPI_KEYS.map(k => <th key={k.key}>{k.label}</th>)}</tr>
                      </thead>
                      <tbody>
                        {mmResult.scenarios.map((s, i) => (
                          <tr key={s.name}>
                            <td style={{ color: COLORS[i % COLORS.length] }}><b>{s.name}</b></td>
                            {MM_KPI_KEYS.map(k => {
                              const v = s.metrics?.[k.key]
                              const color = k.colored ? (v > 0 ? '#3fb950' : v < 0 ? '#f85149' : undefined) : undefined
                              const fmt = (val) => {
                                if (val == null) return '—'
                                if (k.format === 'money') return val.toFixed(2)
                                if (k.format === 'pct') return val.toFixed(1) + '%'
                                return val.toFixed(k.digits ?? 2)
                              }
                              return <td key={k.key} style={{ color }}>{fmt(v)}</td>
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </>
                )}
              </>
            )}
          </div>

          {/* ── Equity Control ── */}
          <div className="card">
            <h2>Equity Control</h2>
            <p className="muted small">Aplica regras de stop/restart retroativamente e compara com a curva original.</p>
            <div className="row">
              <div>
                <label>Parar após X perdas consecutivas</label>
                <input type="number" min="1" placeholder="ex: 3"
                  value={ecConsecLosses} onChange={e => setEcConsecLosses(e.target.value)} />
              </div>
              <div>
                <label>Parar após DD de X%</label>
                <input type="number" min="0" max="100" step="0.5" placeholder="ex: 10"
                  value={ecDdPct} onChange={e => setEcDdPct(e.target.value)} />
              </div>
              <div>
                <label>Reiniciar após X dias</label>
                <input type="number" min="1" placeholder="ex: 20"
                  value={ecRestartDays} onChange={e => setEcRestartDays(e.target.value)} />
              </div>
              <div className="fit" style={{ display: 'flex', alignItems: 'flex-end' }}>
                <ContextualTooltip text="Pausa trades após perdas ou drawdown para simular gestão de risco">
                  <button disabled={ecLoading || !runId} onClick={doEquityControl}>
                    {ecLoading ? 'Aplicando...' : 'Aplicar'}
                  </button>
                </ContextualTooltip>
              </div>
            </div>
            {ecResult && (
              <>
                <div style={{ marginTop: 12 }}>
                  <span className="pill pos">{ecResult.skipped_trades} trades pausados</span>
                </div>
                <div style={{ marginTop: 14 }}>
                  <div className="muted small" style={{ marginBottom: 6 }}>Cinza = original · Azul = controlado</div>
                  <ResponsiveContainer width="100%" height={260}>
                    <LineChart margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                      <CartesianGrid stroke="#1f2a37" strokeDasharray="3 3" />
                      <XAxis dataKey="i" type="number" {...axisProps}
                        domain={[0, Math.max(ecResult.original_equity.length, ecResult.controlled_equity.length) - 1]} />
                      <YAxis {...axisProps} domain={['auto', 'auto']} />
                      <Tooltip {...tooltipStyle} />
                      <Line data={ecResult.original_equity.map((v, i) => ({ i, v }))}
                        type="monotone" dataKey="v" name="Original" stroke="#8b98a5" dot={false} strokeWidth={1.5} />
                      <Line data={ecResult.controlled_equity.map((v, i) => ({ i, v }))}
                        type="monotone" dataKey="v" name="Controlado" stroke="#58a6ff" dot={false} strokeWidth={2} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <div className="grid cols-2" style={{ marginTop: 16, gap: 20 }}>
                  {[
                    { label: 'Original', m: ecResult.metrics_original, color: '#8b98a5' },
                    { label: 'Controlado', m: ecResult.metrics_controlled, color: '#58a6ff' },
                  ].map(({ label, m, color }) => m && (
                    <div key={label}>
                      <div style={{ color, fontWeight: 600, marginBottom: 8 }}>{label}</div>
                      <div className="grid cols-2">
                        <Kpi label="Net Profit" value={m.net_profit} format="money" colored />
                        <Kpi label="Max DD %" value={m.max_drawdown_pct} format="pct" />
                        <Kpi label="Sharpe" value={m.sharpe_ratio} digits={3} />
                        <Kpi label="Win Rate" value={(m.win_rate || 0) * 100} format="pct" digits={1} />
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* ── Validações Simons ── */}
          <StatValidation runId={runId} />

          {/* ── MC com ticks reais ── */}
          <TickMonteCarlo runId={runId} ticksPath={ticksPath} />

          {/* ── Suite de Robustez ── */}
          <div className="card">
            <h2>Suite de Robustez (bateria completa)</h2>
            <p className="muted small">
              Roda MC (shuffle, bootstrap, block bootstrap, skip, noise) + PSR/DSR +
              MinTRL + análise por ano, tudo de uma vez, e emite scorecard.
            </p>
            <div className="row">
              <div>
                <label>Nº candidatos testados (otimização)</label>
                <input type="number" min="1" value={nTrials}
                  onChange={e => setNTrials(+e.target.value)} placeholder="ex: 3663" />
              </div>
              <div>
                <label>Variância dos Sharpes entre candidatos</label>
                <input type="number" step="0.0001" min="0" value={varSrTrials}
                  onChange={e => setVarSrTrials(+e.target.value)} placeholder="0 = sem DSR" />
              </div>
              <div className="fit" style={{ display: 'flex', alignItems: 'flex-end' }}>
                <ContextualTooltip text="Testa MC, PSR/DSR, MinTRL, análise por ano — resultado definitivo">
                  <button disabled={suiteLoading} onClick={doSuite}>
                    {suiteLoading ? 'Rodando...' : 'Rodar suite'}
                  </button>
                </ContextualTooltip>
              </div>
            </div>
            <p className="muted small" style={{ marginTop: 4 }}>
              Deixe <b>Nº candidatos=1</b> se esse backtest não veio de otimização.
            </p>
            {suite && (
              <div style={{ marginTop: 16 }}>
                <div style={{
                  padding: 12, borderRadius: 8, marginBottom: 14,
                  background: suite.overall === 'green' ? 'rgba(56,139,56,0.15)' : suite.overall === 'yellow' ? 'rgba(210,153,34,0.15)' : 'rgba(210,54,54,0.15)',
                  border: '1px solid ' + (suite.overall === 'green' ? '#388b38' : suite.overall === 'yellow' ? '#d29922' : '#d23636'),
                }}>
                  <b style={{ fontSize: 16 }}>
                    {suite.overall === 'green' ? '🟢 ROBUSTA' : suite.overall === 'yellow' ? '🟡 ATENÇÃO' : '🔴 FRÁGIL'}
                    &nbsp;— {suite.passes}/{suite.total} checks passaram
                  </b>
                </div>
                <table>
                  <thead><tr><th>Teste</th><th>Status</th><th>Valor</th><th>Nota</th></tr></thead>
                  <tbody>
                    {suite.scorecard.map((c, i) => (
                      <tr key={i}>
                        <td>{c.name}</td>
                        <td><span className={'pill ' + (c.status === 'pass' ? 'pos' : 'neg')}>{c.status === 'pass' ? 'PASS' : 'FAIL'}</span></td>
                        <td><code>{c.value}</code></td>
                        <td className="small muted">
                          {c.note}
                          {c.status === 'fail' && c.suggestion && (
                            <div style={{ marginTop: 6, padding: '6px 8px', background: 'rgba(210,153,34,0.08)', border: '1px solid rgba(210,153,34,0.3)', borderRadius: 4, color: '#d6cda2', fontSize: 11 }}>
                              <b style={{ color: '#d29922' }}>💡 </b>{c.suggestion}
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <h3 style={{ color: 'var(--muted)', fontSize: 13, marginTop: 20 }}>Monte Carlo — todos os modos</h3>
                <table>
                  <thead><tr><th>Modo</th><th>Prob. lucro</th><th>Net P5</th><th>Net P50</th><th>Net P95</th><th>DD P50 %</th><th>DD P95 %</th></tr></thead>
                  <tbody>
                    {Object.entries(suite.mc).map(([mode, r]) => (
                      <tr key={mode}>
                        <td><code>{mode}</code></td>
                        <td>{(r.prob_profitable * 100).toFixed(1)}%</td>
                        <td>{r.net_p5.toFixed(2)}</td>
                        <td>{r.net_p50.toFixed(2)}</td>
                        <td>{r.net_p95.toFixed(2)}</td>
                        <td>{r.dd_p50.toFixed(2)}</td>
                        <td>{r.dd_p95.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {suite.regime_by_year?.length > 0 && (
                  <>
                    <h3 style={{ color: 'var(--muted)', fontSize: 13, marginTop: 20 }}>Performance por ano (regime analysis)</h3>
                    <table>
                      <thead><tr><th>Ano</th><th>Trades</th><th>Net Profit</th><th>Win Rate</th><th>Max DD %</th><th>Sharpe (anual)</th></tr></thead>
                      <tbody>
                        {suite.regime_by_year.map(r => (
                          <tr key={r.year}>
                            <td>{r.year}</td>
                            <td>{r.trades}</td>
                            <td style={{ color: r.net_profit >= 0 ? '#3fb950' : '#f85149' }}>{r.net_profit.toFixed(2)}</td>
                            <td>{(r.win_rate * 100).toFixed(1)}%</td>
                            <td>{r.max_dd_pct.toFixed(2)}%</td>
                            <td>{r.sharpe_annual.toFixed(3)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </>
                )}
                <div className="grid cols-4" style={{ marginTop: 14 }}>
                  <Kpi label="Sharpe anual" value={suite.sharpe_annualized} digits={3} gradeKey="sharpe_ratio" />
                  <Kpi label="PSR (SR>0)" value={suite.psr_0} digits={3} gradeKey="psr_0" />
                  <Kpi label="DSR" value={suite.dsr.dsr} digits={3} gradeKey="dsr" />
                  <Kpi label="MinTRL" value={suite.mintrl} digits={0} gradeKey="mintrl" />
                </div>
              </div>
            )}
          </div>

          {/* ── Monte Carlo Sintético ── */}
          <div className="card">
            <h2>Monte Carlo</h2>
            <div className="row">
              <div><label>Runs</label><input type="number" value={mcRuns} onChange={e => setMcRuns(+e.target.value)} /></div>
              <div><label>Modo</label>
                <select value={mcMode} onChange={e => setMcMode(e.target.value)}>
                  <option value="shuffle">shuffle (permutação)</option>
                  <option value="bootstrap">bootstrap (reamostragem)</option>
                  <option value="skip">skip (remove % trades)</option>
                  <option value="noise">noise (slippage ± %)</option>
                </select>
              </div>
              <div><label>Seed</label><input type="number" value={mcSeed} onChange={e => setMcSeed(+e.target.value)} /></div>
              {mcMode === 'skip' && (
                <div>
                  <label>% a remover ({(mcSkipPct * 100).toFixed(0)}%)</label>
                  <input type="range" min="0.01" max="0.5" step="0.01"
                    value={mcSkipPct} onChange={e => setMcSkipPct(+e.target.value)} />
                </div>
              )}
              {mcMode === 'noise' && (
                <div>
                  <label>Amplitude ± ({(mcNoisePct * 100).toFixed(0)}%)</label>
                  <input type="range" min="0.01" max="1" step="0.01"
                    value={mcNoisePct} onChange={e => setMcNoisePct(+e.target.value)} />
                </div>
              )}
              <div className="fit"><ContextualTooltip text="Simula cenários futuros com diferentes ordens/distribuições de trades"><button disabled={mcLoading} onClick={doMC}>{mcLoading ? 'Simulando...' : 'Rodar MC'}</button></ContextualTooltip></div>
            </div>
            <p className="muted small" style={{ marginTop: 6 }}>
              <b>shuffle:</b> testa dependência da ordem · <b>bootstrap:</b> distribuição futura ·
              <b> skip:</b> robustez a perda de sinais · <b>noise:</b> sensibilidade a slippage
            </p>
            {mcResult && (
              <>
                <div className="grid cols-4" style={{ marginTop: 14 }}>
                  <Kpi label="Net P5" value={mcResult.net_profit_p5} format="money" colored />
                  <Kpi label="Net P50" value={mcResult.net_profit_p50} format="money" colored />
                  <Kpi label="Net P95" value={mcResult.net_profit_p95} format="money" colored />
                  <Kpi label="Prob. Lucro" value={mcResult.prob_profitable * 100} format="pct" digits={1} />
                  <Kpi label="DD P5 %" value={mcResult.max_dd_pct_p5} format="pct" />
                  <Kpi label="DD P50 %" value={mcResult.max_dd_pct_p50} format="pct" />
                  <Kpi label="DD P95 %" value={mcResult.max_dd_pct_p95} format="pct" />
                  <Kpi label="Prob DD > orig." value={mcResult.prob_dd_exceeds_original} digits={3} gradeKey="prob_dd_exceeds_original" />
                </div>
                <div className="grid cols-2" style={{ marginTop: 14 }}>
                  <div>
                    <div className="muted small" style={{ marginBottom: 6 }}>Distribuição de Net Profit</div>
                    <HistogramChart edges={mcResult.net_profit_hist.edges} counts={mcResult.net_profit_hist.counts} />
                  </div>
                  <div>
                    <div className="muted small" style={{ marginBottom: 6 }}>Distribuição de Max DD %</div>
                    <HistogramChart edges={mcResult.max_dd_hist.edges} counts={mcResult.max_dd_hist.counts} color="#f85149" />
                  </div>
                </div>
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}
