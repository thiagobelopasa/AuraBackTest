import { useEffect, useMemo, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import { api, listRuns, errorMessage, runPBO } from '../services/api'
import { runLabelShort, runFingerprint } from '../services/runLabel'
import { CorrelationHeatmap } from '../components/CorrelationHeatmap'

export function PortfolioPage() {
  const [runs, setRuns] = useState([])
  const [selected, setSelected] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [maxDD, setMaxDD] = useState(20)
  const [optResult, setOptResult] = useState(null)
  const [optLoading, setOptLoading] = useState(false)
  const [pboResult, setPboResult] = useState(null)
  const [pboLoading, setPboLoading] = useState(false)
  const [pboError, setPboError] = useState('')

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
    setResult(null)
    setPboResult(null)
  }

  const aggregate = async () => {
    if (!selected.length) { setError('Selecione pelo menos 1 run'); return }
    setError(''); setLoading(true); setResult(null); setPboResult(null)
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

  const calcPBO = async () => {
    if (selected.length < 2) { setPboError('PBO requer 2+ runs selecionados'); return }
    setPboError(''); setPboLoading(true); setPboResult(null)
    try {
      const r = await runPBO(selected)
      setPboResult(r)
    } catch (e) {
      setPboError(errorMessage(e))
    } finally { setPboLoading(false) }
  }

  const corr = result?.correlation
  const suite = result?.suite

  const pboColor = (v) => {
    if (v === undefined || v === null) return '#8b949e'
    if (v < 0.25) return '#3fb950'
    if (v < 0.5) return '#d29922'
    return '#f85149'
  }

  const corrColor = (v) => {
    if (v === undefined || v === null) return '#8b949e'
    if (v < 0.3) return '#3fb950'
    if (v < 0.6) return '#d29922'
    return '#f85149'
  }

  // Histograma de logits para o PBO
  const logitHistData = useMemo(() => {
    if (!pboResult?.logits?.length) return []
    const bins = 20
    const vals = pboResult.logits
    const min = Math.min(...vals)
    const max = Math.max(...vals)
    const range = max - min || 1
    const counts = Array(bins).fill(0)
    vals.forEach(v => {
      const idx = Math.min(bins - 1, Math.floor(((v - min) / range) * bins))
      counts[idx]++
    })
    return counts.map((count, i) => ({
      x: (min + (i / bins) * range).toFixed(1),
      count,
      fill: (min + (i / bins) * range) < 0 ? '#3fb950' : '#f85149',
    }))
  }, [pboResult])

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
        <div style={{ marginTop: 12, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <button disabled={!selected.length || loading} onClick={aggregate}>
            {loading ? 'Agregando...' : `Analisar portfólio (${selected.length})`}
          </button>
          {selected.length >= 2 && (
            <button
              disabled={pboLoading}
              onClick={calcPBO}
              style={{ background: 'transparent', border: '1px solid #30363d', color: '#e6edf3' }}
            >
              {pboLoading ? 'Calculando PBO...' : 'Calcular PBO (CSCV)'}
            </button>
          )}
        </div>
        {error && <div className="errbox" style={{ marginTop: 10 }}>{error}</div>}
      </div>

      {/* PBO */}
      {(pboResult || pboError) && (
        <div className="card">
          <h2>PBO — Probability of Backtest Overfitting (CSCV)</h2>
          {pboError && <div className="errbox">{pboError}</div>}
          {pboResult && (
            <>
              <div style={{
                display: 'inline-flex', alignItems: 'center', gap: 12,
                padding: '10px 18px', borderRadius: 10, marginBottom: 16,
                background: 'rgba(0,0,0,0.2)',
                border: `1px solid ${pboColor(pboResult.pbo)}`,
              }}>
                <span style={{ fontSize: 28, fontWeight: 700, color: pboColor(pboResult.pbo) }}>
                  {(pboResult.pbo * 100).toFixed(1)}%
                </span>
                <span style={{ fontSize: 13, color: '#8b949e', maxWidth: 280 }}>
                  {pboResult.interpretation}
                </span>
              </div>

              <div className="grid cols-3" style={{ marginBottom: 16 }}>
                <div className="kpi">
                  <div className="label">Combinações CSCV</div>
                  <div className="value">{pboResult.n_combinations.toLocaleString()}</div>
                  <div className="small muted">C(16,8) partições</div>
                </div>
                <div className="kpi">
                  <div className="label">OOS rank médio</div>
                  <div className="value" style={{ color: pboResult.mean_oos_rank > 0.5 ? '#3fb950' : '#f85149' }}>
                    {(pboResult.mean_oos_rank * 100).toFixed(1)}%
                  </div>
                  <div className="small muted">{'>'} 50% = bom</div>
                </div>
                <div className="kpi">
                  <div className="label">Performance degradation</div>
                  <div className="value" style={{ color: pboResult.performance_degradation > 0 ? '#3fb950' : '#f85149' }}>
                    {pboResult.performance_degradation.toFixed(3)}
                  </div>
                  <div className="small muted">slope IS→OOS (≥0 = bom)</div>
                </div>
              </div>

              {logitHistData.length > 0 && (
                <>
                  <p className="muted small" style={{ marginBottom: 6 }}>
                    Distribuição de logits: valores negativos (verde) = vencedor IS mantém rank em OOS. Positivos (vermelho) = overfit.
                  </p>
                  <ResponsiveContainer width="100%" height={130}>
                    <BarChart data={logitHistData} barCategoryGap={2}>
                      <XAxis dataKey="x" tick={{ fontSize: 10, fill: '#8b949e' }} />
                      <YAxis hide />
                      <Tooltip formatter={(v) => [v, 'combinações']} labelFormatter={l => `logit ≈ ${l}`} />
                      <ReferenceLine x="0.0" stroke="#8b949e" strokeDasharray="3 3" />
                      <Bar dataKey="count" fill="#3fb950" isAnimationActive={false}
                        shape={(props) => {
                          const { x, y, width, height, index } = props
                          const fill = logitHistData[index]?.fill || '#3fb950'
                          return <rect x={x} y={y} width={width} height={height} fill={fill} rx={2} />
                        }}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </>
              )}

              {pboResult.missing_runs?.length > 0 && (
                <p className="small muted" style={{ marginTop: 8 }}>
                  Runs ignorados (sem análise salva): {pboResult.missing_runs.join(', ')}
                </p>
              )}
            </>
          )}
        </div>
      )}

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

              <h3 style={{ color: 'var(--muted)', fontSize: 13, marginTop: 16 }}>Pesos ótimos</h3>
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
              <h2>Diversificação — correlação entre curvas de equity</h2>
              <p className="muted small">
                Correlação baixa = diversificação real. Correlação alta (&gt; 0.7) = robôs fazem essencialmente a mesma coisa.
              </p>

              <div className="grid cols-3" style={{ marginBottom: 16 }}>
                <div className="kpi">
                  <div className="label">Correlação média</div>
                  <div className="value" style={{ color: corrColor(corr.avg_correlation) }}>
                    {corr.avg_correlation?.toFixed(3) ?? '—'}
                  </div>
                  <div className="small muted">{'<'} 0.3 = bem diversificado</div>
                </div>
                <div className="kpi">
                  <div className="label">Índice de diversificação</div>
                  <div className="value" style={{ color: corrColor(1 - (corr.diversification_ratio ?? 0)) }}>
                    {((corr.diversification_ratio ?? 0) * 100).toFixed(1)}%
                  </div>
                  <div className="small muted">100% = totalmente descorrelacionado</div>
                </div>
                <div className="kpi">
                  <div className="label">Par mais correlacionado</div>
                  <div className="value small" style={{ color: corrColor(corr.max_correlation), fontSize: 14 }}>
                    {corr.max_correlation?.toFixed(3) ?? '—'}
                  </div>
                  <div className="small muted">
                    {corr.most_correlated_pair?.join(' × ') ?? '—'}
                  </div>
                </div>
              </div>

              {corr.most_correlated_pair && corr.max_correlation > 0.6 && (
                <div style={{
                  padding: '8px 14px', marginBottom: 14, borderRadius: 6,
                  background: 'rgba(210,153,34,0.1)', border: '1px solid rgba(210,153,34,0.3)',
                  color: '#d29922', fontSize: 13,
                }}>
                  ⚠️ <b>{corr.most_correlated_pair[0]}</b> e <b>{corr.most_correlated_pair[1]}</b> têm
                  correlação de <b>{corr.max_correlation.toFixed(2)}</b> — considere reduzir o peso de um deles.
                </div>
              )}

              <CorrelationHeatmap
                matrix={corr.matrix}
                labels={corr.labels || corr.run_ids}
                runIds={corr.run_ids}
              />
            </div>
          )}

          {suite && (
            <div className="card">
              <h2>Scorecard de robustez (portfólio agregado)</h2>
              <div style={{
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
