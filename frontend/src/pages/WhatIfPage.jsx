import { useEffect, useState } from 'react'
import { listRuns, runWhatIf } from '../services/api'
import { Kpi } from '../components/Kpi'
import { runOptionText } from '../services/runLabel'

const HOURS = Array.from({ length: 24 }, (_, i) => i)
const WEEKDAYS = [
  { num: 0, label: 'Seg' }, { num: 1, label: 'Ter' }, { num: 2, label: 'Qua' },
  { num: 3, label: 'Qui' }, { num: 4, label: 'Sex' }, { num: 5, label: 'Sáb' }, { num: 6, label: 'Dom' },
]

const KPI_KEYS = [
  { label: 'Net Profit', key: 'net_profit', format: 'money', colored: true },
  { label: 'Net Profit %', key: 'net_profit_pct', format: 'pct', colored: true },
  { label: 'Sharpe', key: 'sharpe_ratio', digits: 3 },
  { label: 'Max DD %', key: 'max_drawdown_pct', format: 'pct' },
  { label: 'Win Rate', key: 'win_rate', format: 'pct', mult: 100, digits: 1 },
  { label: 'Total Trades', key: 'total', format: 'num', digits: 0 },
]

function DeltaBadge({ orig, val, higher_is_better = true }) {
  if (orig == null || val == null) return null
  const diff = val - orig
  const pct = orig !== 0 ? (diff / Math.abs(orig)) * 100 : 0
  const better = higher_is_better ? diff > 0 : diff < 0
  const color = diff === 0 ? '#8b98a5' : better ? '#3fb950' : '#f85149'
  const sign = diff > 0 ? '+' : ''
  return (
    <span style={{ fontSize: 11, color, marginLeft: 6 }}>
      {sign}{pct.toFixed(1)}%
    </span>
  )
}

export function WhatIfPage() {
  const [runs, setRuns] = useState([])
  const [runId, setRunId] = useState('')
  const [excludedHours, setExcludedHours] = useState(new Set())
  const [excludedWeekdays, setExcludedWeekdays] = useState(new Set())
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    listRuns({ limit: 50 }).then(setRuns).catch(() => {})
  }, [])

  const toggleHour = (h) => setExcludedHours(prev => {
    const next = new Set(prev)
    next.has(h) ? next.delete(h) : next.add(h)
    return next
  })

  const toggleWeekday = (d) => setExcludedWeekdays(prev => {
    const next = new Set(prev)
    next.has(d) ? next.delete(d) : next.add(d)
    return next
  })

  const simulate = async () => {
    if (!runId) return
    setLoading(true); setError(''); setResult(null)
    try {
      const r = await runWhatIf(runId, {
        excluded_hours: [...excludedHours],
        excluded_weekdays: [...excludedWeekdays],
      })
      setResult(r)
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally { setLoading(false) }
  }

  const orig = result?.original
  const wi = result?.whatif

  return (
    <div>
      <div className="card">
        <h2>What-If Analysis</h2>
        <p className="muted small">Simula como seria a performance excluindo certas horas ou dias da semana.</p>
        <div className="row">
          <div style={{ flex: 3 }}>
            <label>Run</label>
            <select value={runId} onChange={e => setRunId(e.target.value)}>
              <option value="">-- selecione --</option>
              {runs.map(r => <option key={r.id} value={r.id}>{runOptionText(r)}</option>)}
            </select>
          </div>
        </div>

        <div style={{ marginTop: 16 }}>
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
          <button disabled={!runId || loading} onClick={simulate}>
            {loading ? 'Simulando...' : 'Simular'}
          </button>
        </div>
        {error && <div className="errbox" style={{ marginTop: 8 }}>{error}</div>}
      </div>

      {result && orig && wi && (
        <div className="card">
          <h2>Resultado</h2>
          <div className="muted small" style={{ marginBottom: 12 }}>
            {result.excluded_trades} trades excluídos · {result.remaining_trades} trades restantes
          </div>
          <div className="grid cols-2" style={{ gap: 20 }}>
            <div>
              <div style={{ fontWeight: 600, marginBottom: 10, color: '#8b98a5' }}>Original ({orig.total} trades)</div>
              <div className="grid cols-2">
                {KPI_KEYS.map(m => {
                  const v = m.mult ? (orig[m.key] || 0) * m.mult : (orig[m.key] || 0)
                  return <Kpi key={m.key} label={m.label} value={v} format={m.format} digits={m.digits ?? 2} colored={m.colored} />
                })}
              </div>
            </div>
            <div>
              <div style={{ fontWeight: 600, marginBottom: 10, color: '#58a6ff' }}>What-If ({wi.total} trades)</div>
              <div className="grid cols-2">
                {KPI_KEYS.map(m => {
                  const v = m.mult ? (wi[m.key] || 0) * m.mult : (wi[m.key] || 0)
                  const origV = m.mult ? (orig[m.key] || 0) * m.mult : (orig[m.key] || 0)
                  const higherBetter = !['max_drawdown_pct'].includes(m.key)
                  return (
                    <div key={m.key}>
                      <Kpi label={m.label} value={v} format={m.format} digits={m.digits ?? 2} colored={m.colored} />
                      <DeltaBadge orig={origV} val={v} higher_is_better={higherBetter} />
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
