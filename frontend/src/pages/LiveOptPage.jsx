import { useEffect, useMemo, useRef, useState } from 'react'
import {
  startLiveOpt, stopLiveOpt, clearLiveOpt, clearLiveOptFiles, liveOptSnapshot, openLiveOptStream,
  instrumentEA, openTopAsRuns, sessionToTriage, evalCustomFormula, errorMessage,
} from '../services/api'
import { downloadCSV } from '../services/csv'
import { InstallationPicker } from '../components/InstallationPicker'
import { useToast } from '../components/Toast'
import { ContextualTooltip } from '../components/ContextualTooltip'

// Aura Score = combinação ponderada dos principais critérios de risco ajustado.
// Fórmula: 40% Sortino + 30% Calmar + 20% (PF-1) + 10% SQN
// Favorece estratégias que pontuam bem em TODOS os eixos simultaneamente.
function computeAuraScore(metrics) {
  const { sortino_ratio = 0, calmar_ratio = 0, profit_factor = 1, sqn = 0 } = metrics
  return sortino_ratio * 0.40 + calmar_ratio * 0.30 + (profit_factor - 1) * 0.20 + sqn * 0.10
}

const SORT_OPTIONS = [
  { value: 'aura_score', label: '★ Aura Score (combinado)' },
  { value: 'sortino_ratio', label: 'Sortino' },
  { value: 'sharpe_ratio', label: 'Sharpe' },
  { value: 'calmar_ratio', label: 'Calmar' },
  { value: 'net_profit', label: 'Net Profit' },
  { value: 'profit_factor', label: 'Profit Factor' },
  { value: 'recovery_factor', label: 'Recovery Factor' },
  { value: 'sqn', label: 'SQN' },
  { value: 'k_ratio', label: 'K-Ratio' },
  { value: 'expectancy', label: 'Expectancy' },
  { value: 'max_drawdown_pct', label: 'Max DD % (menor=melhor)' },
  { value: 'complex_criterion', label: 'Critério MT5 (nativo)' },
]

const TIMEFRAMES = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1', 'W1', 'MN1']

