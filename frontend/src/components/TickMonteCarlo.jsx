import { useEffect, useState } from 'react'
import { runTickMonteCarlo, fetchRunTicks, errorMessage } from '../services/api'

function StatusBanner({ overall, passes, total }) {
  const bg = overall === 'green' ? 'rgba(56,139,56,0.15)'
    : overall === 'yellow' ? 'rgba(210,153,34,0.15)' : 'rgba(248,81,73,0.15)'
  const border = overall === 'green' ? '#388b38'
    : overall === 'yellow' ? '#d29922' : '#f85149'
  const label = overall === 'green' ? 'ROBUSTO'
    : overall === 'yellow' ? 'ATENÇÃO' : 'FRÁGIL'
  const icon = overall === 'green' ? '🟢' : overall === 'yellow' ? '🟡' : '🔴'
  return (
    <div style={{ padding: '10px 14px', borderRadius: 8, background: bg,
                  border: `1px solid ${border}`, marginBottom: 14 }}>
      <b style={{ fontSize: 15 }}>
        {icon} {label} — {passes}/{total} testes contra ticks reais passaram
      </b>
    </div>
  )
}

function MethodCard({ title, data }) {
  if (!data || data.error) {
    return (
      <div className="card" style={{ margin: 0, background: 'rgba(248,81,73,0.07)' }}>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>{title}</div>
        <div className="muted small">{data?.error || 'sem dados'}</div>
      </div>
    )
  }
  const prob = (data.prob_profitable || 0) * 100
  const probColor = prob >= 90 ? '#3fb950' : prob >= 70 ? '#d29922' : '#f85149'
  return (
    <div className="card" style={{ margin: 0 }}>
      <div style={{ fontWeight: 600, marginBottom: 6 }}>{title}</div>
      <div className="grid cols-2" style={{ gap: 8, marginBottom: 8 }}>
        <div>
          <div className="muted small">Prob. lucro</div>
          <div style={{ fontSize: 18, fontWeight: 600, color: probColor }}>{prob.toFixed(1)}%</div>
        </div>
        <div>
          <div className="muted small">Net P50</div>
          <div style={{ fontSize: 18, fontWeight: 600 }}>{data.net_p50?.toFixed(2)}</div>
        </div>
        <div>
          <div className="muted small">Net P5 / P95</div>
          <div style={{ fontSize: 12 }}>{data.net_p5?.toFixed(2)} / {data.net_p95?.toFixed(2)}</div>
        </div>
        <div>
          <div className="muted small">DD P50 / P95</div>
          <div style={{ fontSize: 12 }}>{data.dd_p50?.toFixed(1)}% / {data.dd_p95?.toFixed(1)}%</div>
        </div>
      </div>
      <div className="muted small">
        Histórico: Net={data.original_net?.toFixed(2)} · DD={data.original_dd_pct?.toFixed(1)}%
      </div>
    </div>
  )
}

