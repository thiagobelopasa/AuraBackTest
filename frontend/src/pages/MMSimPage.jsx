import { useEffect, useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  Tooltip, CartesianGrid, Legend,
} from 'recharts'
import { listRuns, runMMSimulate } from '../services/api'
import { Kpi } from '../components/Kpi'
import { runOptionText } from '../services/runLabel'

const axisProps = { stroke: '#8b98a5', tick: { fontSize: 11 } }
const tooltipStyle = {
  contentStyle: { background: '#0b0f14', border: '1px solid #1f2a37', fontSize: 12 },
}
const COLORS = ['#58a6ff', '#3fb950', '#d29922', '#f85149', '#bc8cff', '#79c0ff']
const MM_TYPES = [
  { value: 'fixed_lots', label: 'Fixed Lots' },
  { value: 'risk_pct', label: '% do Capital' },
  { value: 'fixed_risk_money', label: 'Valor Fixo $' },
]

const KPI_KEYS = [
  { label: 'Net Profit', key: 'net_profit', format: 'money', colored: true },
  { label: 'Net Profit %', key: 'net_profit_pct', format: 'pct', colored: true },
  { label: 'Sharpe', key: 'sharpe_ratio', digits: 3 },
  { label: 'Max DD %', key: 'max_drawdown_pct', format: 'pct' },
  { label: 'Annual Return %', key: 'annual_return_pct', format: 'pct', colored: true },
]

let _idCounter = 0
const uid = () => ++_idCounter

export function MMSimPage() {
  const [runs, setRuns] = useState([])
  const [runId, setRunId] = useState('')
  const [scenarios, setScenarios] = useState([
    { id: uid(), name: 'Fixed 1 lot', mm_type: 'fixed_lots', param: 1 },
    { id: uid(), name: '2% Risk', mm_type: 'risk_pct', param: 0.02 },
  ])
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    listRuns({ limit: 50 }).then(setRuns).catch(() => {})
  }, [])

  const addScenario = () => setScenarios(prev => [
    ...prev,
    { id: uid(), name: `Cenário ${prev.length + 1}`, mm_type: 'risk_pct', param: 0.01 },
  ])

  const updateScenario = (id, field, value) =>
    setScenarios(prev => prev.map(s => s.id === id ? { ...s, [field]: value } : s))

  const removeScenario = (id) =>
    setScenarios(prev => prev.filter(s => s.id !== id))

  const simulate = async () => {
    if (!runId || !scenarios.length) return
    setLoading(true); setError(''); setResult(null)
    try {
      const r = await runMMSimulate(runId, {
        scenarios: scenarios.map(({ name, mm_type, param }) => ({ name, mm_type, param: +param })),
      })
      setResult(r)
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally { setLoading(false) }
  }

  const maxLen = result?.scenarios
    ? Math.max(...result.scenarios.map(s => s.equity_curve?.length || 0))
    : 0

  const chartData = maxLen > 0
    ? Array.from({ length: maxLen }, (_, i) => {
        const row = { i }
        result.scenarios.forEach(s => {
          row[s.name] = s.equity_curve?.[i] ?? null
        })
        return row
      })
    : []

  return (
    <div>
      <div className="card">
        <h2>Money Management Simulator</h2>
        <p className="muted small">Compara como a mesma estratégia teria performado com diferentes regras de dimensionamento.</p>

        <div className="row" style={{ marginBottom: 12 }}>
          <div style={{ flex: 3 }}>
            <label>Run</label>
            <select value={runId} onChange={e => setRunId(e.target.value)}>
              <option value="">-- selecione --</option>
              {runs.map(r => <option key={r.id} value={r.id}>{runOptionText(r)}</option>)}
            </select>
          </div>
        </div>

        <table>
          <thead>
            <tr>
              <th>Nome</th><th>Tipo</th><th>Parâmetro</th><th></th>
            </tr>
          </thead>
          <tbody>
            {scenarios.map(s => (
              <tr key={s.id}>
                <td>
                  <input value={s.name} onChange={e => updateScenario(s.id, 'name', e.target.value)}
                    style={{ width: '100%' }} />
                </td>
                <td>
                  <select value={s.mm_type} onChange={e => updateScenario(s.id, 'mm_type', e.target.value)}>
                    {MM_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                  </select>
                </td>
                <td>
                  <input type="number" step="0.001" value={s.param}
                    onChange={e => updateScenario(s.id, 'param', e.target.value)}
                    style={{ width: 90 }} />
                  <span className="muted small" style={{ marginLeft: 4 }}>
                    {s.mm_type === 'risk_pct' ? '(ex: 0.02 = 2%)'
                      : s.mm_type === 'fixed_lots' ? 'lotes'
                      : '$'}
                  </span>
                </td>
                <td>
                  <button onClick={() => removeScenario(s.id)}
                    style={{ padding: '2px 8px', fontSize: 12 }}>✕</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="row" style={{ marginTop: 12, gap: 8 }}>
          <button onClick={addScenario} style={{ fontSize: 12 }}>+ Adicionar cenário</button>
          <button disabled={!runId || loading || !scenarios.length} onClick={simulate}>
            {loading ? 'Simulando...' : 'Simular'}
          </button>
        </div>
        {error && <div className="errbox" style={{ marginTop: 8 }}>{error}</div>}
      </div>

      {result && (
        <>
          <div className="card">
            <h2>Curvas de Equity</h2>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData}>
                <CartesianGrid stroke="#1f2a37" strokeDasharray="3 3" />
                <XAxis dataKey="i" {...axisProps} />
                <YAxis {...axisProps} domain={['auto', 'auto']} />
                <Tooltip {...tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {result.scenarios.map((s, i) => (
                  <Line key={s.name} type="monotone" dataKey={s.name}
                    stroke={COLORS[i % COLORS.length]} dot={false} strokeWidth={2}
                    connectNulls />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="card">
            <h2>KPIs Comparativos</h2>
            <table>
              <thead>
                <tr>
                  <th>Cenário</th>
                  {KPI_KEYS.map(k => <th key={k.key}>{k.label}</th>)}
                </tr>
              </thead>
              <tbody>
                {result.scenarios.map((s, i) => (
                  <tr key={s.name}>
                    <td style={{ color: COLORS[i % COLORS.length] }}><b>{s.name}</b></td>
                    {KPI_KEYS.map(k => {
                      const v = s.metrics?.[k.key]
                      const colored = k.colored
                      const fmt = (val) => {
                        if (val == null) return '—'
                        if (k.format === 'money') return val.toFixed(2)
                        if (k.format === 'pct') return val.toFixed(1) + '%'
                        return val.toFixed(k.digits ?? 2)
                      }
                      const color = colored
                        ? (v > 0 ? '#3fb950' : v < 0 ? '#f85149' : undefined)
                        : undefined
                      return <td key={k.key} style={{ color }}>{fmt(v)}</td>
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
