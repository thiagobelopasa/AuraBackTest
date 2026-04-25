import { useState } from 'react'
import { runOptimization, errorMessage } from '../services/api'
import { InstallationPicker } from '../components/InstallationPicker'

export function OptimizationPage() {
  const [selection, setSelection] = useState(null)
  const [values, setValues] = useState({})
  const [ranges, setRanges] = useState({})  // {name: {start,step,stop,enabled}}
  const [symbol, setSymbol] = useState('')
  const [period, setPeriod] = useState('M1')
  // Defaults: último trimestre terminado
  const [fromDate, setFromDate] = useState('2025-01-01')
  const [toDate, setToDate] = useState('2025-03-31')
  const [criterion, setCriterion] = useState('balance')
  const [genetic, setGenetic] = useState(true)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  const handleSelection = (sel) => {
    setSelection(sel)
    const v = {}, rg = {}
    sel.inputs.forEach(i => {
      v[i.name] = i.default
      rg[i.name] = { start: '', step: '', stop: '', enabled: false }
    })
    setValues(v); setRanges(rg)
  }

  const toggleRange = (name) => {
    setRanges(r => ({ ...r, [name]: { ...r[name], enabled: !r[name].enabled } }))
  }

  const doRun = async () => {
    setError(''); setResult(null)
    if (new Date(fromDate) >= new Date(toDate)) {
      setError(`Datas inválidas: "De" (${fromDate}) precisa ser anterior a "Até" (${toDate})`)
      return
    }
    const rangeList = Object.entries(ranges)
      .filter(([, r]) => r.enabled && r.start !== '' && r.stop !== '' && r.step !== '')
      .map(([name, r]) => ({ name, start: +r.start, stop: +r.stop, step: +r.step }))
    if (!rangeList.length) {
      setError('Habilite ao menos 1 parâmetro com start/step/stop preenchidos')
      return
    }
    setLoading(true)
    try {
      const r = await runOptimization({
        terminal_exe: selection.installation.terminal_exe,
        data_folder: selection.installation.data_folder,
        ea_relative_path: selection.expert.relative_path,
        ea_inputs_defaults: values,
        ranges: rangeList,
        symbol, period,
        from_date: fromDate, to_date: toDate,
        criterion, genetic,
      })
      setResult(r)
    } catch (e) {
      setError(`Erro: ${errorMessage(e)}`)
    } finally { setLoading(false) }
  }

  const optimizableInputs = selection?.inputs?.filter(i => i.optimizable) || []

  return (
    <div>
      <div className="card">
        <h2>Otimização (MT5 nativo)</h2>
        <p className="muted small">
          MT5 usa grid exaustivo ou algoritmo genético paralelizando em todos os cores.
          Depois da otimização, use a aba <b>Triagem</b> para filtrar os robustos.
        </p>
        <InstallationPicker onSelection={handleSelection} />
      </div>

      {optimizableInputs.length > 0 && (
        <div className="card">
          <h2>Parâmetros a otimizar</h2>
          <table>
            <thead><tr>
              <th>opt</th><th>Nome</th><th>Default</th>
              <th>Start</th><th>Step</th><th>Stop</th>
            </tr></thead>
            <tbody>
              {optimizableInputs.map(i => (
                <tr key={i.name}>
                  <td style={{ width: 40 }}>
                    <input type="checkbox" style={{ width: 'auto' }}
                      checked={ranges[i.name]?.enabled || false}
                      onChange={() => toggleRange(i.name)} />
                  </td>
                  <td><code>{i.name}</code> <span className="muted small">({i.type})</span></td>
                  <td>
                    <input value={values[i.name] ?? ''}
                      onChange={e => setValues({ ...values, [i.name]: e.target.value })} />
                  </td>
                  <td><input value={ranges[i.name]?.start ?? ''}
                    onChange={e => setRanges({ ...ranges, [i.name]: { ...ranges[i.name], start: e.target.value } })} /></td>
                  <td><input value={ranges[i.name]?.step ?? ''}
                    onChange={e => setRanges({ ...ranges, [i.name]: { ...ranges[i.name], step: e.target.value } })} /></td>
                  <td><input value={ranges[i.name]?.stop ?? ''}
                    onChange={e => setRanges({ ...ranges, [i.name]: { ...ranges[i.name], stop: e.target.value } })} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="card">
        <h2>Mercado & Configuração</h2>
        <div className="row">
          <div><label>Símbolo</label><input value={symbol} onChange={e => setSymbol(e.target.value)} /></div>
          <div><label>TF</label>
            <select value={period} onChange={e => setPeriod(e.target.value)}>
              {['M1','M5','M15','M30','H1','H4','D1'].map(p => <option key={p}>{p}</option>)}
            </select>
          </div>
          <div><label>De</label><input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)} /></div>
          <div><label>Até</label><input type="date" value={toDate} onChange={e => setToDate(e.target.value)} /></div>
          <div><label>Critério</label>
            <select value={criterion} onChange={e => setCriterion(e.target.value)}>
              <option value="balance">Net Profit</option>
              <option value="profit_factor">Profit Factor</option>
              <option value="expected_payoff">Expected Payoff</option>
              <option value="drawdown_min">Drawdown mínimo</option>
              <option value="recovery_factor">Recovery Factor</option>
              <option value="sharpe_ratio">Sharpe</option>
              <option value="complex_criterion">Complexo (requer OnTester no EA)</option>
            </select>
          </div>
          <div><label>Modo</label>
            <select value={genetic ? '1' : '0'} onChange={e => setGenetic(e.target.value === '1')}>
              <option value="1">Genético (rápido)</option>
              <option value="0">Grid completo</option>
            </select>
          </div>
        </div>
        <div style={{ marginTop: 14 }}>
          <button disabled={!selection?.expert || !symbol || loading} onClick={doRun}>
            {loading ? 'Otimizando MT5...' : 'Rodar otimização'}
          </button>
        </div>
        {error && <div className="errbox">{error}</div>}
      </div>

      {result && (
        <div className="card">
          <h2>Resultado</h2>
          <div className="grid cols-3">
            <div className="kpi"><div className="label">Passes</div><div className="value">{result.num_passes}</div></div>
            <div className="kpi"><div className="label">Tempo (s)</div><div className="value">{result.elapsed_seconds.toFixed(0)}</div></div>
            <div className="kpi"><div className="label">Run ID</div><div className="value" style={{ fontSize: 13 }}>{result.run_id}</div></div>
          </div>

          {result.num_passes === 0 && (
            <div className="errbox" style={{ marginTop: 14 }}>
              <b>Nenhum pass executado.</b> Causas comuns:
              <ul style={{ margin: '6px 0 0 20px' }}>
                <li><b>Critério "Complexo"</b> exige que o EA tenha a função <code>OnTester()</code> no código MQL5 — se seu EA não implementa, use <b>Net Profit</b> ou outro critério</li>
                <li>Símbolo inexistente ou não disponível no MT5 selecionado (tente abrir o Market Watch no MT5 e verifique o nome exato, ex: <code>US100.cash</code> ≠ <code>US100.CASH</code>)</li>
                <li>Período sem dados históricos (baixe os ticks/barras no MT5 antes de rodar)</li>
                <li>Datas fora do intervalo disponível, ou EA com erro de compilação</li>
                <li>Ranges mal definidos (step maior que stop-start)</li>
              </ul>
              <div className="small" style={{ marginTop: 8 }}>
                Report XML: <code>{result.report_xml_path || 'não gerado'}</code>
              </div>
            </div>
          )}

          {result.num_passes > 0 && (
            <>
              <h3 style={{ color: 'var(--muted)', fontSize: 13, marginTop: 20 }}>Top 10</h3>
              <table>
                <thead><tr><th>#</th><th>Parâmetros</th><th>Score</th><th>Net</th><th>DD%</th><th>Trades</th></tr></thead>
                <tbody>
                  {result.top10.map((p, i) => (
                    <tr key={p.pass_idx}>
                      <td>{i + 1}</td>
                      <td className="small"><code>{JSON.stringify(p.parameters)}</code></td>
                      <td>{p.metrics.score?.toFixed(2) ?? p.metrics.custom_score?.toFixed(2) ?? '—'}</td>
                      <td>{p.metrics.net_profit?.toFixed(2) ?? '—'}</td>
                      <td>{p.metrics.equity_dd_pct?.toFixed(2) ?? '—'}</td>
                      <td>{p.metrics.total_trades ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          {(result.stdout_tail || result.stderr_tail) && (
            <details style={{ marginTop: 14 }}>
              <summary className="muted small" style={{ cursor: 'pointer' }}>Ver log do terminal MT5</summary>
              {result.stdout_tail && <pre className="log">{result.stdout_tail}</pre>}
              {result.stderr_tail && <pre className="log" style={{ color: '#f85149' }}>{result.stderr_tail}</pre>}
            </details>
          )}
        </div>
      )}
    </div>
  )
}