export function TickMonteCarlo({ runId, ticksPath }) {
  const [path, setPath] = useState(ticksPath || '')
  const [runs, setRuns] = useState(500)
  const [jitterSec, setJitterSec] = useState(30)
  const [worstTicks, setWorstTicks] = useState(3)
  const [blockTicks, setBlockTicks] = useState(100)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [fetching, setFetching] = useState(false)

  useEffect(() => {
    if (ticksPath) setPath(ticksPath)
  }, [ticksPath])

  const doAutoFetch = async () => {
    if (!runId) return
    setFetching(true); setError('')
    try {
      const r = await fetchRunTicks(runId)
      setPath(r.parquet_path)
    } catch (e) {
      setError(errorMessage(e))
    } finally { setFetching(false) }
  }

  const doRun = async () => {
    if (!runId) return
    setLoading(true); setError(''); setResult(null)
    try {
      const r = await runTickMonteCarlo(runId, {
        parquet_path: path || undefined,
        runs, jitter_seconds: jitterSec,
        worst_n_ticks: worstTicks, block_ticks: blockTicks,
      })
      setResult(r)
    } catch (e) {
      setError(errorMessage(e))
    } finally { setLoading(false) }
  }

  return (
    <div className="card">
      <h2>Monte Carlo com Ticks Reais</h2>
      <p className="muted small" style={{ marginBottom: 10 }}>
        Três testes usando o arquivo de ticks do ativo (mais realista que MC sintético):
        entry jitter (timing), spread slippage (execução), e block bootstrap de tick-returns
        (caminhos alternativos preservando autocorrelação).
      </p>

      {/* Auto-fetch strip */}
      <div style={{
        marginBottom: 12, padding: '10px 14px',
        background: path ? 'rgba(63,185,80,0.05)' : 'rgba(88,166,255,0.05)',
        border: `1px solid ${path ? 'rgba(63,185,80,0.25)' : '#1f2a37'}`,
        borderRadius: 6,
      }}>
        {path ? (
          <div className="small" style={{ color: '#3fb950' }}>
            ✓ Ticks disponíveis: <code style={{ color: '#8b98a5', fontSize: 11 }}>{path}</code>
            <button className="ghost" style={{ marginLeft: 12, fontSize: 11, padding: '2px 8px' }}
              onClick={() => setPath('')}>trocar</button>
          </div>
        ) : (
          <div>
            <div className="muted small" style={{ marginBottom: 8 }}>
              Baixar ticks do mesmo MT5 usado no backtest (símbolo e período já configurados):
            </div>
            <button disabled={fetching || !runId} style={{ fontSize: 12 }} onClick={doAutoFetch}>
              {fetching ? 'Baixando ticks…' : 'Buscar ticks do MT5'}
            </button>
          </div>
        )}
        {!path && (
          <div style={{ marginTop: 8 }}>
            <input value={path} onChange={e => setPath(e.target.value)}
              placeholder="ou informe caminho manual: C:/ticks/WIN/ticks.parquet"
              style={{ width: '100%', fontSize: 12 }} />
          </div>
        )}
      </div>

      <div className="row" style={{ marginTop: 8, gap: 8 }}>
        <div>
          <label>Runs</label>
          <input type="number" min="50" max="5000" value={runs} onChange={e => setRuns(+e.target.value)} />
        </div>
        <div>
          <label>Jitter (±segundos)</label>
          <input type="number" min="1" max="3600" value={jitterSec} onChange={e => setJitterSec(+e.target.value)} />
        </div>
        <div>
          <label>Worst-of-N ticks (slippage)</label>
          <input type="number" min="1" max="50" value={worstTicks} onChange={e => setWorstTicks(+e.target.value)} />
        </div>
        <div>
          <label>Block size (ticks)</label>
          <input type="number" min="10" max="5000" value={blockTicks} onChange={e => setBlockTicks(+e.target.value)} />
        </div>
        <div className="fit" style={{ display: 'flex', alignItems: 'flex-end' }}>
          <button disabled={loading || !runId} onClick={doRun}>
            {loading ? 'Processando (1-3min)…' : 'Rodar MC com ticks'}
          </button>
        </div>
      </div>
      {error && <div className="errbox" style={{ marginTop: 8 }}>{error}</div>}

      {result && (
        <div style={{ marginTop: 16 }}>
          <StatusBanner overall={result.overall} passes={result.passes} total={result.total} />
          <div className="grid cols-3" style={{ gap: 12, marginBottom: 16 }}>
            <MethodCard title="1. Entry Jitter (timing)" data={result.entry_jitter} />
            <MethodCard title="2. Spread Slippage (custos reais)" data={result.spread_slippage} />
            <MethodCard title="3. Tick-Return Bootstrap (paths)" data={result.tick_bootstrap} />
          </div>
          <table>
            <thead><tr><th>Teste</th><th>Status</th><th>Valor</th></tr></thead>
            <tbody>
              {result.scorecard.map((c, i) => (
                <tr key={i}>
                  <td><b>{c.name}</b><div className="muted small">{c.note}</div></td>
                  <td>
                    <span className={'pill ' + (c.status === 'pass' ? 'pos' : 'neg')}>
                      {c.status === 'pass' ? 'PASS' : 'FAIL'}
                    </span>
                  </td>
                  <td style={{ fontSize: 12 }}>
                    <code>{c.value}</code>
                    {c.suggestion && (
                      <div style={{ marginTop: 8, padding: '8px 10px', background: 'rgba(210,153,34,0.08)', border: '1px solid rgba(210,153,34,0.3)', borderRadius: 4, fontSize: 11, color: '#d6cda2' }}>
                        <b>💡 Como melhorar:</b> {c.suggestion}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
