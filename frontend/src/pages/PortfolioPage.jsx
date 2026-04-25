import { useEffect, useMemo, useState } from 'react'
import { api, listRuns, errorMessage } from '../services/api'
import { runLabelShort, runFingerprint } from '../services/runLabel'

export function PortfolioPage() {
  const [runs, setRuns] = useState([])
  const [selected, setSelected] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [maxDD, setMaxDD] = useState(20)
  const [optResult, setOptResult] = useState(null)
  const [optLoading, setOptLoading] = useState(false)

  useEffect(() => {
    listRuns({ limit: 200 }).then(setRuns).catch(() => {})
  }, [])

  const runIndex = useMemo(() => {
    const m = {}
    runs.forEach(r => { m[r.id] = r })
    return m
  }, [runs])

  const toggle = (id) => {
    setSelected(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id])
  }

  const aggregate = async () => {
    if (!selected.length) { setError('Selecione pelo menos 1 run'); return }
    setError(''); setLoading(true); setResult(null)
    try {
      const r = await api.post('/portfolio/aggregate', {
        run_ids: selected,
        initial_equity: 10000,
      })
      setResult(r.data)
    } catch (e) {
      setError(`Erro: ${errorMessage(e)}`)
    } finally { setLoading(false) }
  }

  const optimizeWeights = async () => {
    if (!selected.length) { setError('Selecione runs primeiro'); return }
    setError(''); setOptLoading(true); setOptResult(null)
    try {
      const r = await api.post('/portfolio/optimize-weights', {
        run_ids: selected,
        initial_equity: 10000,
        max_dd_pct: maxDD,
        n_samples: 4000,
      })
      setOptResult(r.data)
    } catch (e) {
      setError(`Erro: ${errorMessage(e)}`)
    } finally { setOptLoading(false) }
  }

  const corr = result?.correlation
  const suite = result?.suite

  return (
    <div>
      <div className="card">
        <h2>Portfólio — combinar backtests</h2>
        <p className="muted small">
          Selecione 2+ runs (backtests já importados) para combinar trades por timestamp,
          rodar análise agregada, suite de robustez e matriz de correlação entre as curvas.
        </p>
        <div style={{ maxHeight: 320, overflow: 'auto' }}>
          <table>
            <thead><tr>
              <th></th><th>Nome / robô</th><th>Ativo</th><th>TF</th>
              <th>Fingerprint</th><th>Tipo</th><th>Período</th><th>ID</th>
            </tr></thead>
            <tbody>
              {runs.map(r => (
                <tr key={r.id}>
                  <td style={{ width: 30 }}>
                    <input type="checkbox" style={{ width: 'auto' }}
                      checked={selected.includes(r.id)}
                      onChange={() => toggle(r.id)} />
                  </td>
                  <td>{r.label?.trim() || <span className="muted small">—</span>}</td>
                  <td><b>{r.symbol || '—'}</b></td>
                  <td><b>{r.timeframe || '—'}</b></td>
                  <td className="small muted">{r.params_hash ? <code>#{r.params_hash}</code> : '—'}</td>
                  <td>{r.kind}</td>
                  <td className="small muted">{r.from_date} → {r.to_date}</td>
                  <td className="small muted"><code>{r.id}</code></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ marginTop: 12 }}>
          <button disabled={!selected.length || loading} onClick={aggregate}>
            {loading ? 'Agregando...' : `Analisar portfólio (${selected.length})`}
          </button>
        </div>
        {error && <div className="errbox" style={{ marginTop: 10 }}>{error}</div>}
      </div>

      {selected.length >= 2 && (
        <div className="card">
          <h2>Otimização de pesos (respeitando DD máximo)</h2>
          <p className="muted small">
            Busca combinação de pesos (somam 1) que maximiza o Net Profit mantendo
            o Max DD ≤ alvo. Ex: se um robô tem lucro alto mas DD grande, peso 0.5
            pode somar profit sem estourar o DD do portfólio.
          </p>
          <div className="row">
            <div>
              <label>Max DD % do portfólio ({maxDD}%)</label>
              <input type="range" min="1" max="50" step="0.5"
                value={maxDD} onChange={e => setMaxDD(+e.target.value)} />
            </div>
            <div className="fit" style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button disabled={optLoading} onClick={optimizeWeights}>
                {optLoading ? 'Otimizando...' : 'Achar pesos ideais'}
              </button>
            </div>
          </div>

          {optResult && (
            <div style={{ marginTop: 14 }}>
              {!optResult.best.feasible && (
                <div className="errbox" style={{ marginBottom: 10 }}>
                  Nenhum peso respeita DD ≤ {maxDD}%. Mostrando o de menor DD encontrado ({optResult.best.max_dd_pct.toFixed(2)}%).
                </div>
              )}
              <div className="grid cols-4">
                <div className="kpi">
                  <div className="label">Baseline (pesos iguais)</div>
                  <div className="value">{optResult.baseline_equal.net_profit.toFixed(2)}</div>
                  <div className="small muted">DD {optResult.baseline_equal.max_dd_pct.toFixed(2)}%</div>
                </div>
                <div className="kpi" style={{ borderLeft: '4px solid #3fb950' }}>
                  <div className="label">Otimizado</div>
                  <div className="value pos">{optResult.best.net_profit.toFixed(2)}</div>
                  <div className="small muted">DD {optResult.best.max_dd_pct.toFixed(2)}%</div>
                </div>
                <div className="kpi">
                  <div className="label">Ganho vs baseline</div>
                  <div className="value" style={{ color: optResult.best.net_profit > optResult.baseline_equal.net_profit ? '#3fb950' : '#f85149' }}>
                    {((optResult.best.net_profit - optResult.baseline_equal.net_profit) / Math.abs(optResult.baseline_equal.net_profit || 1) * 100).toFixed(1)}%
                  </div>
                </div>
                <div className="kpi">
                  <div className="label">Amostras testadas</div>
                  <div className="value">{optResult.n_samples}</div>
                </div>
              </div>

              <h3 style={{ color: 'var(--muted)', fontSize: 13, marginTop: 16 }}>
                Pesos ótimos
              </h3>
              <table>
                <thead><tr>
                  <th>Robô</th><th>Fingerprint</th><th>Peso</th><th>Distribuição</th>
                </tr></thead>
                <tbody>
                  {optResult.run_ids.map(rid => {
                    const w = optResult.best.weights[rid]
                    const run = runIndex[rid]
                    return (
                      <tr key={rid}>
                        <td>{run ? runLabelShort(run) : <code>{rid}</code>}</td>
                        <td className="small muted">{run ? runFingerprint(run) : ''}</td>
                        <td><b>{(w * 100).toFixed(1)}%</b></td>
                        <td style={{ width: '55%' }}>
                          <div style={{ background: '#30363d', borderRadius: 3, height: 14 }}>
                            <div style={{
                              background: '#3fb950', height: '100%',
                              width: `${w * 100}%`, borderRadius: 3,
                            }} />
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {result && (
        <>
          <div className="card">
            <h2>Visão geral do portfólio</h2>
            <div className="grid cols-4">
              <div className="kpi"><div className="label">Runs</div><div className="value">{result.run_count}</div></div>
              <div className="kpi"><div className="label">Trades totais</div><div className="value">{result.total_trades}</div></div>
              <div className="kpi"><div className="label">Net Profit</div><div className="value" style={{ color: result.analysis.net_profit >= 0 ? '#3fb950' : '#f85149' }}>{result.analysis.net_profit?.toFixed(2)}</div></div>
              <div className="kpi"><div className="label">Max DD %</div><div className="value">{result.analysis.max_drawdown_pct?.toFixed(2)}%</div></div>
              <div className="kpi"><div className="label">Sharpe</div><div className="value">{result.analysis.sharpe_ratio?.toFixed(3)}</div></div>
              <div className="kpi"><div className="label">Profit Factor</div><div className="value">{result.analysis.profit_factor?.toFixed(2)}</div></div>
              <div className="kpi"><div className="label">Win Rate</div><div className="value">{(result.analysis.win_rate * 100)?.toFixed(1)}%</div></div>
              <div className="kpi"><div className="label">Total Trades</div><div className="value">{result.analysis.total}</div></div>
            </div>
          </div>

          <div className="card">
            <h2>Contribuição por run</h2>
            <table>
              <thead><tr>
                <th>Robô</th><th>Ativo</th><th>TF</th><th>Fingerprint</th>
                <th>Trades</th><th>Net Profit</th>
              </tr></thead>
              <tbody>
                {result.per_run.map(r => {
                  const run = runIndex[r.run_id]
                  return (
                    <tr key={r.run_id}>
                      <td>{run?.label?.trim() || <code className="small muted">{r.run_id}</code>}</td>
                      <td><b>{r.symbol || run?.symbol || '—'}</b></td>
                      <td><b>{run?.timeframe || '—'}</b></td>
                      <td className="small muted">{run?.params_hash ? <code>#{run.params_hash}</code> : '—'}</td>
                      <td>{r.trades}</td>
                      <td style={{ color: r.net_profit >= 0 ? '#3fb950' : '#f85149' }}>
                        {r.net_profit.toFixed(2)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {corr && corr.run_ids.length > 1 && (
            <div className="card">
              <h2>Matriz de correlação (retornos diários)</h2>
              <p className="muted small">
                Correlação baixa entre runs = diversificação real. Correlação alta
                (&gt; 0.7) = runs fazem essencialmente a mesma coisa.
              </p>
              <table>
                <thead>
                  <tr>
                    <th></th>
                    {corr.run_ids.map(id => <th key={id} style={{ fontSize: 10 }}><code>{id}</code></th>)}
                  </tr>
                </thead>
                <tbody>
                  {corr.matrix.map((row, i) => (
                    <tr key={corr.run_ids[i]}>
                      <td style={{ fontSize: 10 }}><code>{corr.run_ids[i]}</code></td>
                      {row.map((v, j) => {
                        const absv = Math.abs(v)
                        const bg = v >= 0
                          ? `rgba(63, 185, 80, ${absv * 0.6})`
                          : `rgba(248, 81, 73, ${absv * 0.6})`
                        return <td key={j} style={{ background: bg, textAlign: 'center' }}>{v.toFixed(2)}</td>
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {suite && (
            <div className="card">
              <h2>Scorecard de robustez (portfólio agregado)</h2>
              <div className={`scorecard-banner ${suite.overall}`}
                style={{
                  padding: 12, borderRadius: 8, marginBottom: 14,
                  background: suite.overall === 'green' ? 'rgba(56,139,56,0.15)'
                    : suite.overall === 'yellow' ? 'rgba(210,153,34,0.15)'
                    : 'rgba(210,54,54,0.15)',
                  border: '1px solid ' + (suite.overall === 'green' ? '#388b38'
                    : suite.overall === 'yellow' ? '#d29922' : '#d23636'),
                }}>
                <b style={{ fontSize: 16 }}>
                  {suite.overall === 'green' ? '🟢 ROBUSTO' : suite.overall === 'yellow' ? '🟡 ATENÇÃO' : '🔴 FRÁGIL'}
                  &nbsp;— {suite.passes}/{suite.total} checks
                </b>
              </div>
              <table>
                <thead><tr><th>Teste</th><th>Status</th><th>Valor</th></tr></thead>
                <tbody>
                  {suite.scorecard?.map((c, i) => (
                    <tr key={i}>
                      <td>{c.name}</td>
                      <td><span className={'pill ' + (c.status === 'pass' ? 'pos' : 'neg')}>
                        {c.status === 'pass' ? 'PASS' : 'FAIL'}
                      </span></td>
                      <td><code>{c.value}</code></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}
