import { useState } from 'react'
import { runSingle, parseReport, ingestReport, errorMessage } from '../services/api'
import { InstallationPicker } from '../components/InstallationPicker'

export function BacktestPage({ onRunSaved }) {
  const [selection, setSelection] = useState(null)
  const [values, setValues] = useState({})
  const [symbol, setSymbol] = useState('')
  const [period, setPeriod] = useState('M1')
  const [fromDate, setFromDate] = useState('2024-01-01')
  const [toDate, setToDate] = useState('2024-01-31')
  const [deposit, setDeposit] = useState(10000)
  const [label, setLabel] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [runResult, setRunResult] = useState(null)

  const handleSelection = (sel) => {
    setSelection(sel)
    const v = {}
    sel.inputs.forEach(i => { v[i.name] = i.default })
    setValues(v)
  }

  const doRun = async () => {
    setError(''); setLoading(true); setRunResult(null)
    try {
      const res = await runSingle({
        terminal_exe: selection.installation.terminal_exe,
        data_folder: selection.installation.data_folder,
        ea_relative_path: selection.expert.relative_path,
        ea_inputs_defaults: values,
        ranges: [],
        symbol, period,
        from_date: fromDate, to_date: toDate,
        deposit,
      })
      setRunResult(res)
      if (res.report_path) {
        await parseReport(res.report_path)
        const ingest = await ingestReport({
          run_id: res.run_id,
          report_path: res.report_path,
          ea_path: selection.expert.relative_path,
          symbol, timeframe: period,
          from_date: fromDate, to_date: toDate,
          deposit, parameters: values,
          label,
        })
        if (onRunSaved) onRunSaved(ingest.run_id)
      }
    } catch (e) {
      setError(`Erro no backtest: ${errorMessage(e)}`)
    } finally { setLoading(false) }
  }

  const ready = selection?.installation && selection?.expert && symbol

  return (
    <div>
      <div className="card">
        <h2>1. Escolher MT5 e Robô</h2>
        <InstallationPicker onSelection={handleSelection} />
      </div>

      {selection?.inputs?.length > 0 && (
        <div className="card">
          <h2>2. Parâmetros do EA</h2>
          <div style={{ maxHeight: 320, overflow: 'auto' }}>
            <table>
              <thead>
                <tr><th>Nome</th><th>Tipo</th><th>Default</th><th>Valor</th><th>Comentário</th></tr>
              </thead>
              <tbody>
                {selection.inputs.map(i => (
                  <tr key={i.name}>
                    <td><code>{i.name}</code></td>
                    <td className="muted">{i.type}</td>
                    <td className="muted">{String(i.default)}</td>
                    <td>
                      <input
                        value={values[i.name] ?? ''}
                        onChange={e => setValues({ ...values, [i.name]: e.target.value })}
                      />
                    </td>
                    <td className="muted small">{i.comment}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="card">
        <h2>3. Mercado & Período</h2>
        <div className="row">
          <div><label>Símbolo</label><input value={symbol} onChange={e => setSymbol(e.target.value)} placeholder="US100.cash" /></div>
          <div><label>Timeframe</label>
            <select value={period} onChange={e => setPeriod(e.target.value)}>
              {['M1','M5','M15','M30','H1','H4','D1'].map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div><label>De</label><input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)} /></div>
          <div><label>Até</label><input type="date" value={toDate} onChange={e => setToDate(e.target.value)} /></div>
          <div><label>Depósito</label><input type="number" value={deposit} onChange={e => setDeposit(+e.target.value)} /></div>
        </div>
      </div>

      <div className="card">
        <h2>4. Identificação e Execução</h2>
        <div className="row" style={{ marginBottom: 12 }}>
          <div style={{ flex: 3 }}>
            <label>Nome do robô / versão <span className="muted">(para comparar no histórico)</span></label>
            <input value={label} onChange={e => setLabel(e.target.value)}
              placeholder="Ex: Big-Small v2 — agressivo" />
          </div>
        </div>
        <button disabled={!ready || loading} onClick={doRun}>
          {loading ? 'Rodando MT5...' : 'Rodar backtest'}
        </button>
        {error && <div className="errbox">{error}</div>}
      </div>

      {runResult && (
        <div className="card">
          <h2>Resultado</h2>
          <div className="grid cols-3">
            <div className="kpi"><div className="label">Run ID</div><div className="value" style={{ fontSize: 14 }}>{runResult.run_id}</div></div>
            <div className="kpi"><div className="label">Return Code</div><div className="value">{runResult.return_code}</div></div>
            <div className="kpi"><div className="label">Tempo</div><div className="value">{runResult.elapsed_seconds.toFixed(1)}s</div></div>
          </div>
          <p className="small muted" style={{ marginTop: 10 }}>
            Report: <code>{runResult.report_path || 'não encontrado'}</code>
          </p>
          {runResult.report_path && (
            <p className="small"><span className="pill pos">Ingesta concluída</span> Abra a aba <b>Backtest Individual</b> para análise completa.</p>
          )}
          {runResult.stdout_tail && <pre className="log">{runResult.stdout_tail}</pre>}
        </div>
      )}
    </div>
  )
}
