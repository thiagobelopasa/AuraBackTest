import { useEffect, useRef, useState } from 'react'
import { InstallationPicker } from '../components/InstallationPicker'
import { wfaAutoStart, wfaAutoJob, errorMessage } from '../services/api'

const SCORE_KEYS = [
  { value: 'profit_factor', label: 'Profit Factor' },
  { value: 'sharpe_ratio', label: 'Sharpe Ratio' },
  { value: 'sortino_ratio', label: 'Sortino Ratio' },
  { value: 'net_profit', label: 'Net Profit' },
  { value: 'recovery_factor', label: 'Recovery Factor' },
]

const PERIODS = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1']

function statusColor(status) {
  if (status === 'done') return '#3fb950'
  if (status === 'error') return '#f85149'
  if (status === 'running') return '#d29922'
  return '#8b949e'
}

function ScoreBar({ is_, oos, max }) {
  if (!max || max === 0) return null
  const isW = Math.min(100, (is_ / max) * 100)
  const oosW = Math.min(100, (oos / max) * 100)
  const oosColor = oos >= is_ ? '#3fb950' : '#f85149'
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ width: 30, fontSize: 10, color: '#8b949e', textAlign: 'right' }}>IS</span>
        <div style={{ flex: 1, background: '#21262d', borderRadius: 3, height: 10 }}>
          <div style={{ width: `${isW}%`, background: '#1f6feb', height: '100%', borderRadius: 3 }} />
        </div>
        <span style={{ width: 52, fontSize: 11 }}>{is_.toFixed(3)}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ width: 30, fontSize: 10, color: '#8b949e', textAlign: 'right' }}>OOS</span>
        <div style={{ flex: 1, background: '#21262d', borderRadius: 3, height: 10 }}>
          <div style={{ width: `${oosW}%`, background: oosColor, height: '100%', borderRadius: 3 }} />
        </div>
        <span style={{ width: 52, fontSize: 11, color: oosColor }}>{oos.toFixed(3)}</span>
      </div>
    </div>
  )
}