export function LiveOptPage({ onOpenRun }) {
  const { toast } = useToast()
  // Fluxo "Preparar robô"
  const [selection, setSelection] = useState(null)
  const [preparing, setPreparing] = useState(false)
  const [prepared, setPrepared] = useState(null)

  // Metadata da session
  const [timeframe, setTimeframe] = useState('M1')
  const [label, setLabel] = useState('')

  // Estado da coleta
  const [sessionId, setSessionId] = useState(null)
  const [running, setRunning] = useState(false)
  const [watchDir, setWatchDir] = useState('')
  const [passes, setPasses] = useState([])
  const [sortKey, setSortKey] = useState('sortino_ratio')
  const [topN, setTopN] = useState(10)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)

  // Resultado de "Abrir top N"
  const [openedRuns, setOpenedRuns] = useState(null)
  const [triageResult, setTriageResult] = useState(null)

  // Métrica customizada
  const [customFormula, setCustomFormula] = useState('')
  const [formulaPreview, setFormulaPreview] = useState(null)

  const robotName = useMemo(() => {
    if (!selection?.expert) return ''
    // Ex: "RPAlgo/Big-Small" ou "MeuEA"; fica o nome curto pra label
    return selection.expert.relative_path || selection.expert.name || ''
  }, [selection])

  useEffect(() => {
    let cancelled = false
    liveOptSnapshot().then(s => {
      if (cancelled) return
      setRunning(s.running); setWatchDir(s.watch_dir); setPasses(s.passes || [])
      if (s.session_id) setSessionId(s.session_id)
    }).catch(() => {})

    const ws = openLiveOptStream()
    wsRef.current = ws
    ws.onopen = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onerror = () => setConnected(false)
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data)
        if (msg.event === 'snapshot') {
          setRunning(msg.data.running); setWatchDir(msg.data.watch_dir)
          setPasses(msg.data.passes || [])
        } else if (msg.event === 'pass') {
          setPasses(prev => {
            const next = [...prev, msg.data]
            // Toast a cada 10 passes recebidos (evita spam)
            if (next.length > 0 && next.length % 10 === 0) {
              const cm = msg.data.computed_metrics || {}
              const aura = computeAuraScore(cm).toFixed(2)
              toast.info(`${next.length} passes coletados`,
                `Último: ${msg.data.num_trades} trades · Aura ${aura} · Sortino ${cm.sortino_ratio?.toFixed(2) || '—'}`)
            }
            return next
          })
        }
      } catch (e) { console.error(e) }
    }
    return () => { cancelled = true; try { ws.close() } catch (_) {} }
  }, [])

  const prepareRobot = async () => {
    if (!selection?.expert?.has_source) {
      toast.error('Sem código-fonte', 'Selecione um EA com .mq5 disponível.')
      return
    }
    setPreparing(true); setError(''); setPrepared(null)
    try {
      const r = await instrumentEA({
        ea_path: selection.expert.absolute_path,
        terminal_exe: selection.installation.terminal_exe,
        compile_after: true,
      })
      setPrepared(r)
      if (r.compiled) {
        toast.gold('Robô pronto',
          `Use "${r.output_name}" no Strategy Tester. ${r.inputs_captured.length} parâmetros capturados.`)
      } else {
        toast.error('Compilação falhou', 'Veja o log de compilação abaixo.')
      }
    } catch (e) {
      toast.error('Falha ao preparar', errorMessage(e))
    } finally { setPreparing(false) }
  }

  const start = async () => {
    setError(''); setLoading(true); setOpenedRuns(null); setTriageResult(null)
    try {
      const r = await startLiveOpt({
        robot_name: robotName,
        timeframe,
        label: label || null,
      })
      setSessionId(r.session_id); setRunning(r.running); setWatchDir(r.watch_dir)
      setPasses([])
      toast.success('Coleta iniciada',
        `Rode a otimização no MT5. Session: ${r.session_id.slice(0,8)}…`)
    } catch (e) { toast.error('Falha ao iniciar', errorMessage(e)) }
    finally { setLoading(false) }
  }
  const stop = async () => {
    setLoading(true)
    try {
      const r = await stopLiveOpt()
      setRunning(r.running)
      toast.info('Coleta parada', `${passes.length} passes salvos. Veja no Histórico.`)
    }
    catch (e) { toast.error('Falha ao parar', errorMessage(e)) }
    finally { setLoading(false) }
  }
  const clear = async () => {
    try { await clearLiveOpt(); setPasses([]) }
    catch (e) { toast.error('Falha', errorMessage(e)) }
  }
  const clearFiles = async () => {
    try {
      const r = await clearLiveOptFiles()
      setPasses([])
      toast.success('Limpo', `${r.cleared_files} arquivos processados removidos do diretório`)
    }
    catch (e) { toast.error('Falha ao limpar arquivos', errorMessage(e)) }
  }

  const exportCSV = () => {
    const rows = passes.map(p => ({
      pass_id: p.pass_id,
      num_trades: p.num_trades,
      ...(p.parameters || {}),
      sortino: p.computed_metrics?.sortino_ratio,
      sharpe: p.computed_metrics?.sharpe_ratio,
      calmar: p.computed_metrics?.calmar_ratio,
      net_profit: p.computed_metrics?.net_profit,
      profit_factor: p.computed_metrics?.profit_factor,
      max_dd_pct: p.computed_metrics?.max_drawdown_pct,
      sqn: p.computed_metrics?.sqn,
      win_rate: p.computed_metrics?.win_rate,
    }))
    if (!rows.length) { toast.error('Sem passes pra exportar'); return }
    const fname = `${robotName || 'aura'}_${timeframe}_${sessionId?.slice(0,8) || 'live'}.csv`
    downloadCSV(rows, fname)
    toast.success('CSV exportado', `${rows.length} passes — ${fname}`)
  }

  const sorted = useMemo(() => {
    const arr = passes.map(p => ({
      ...p,
      _aura_score: computeAuraScore({ ...p.native_metrics, ...p.computed_metrics }),
    }))
    const desc = sortKey !== 'max_drawdown_pct'
    arr.sort((a, b) => {
      let va, vb
      if (sortKey === 'aura_score') {
        va = a._aura_score ?? -Infinity
        vb = b._aura_score ?? -Infinity
      } else {
        va = a.computed_metrics?.[sortKey] ?? a.native_metrics?.[sortKey] ?? -Infinity
        vb = b.computed_metrics?.[sortKey] ?? b.native_metrics?.[sortKey] ?? -Infinity
      }
      return desc ? vb - va : va - vb
    })
    return arr
  }, [passes, sortKey])

  const paramKeys = useMemo(() => {
    const s = new Set()
    for (const p of passes) Object.keys(p.parameters || {}).forEach(k => s.add(k))
    return Array.from(s)
  }, [passes])

  const openTop = async () => {
    if (!sessionId) { toast.error('Sem session ativa', 'Inicie a coleta primeiro.'); return }
    setLoading(true); setError(''); setOpenedRuns(null); setTriageResult(null)
    try {
      const payload = {
        sort_key: sortKey,
        top_n: topN,
        ascending: sortKey === 'max_drawdown_pct',
      }
      if (customFormula.trim()) {
        payload.custom_formula = customFormula.trim()
      }
      const r = await openTopAsRuns(sessionId, payload)
      setOpenedRuns(r)
      toast.gold(`${r.length} runs criados`,
        customFormula.trim()
          ? `Ranqueados pela fórmula: ${customFormula.trim()}`
          : 'Clique "Abrir" pra análise individual com MC, MAE/MFE, stat validation.')
    } catch (e) { toast.error('Falha', errorMessage(e)) }
    finally { setLoading(false) }
  }

  const previewFormula = async () => {
    if (!sessionId || !customFormula.trim()) return
    setLoading(true)
    try {
      const r = await evalCustomFormula(sessionId, customFormula.trim())
      setFormulaPreview(r)
      toast.info('Fórmula válida',
        `${r.evaluated}/${r.total_passes} passes avaliados · top: ${r.top[0]?.score?.toFixed(3) || '—'}`)
    } catch (e) {
      setFormulaPreview(null)
      toast.error('Fórmula inválida', errorMessage(e))
    } finally { setLoading(false) }
  }

  const sendToTriage = async () => {
    if (!sessionId) { toast.error('Sem session ativa', 'Inicie a coleta primeiro.'); return }
    setLoading(true); setError(''); setOpenedRuns(null); setTriageResult(null)
    try {
      const r = await sessionToTriage(sessionId, sortKey)
      setTriageResult(r)
      toast.info(`Triagem: ${r.num_passes} passes`,
        `Top robust score: ${r.passes[0]?.robust_score?.toFixed(2) || '—'}`)
    } catch (e) { toast.error('Falha na triagem', errorMessage(e)) }
    finally { setLoading(false) }
  }

  return (
    <div>
      <div className="card">
        <h2>1. Preparar robô (auto-instrumentação)</h2>
        <p className="muted small">
          Selecione o MT5 e o EA. O AuraBackTest gera uma cópia instrumentada
          (<code>&lt;nome&gt;_Aura</code>) e compila automaticamente.
          <b> Zero edição manual.</b>
        </p>
        <InstallationPicker onSelection={setSelection} />
        <div className="row" style={{ marginTop: 12 }}>
          <div className="fit">
            <button disabled={!selection?.expert?.has_source || preparing} onClick={prepareRobot}>
              {preparing ? 'Preparando…' : 'Preparar robô'}
            </button>
          </div>
        </div>
        {prepared && (
          <div style={{ marginTop: 12 }}>
            <div className="kpi">
              <div className="label">Status</div>
              <div className="value" style={{ color: prepared.compiled ? '#3fb950' : '#f85149' }}>
                {prepared.compiled ? `Pronto: use "${prepared.output_name}" no Strategy Tester` : 'Compilação falhou'}
              </div>
            </div>
            <div className="small muted" style={{ marginTop: 8 }}>
              <div><b>Arquivo:</b> <code>{prepared.output_path}</code></div>
              <div><b>Capturados ({prepared.inputs_captured.length}):</b> {prepared.inputs_captured.join(', ') || '—'}</div>
              {prepared.inputs_skipped.length > 0 && <div><b>Ignorados:</b> {prepared.inputs_skipped.join(', ')}</div>}
            </div>
            {!prepared.compiled && prepared.compile_log_tail && (
              <pre style={{
                marginTop: 8, padding: 10, background: 'var(--panel-2)',
                border: '1px solid var(--border)', borderRadius: 6,
                fontSize: 11, maxHeight: 200, overflow: 'auto', whiteSpace: 'pre-wrap',
              }}>{prepared.compile_log_tail}</pre>
            )}
          </div>
        )}
      </div>

      <div className="card">
        <h2>2. Coleta ao vivo da otimização MT5</h2>
        <p className="muted small">
          Configure a session e clique Iniciar. Abra o Strategy Tester do MT5,
          selecione <code>{prepared?.output_name || '<nome>_Aura'}</code> e rode
          a otimização. Cada pass aparece aqui em tempo real e fica salvo no
          histórico.
        </p>
        <div className="row">
          <div style={{ flex: 2 }}>
            <label>Label da session (opcional)</label>
            <input value={label} onChange={e => setLabel(e.target.value)}
              placeholder={robotName ? `ex: ${robotName} — tuning SL` : 'ex: Big-Small — tuning SL'} />
          </div>
          <div>
            <label>Timeframe</label>
            <select value={timeframe} onChange={e => setTimeframe(e.target.value)}>
              {TIMEFRAMES.map(tf => <option key={tf} value={tf}>{tf}</option>)}
            </select>
          </div>
          <div>
            <label>Ordenar por</label>
            <select value={sortKey} onChange={e => setSortKey(e.target.value)}>
              {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <div className="fit" style={{ paddingBottom: 6, display: 'flex', alignItems: 'flex-end', gap: 6 }}>
            {!running
              ? <ContextualTooltip text="Comece a coletar passes da otimização MT5">
                  <button disabled={loading} onClick={start}>Iniciar coleta</button>
                </ContextualTooltip>
              : <ContextualTooltip text="Pare a coleta quando terminar a otimização">
                  <button disabled={loading} onClick={stop}>Parar coleta</button>
                </ContextualTooltip>}
            <button className="ghost" disabled={loading || !passes.length} onClick={clear}>Limpar tela</button>
            <ContextualTooltip text="Remove arquivos processados do diretório para evitar re-coleta">
              <button className="ghost" disabled={loading} onClick={clearFiles} style={{ opacity: 0.7 }}>🗑️ Limpar arquivos</button>
            </ContextualTooltip>
            <button className="ghost" disabled={!passes.length} onClick={exportCSV}>Exportar CSV</button>
          </div>
        </div>
        <div className="small muted" style={{ marginTop: 10 }}>
          Session: <code>{sessionId || '—'}</code> · Robô: <b>{robotName || '—'}</b> · TF: <b>{timeframe}</b>
          <br/>
          Status: {running ? <b style={{color:'#3fb950'}}>coletando</b> : <b style={{color:'#8b949e'}}>parado</b>}
          {' · '}
          Stream: {connected ? <b style={{color:'#3fb950'}}>conectado</b> : <b style={{color:'#f85149'}}>desconectado</b>}
          {' · '}
          Passes: <b>{passes.length}</b>
          {watchDir && <><br/>Pasta: <code>{watchDir}</code></>}
        </div>
        {error && <div className="errbox" style={{ marginTop: 10 }}>{error}</div>}
      </div>

      {passes.length > 0 && sessionId && (
        <div className="card">
          <h2>3. Analisar top passes</h2>
          <div className="row">
            <div>
              <label>Top N</label>
              <input type="number" min="1" max="100" value={topN}
                onChange={e => setTopN(parseInt(e.target.value) || 10)} />
            </div>
            <div style={{ flex: 2 }}>
              <label>
                Fórmula customizada <span className="muted" style={{ textTransform: 'none' }}>
                  (opcional — sobrescreve ordenação)
                </span>
              </label>
              <input value={customFormula}
                onChange={e => setCustomFormula(e.target.value)}
                placeholder="ex: net_profit / max_drawdown_pct" />
            </div>
            <div className="fit" style={{ paddingBottom: 6, display: 'flex', alignItems: 'flex-end', gap: 8, flexWrap: 'wrap' }}>
              <button className="ghost" disabled={loading || !customFormula.trim()}
                onClick={previewFormula}>
                Testar fórmula
              </button>
              <ContextualTooltip text="Cria runs salvos dos melhores passes para análise individual">
                <button disabled={loading} onClick={openTop}>
                  Abrir top {topN} como runs
                </button>
              </ContextualTooltip>
              <ContextualTooltip text="Próximo passo: analise automática dos passes →">
                <button className="ghost" disabled={loading} onClick={sendToTriage}>
                  Triagem
                </button>
              </ContextualTooltip>
            </div>
          </div>
          {formulaPreview && (
            <div className="small muted" style={{ marginTop: 8 }}>
              Variáveis disponíveis: {formulaPreview.variables_available.slice(0, 12).join(', ')}
              {formulaPreview.variables_available.length > 12 && '…'}
              <br />
              Top pela fórmula: {formulaPreview.top.slice(0, 3).map(t =>
                `${t.score.toFixed(3)}`).join(' · ')}
            </div>
          )}
          {openedRuns && (
            <div style={{ marginTop: 14 }}>
              <p className="muted small">
                Runs criados. Clique em "Abrir" para ir à aba Análise com MC, MAE/MFE, stat validation, etc.
              </p>
              <table>
                <thead>
                  <tr><th>#</th><th>Label</th><th>Score</th><th>Run ID</th><th></th></tr>
                </thead>
                <tbody>
                  {openedRuns.map(r => (
                    <tr key={r.run_id}>
                      <td>{r.rank}</td>
                      <td>{r.label}</td>
                      <td>{r.score?.toFixed(3) ?? '—'}</td>
                      <td className="small muted"><code>{r.run_id}</code></td>
                      <td>
                        <button className="ghost" onClick={() => onOpenRun && onOpenRun(r.run_id)}>
                          Abrir
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {triageResult && (
            <div style={{ marginTop: 14 }}>
              <p className="muted small">
                Análise de estabilidade (vizinhança) dos {triageResult.num_passes} passes.
                Robust Score alto = vizinhos também performam bem (menos suspeita de overfit).
              </p>
              <table>
                <thead>
                  <tr>
                    <th>#</th><th>Params</th><th>Robust Score</th>
                    <th>Estabilidade</th><th>Vizinhos</th>
                    <th>{triageResult.score_key}</th>
                  </tr>
                </thead>
                <tbody>
                  {triageResult.passes.slice(0, 30).map((p, i) => (
                    <tr key={p.pass_idx}>
                      <td>{i + 1}</td>
                      <td className="small"><code>{JSON.stringify(p.parameters)}</code></td>
                      <td>{p.robust_score?.toFixed(2)}</td>
                      <td>{((p.stability ?? 0) * 100).toFixed(1)}%</td>
                      <td>{p.neighbor_count}</td>
                      <td>{p.metrics[triageResult.score_key]?.toFixed(3) ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {triageResult.passes.length > 30 && (
                <p className="muted small">Mostrando top 30 de {triageResult.num_passes}.</p>
              )}
            </div>
          )}
        </div>
      )}

      {sorted.length > 0 && (
        <div className="card">
          <h2>Passes recebidos — ordenado por {SORT_OPTIONS.find(o => o.value === sortKey)?.label}</h2>
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>#</th><th>pass_id</th><th>Trades</th>
                  {paramKeys.map(k => <th key={k}>{k}</th>)}
                  <th style={{ color: '#D4AF5F' }}>★ Aura</th>
                  <th>Sortino</th><th>Sharpe</th><th>Calmar</th>
                  <th>Net Profit</th><th>PF</th><th>DD %</th><th>SQN</th>
                  <th>MT5 Crit.</th>
                </tr>
              </thead>
              <tbody>
                {sorted.slice(0, 100).map((p, i) => {
                  const m = { ...p.native_metrics, ...p.computed_metrics }
                  const aura = p._aura_score
                  const auraColor = aura > 1.5 ? '#3fb950' : aura > 0.5 ? '#d29922' : '#f85149'
                  return (
                    <tr key={p.pass_id}>
                      <td>{i + 1}</td>
                      <td className="small"><code>{(p.pass_id || '').slice(0, 12)}…</code></td>
                      <td>{p.num_trades}</td>
                      {paramKeys.map(k => <td key={k}>{String(p.parameters?.[k] ?? '—')}</td>)}
                      <td style={{ fontWeight: 600, color: auraColor }}>{fmt(aura)}</td>
                      <td>{fmt(m.sortino_ratio)}</td>
                      <td>{fmt(m.sharpe_ratio)}</td>
                      <td>{fmt(m.calmar_ratio)}</td>
                      <td>{fmt(m.net_profit, 2)}</td>
                      <td>{fmt(m.profit_factor)}</td>
                      <td>{fmt(m.max_drawdown_pct, 2)}</td>
                      <td>{fmt(m.sqn)}</td>
                      <td>{fmt(m.complex_criterion)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          {sorted.length > 100 && <p className="muted small">Mostrando top 100 de {sorted.length}.</p>}
        </div>
      )}
    </div>
  )
}

function fmt(v, digits = 3) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return Number(v).toFixed(digits)
}