export function WFAPage({ onOpenRun }) {
  const [installation, setInstallation] = useState(null)
  const [expert, setExpert] = useState(null)

  const [symbol, setSymbol] = useState('EURUSD')
  const [period, setPeriod] = useState('M1')
  const [startDate, setStartDate] = useState('2022-01-01')
  const [endDate, setEndDate] = useState('2024-12-31')
  const [folds, setFolds] = useState(4)
  const [oosPct, setOosPct] = useState(25)
  const [anchored, setAnchored] = useState(false)
  const [scoreKey, setScoreKey] = useState('profit_factor')
  const [topN, setTopN] = useState(3)

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [job, setJob] = useState(null)
  const pollRef = useRef(null)

  useEffect(() => () => clearInterval(pollRef.current), [])

  const startPolling = (jobId) => {
    clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const j = await wfaAutoJob(jobId)
        setJob(j)
        if (j.status === 'done' || j.status === 'error') {
          clearInterval(pollRef.current)
          setLoading(false)
        }
      } catch {
        clearInterval(pollRef.current)
        setLoading(false)
      }
    }, 3000)
  }

  const handleStart = async () => {
    if (!installation || !expert) { setError('Selecione instalação e EA'); return }
    setError(''); setLoading(true); setJob(null)
    try {
      const j = await wfaAutoStart({
        terminal_exe: installation.terminal_exe,
        data_folder: installation.data_folder,
        ea_relative_path: expert.relative_path,
        ea_inputs_defaults: {},
        ranges: [],
        symbol,
        period,
        start_date: startDate,
        end_date: endDate,
        folds,
        oos_pct: oosPct / 100,
        anchored,
        deposit: 10000,
        top_n: topN,
        score_key: scoreKey,
      })
      setJob(j)
      startPolling(j.job_id)
    } catch (e) {
      setError(errorMessage(e))
      setLoading(false)
    }
  }

  // Calcula max IS pra normalizar barras
  const maxIS = job
    ? Math.max(...(job.is_results || []).map(r => Math.abs(r.mean)), 0.001)
    : 0

  const stabilityColor = (v) => {
    if (v === null || v === undefined) return '#8b949e'
    if (v >= 0.75) return '#3fb950'
    if (v >= 0.5) return '#d29922'
    return '#f85149'
  }

  return (
    <div>
      <div className="card">
        <h2>Walk-Forward Analysis — automático ponta-a-ponta</h2>
        <p className="muted small">
          Divide o período em folds, otimiza IS em cada fold via MT5 e roda o
          backtest OOS com os melhores parâmetros. Cada resultado OOS é salvo
          como run individual (abrível na aba Backtest Individual).
        </p>
        <InstallationPicker
          onSelection={({ installation: inst, expert: ea }) => {
            setInstallation(inst)
            setExpert(ea)
          }}
        />

        <div className="grid cols-2" style={{ marginTop: 14 }}>
          <div>
            <label>Símbolo</label>
            <input value={symbol} onChange={e => setSymbol(e.target.value)} placeholder="EURUSD" />
          </div>
          <div>
            <label>Timeframe</label>
            <select value={period} onChange={e => setPeriod(e.target.value)}>
              {PERIODS.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div>
            <label>Data início</label>
            <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} />
          </div>
          <div>
            <label>Data fim</label>
            <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} />
          </div>
        </div>

        <div className="grid cols-2" style={{ marginTop: 10 }}>
          <div>
            <label>Número de folds ({folds})</label>
            <input type="range" min={2} max={10} value={folds} onChange={e => setFolds(+e.target.value)} />
          </div>
          <div>
            <label>OOS % por fold ({oosPct}%)</label>
            <input type="range" min={10} max={40} step={5} value={oosPct} onChange={e => setOosPct(+e.target.value)} />
          </div>
          <div>
            <label>Score key (critério IS)</label>
            <select value={scoreKey} onChange={e => setScoreKey(e.target.value)}>
              {SCORE_KEYS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </div>
          <div>
            <label>Top-N passes IS → OOS ({topN})</label>
            <input type="range" min={1} max={5} value={topN} onChange={e => setTopN(+e.target.value)} />
          </div>
        </div>

        <div className="row" style={{ marginTop: 12, alignItems: 'center', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input type="checkbox" style={{ width: 'auto' }} id="anchored"
              checked={anchored} onChange={e => setAnchored(e.target.checked)} />
            <label htmlFor="anchored" style={{ margin: 0, cursor: 'pointer' }}>
              Anchored (IS sempre cresce a partir da origem)
            </label>
          </div>
          <button
            disabled={loading || !installation || !expert}
            onClick={handleStart}
            style={{ marginLeft: 'auto' }}
          >
            {loading ? 'Rodando…' : 'Iniciar WFA'}
          </button>
        </div>
        {error && <div className="errbox" style={{ marginTop: 10 }}>{error}</div>}
      </div>

      {job && (
        <>
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
              <h2 style={{ margin: 0 }}>Progresso</h2>
              <span style={{
                padding: '3px 10px', borderRadius: 12, fontSize: 12, fontWeight: 600,
                background: 'rgba(0,0,0,0.25)',
                color: statusColor(job.status),
                border: `1px solid ${statusColor(job.status)}`,
              }}>
                {job.status.toUpperCase()}
              </span>
            </div>
            {job.progress && (
              <p className="muted small" style={{ marginBottom: 10 }}>{job.progress}</p>
            )}
            {job.error && (
              <div className="errbox">{job.error}</div>
            )}

            {job.stability_score !== null && job.stability_score !== undefined && (
              <div className="grid cols-3" style={{ marginTop: 10 }}>
                <div className="kpi">
                  <div className="label">Stability Score</div>
                  <div className="value" style={{ color: stabilityColor(job.stability_score) }}>
                    {(job.stability_score * 100).toFixed(1)}%
                  </div>
                  <div className="small muted">OOS / IS médio</div>
                </div>
                <div className="kpi">
                  <div className="label">Consistency</div>
                  <div className="value" style={{ color: stabilityColor(job.consistency) }}>
                    {(job.consistency * 100).toFixed(0)}%
                  </div>
                  <div className="small muted">folds com OOS {'>'} 0</div>
                </div>
                <div className="kpi">
                  <div className="label">Degradation</div>
                  <div className="value" style={{ color: job.degradation < 0.3 ? '#3fb950' : job.degradation < 0.6 ? '#d29922' : '#f85149' }}>
                    {(job.degradation * 100).toFixed(1)}%
                  </div>
                  <div className="small muted">queda IS → OOS</div>
                </div>
              </div>
            )}
          </div>

          {job.is_results?.length > 0 && (
            <div className="card">
              <h2>Resultados por fold — IS vs OOS ({scoreKey})</h2>
              <table>
                <thead>
                  <tr>
                    <th>Fold</th>
                    <th>IS (média top-{topN})</th>
                    <th>OOS (média)</th>
                    <th>Comparativo</th>
                    <th>Passes OOS</th>
                  </tr>
                </thead>
                <tbody>
                  {job.is_results.map((isR, idx) => {
                    const oosR = job.oos_results?.[idx]
                    const oosVal = oosR?.mean ?? 0
                    const isVal = isR.mean ?? 0
                    return (
                      <tr key={idx}>
                        <td><b>#{isR.fold}</b></td>
                        <td>{isVal.toFixed(4)}</td>
                        <td style={{ color: oosVal >= isVal ? '#3fb950' : '#f85149' }}>
                          <b>{oosVal.toFixed(4)}</b>
                        </td>
                        <td style={{ minWidth: 220 }}>
                          <ScoreBar is_={isVal} oos={oosVal} max={maxIS} />
                        </td>
                        <td>
                          {oosR?.details?.map((d, di) => (
                            d.run_id ? (
                              <button
                                key={di}
                                className="small"
                                style={{ marginRight: 4, marginBottom: 2, padding: '2px 8px', fontSize: 11 }}
                                onClick={() => onOpenRun?.(d.run_id)}
                              >
                                pass #{d.pass_idx}
                              </button>
                            ) : (
                              <span key={di} className="small muted" style={{ marginRight: 4 }}>
                                #{d.pass_idx} (sem dados)
                              </span>
                            )
                          ))}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}
