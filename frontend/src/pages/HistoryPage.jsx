import { useEffect, useState } from 'react'
import {
  listRuns, deleteRun, updateRunLabel, setRunFavorite,
  listLiveSessions, deleteLiveSession, openTopAsRuns, sessionToTriage,
  sessionPBO, setSessionFavorite, getLiveSessionPasses,
  errorMessage,
} from '../services/api'
import { downloadCSV } from '../services/csv'
import { useToast } from '../components/Toast'

export function HistoryPage({ onOpenRun }) {
  const { toast } = useToast()
  const [runs, setRuns] = useState([])
  const [kind, setKind] = useState('')
  const [onlyFavorites, setOnlyFavorites] = useState(false)
  const [loading, setLoading] = useState(false)
  const [editing, setEditing] = useState(null)

  const [sessions, setSessions] = useState([])
  const [sessionError, setSessionError] = useState('')
  const [sessionLoading, setSessionLoading] = useState(false)

  const refresh = async () => {
    setLoading(true)
    try {
      const r = await listRuns({ limit: 200, ...(kind ? { kind } : {}) })
      setRuns(r)
    } finally { setLoading(false) }
  }

  const refreshSessions = async () => {
    setSessionLoading(true); setSessionError('')
    try {
      const r = await listLiveSessions(100)
      setSessions(r)
    } catch (e) {
      setSessionError(errorMessage(e))
    } finally { setSessionLoading(false) }
  }

  useEffect(() => { refresh() }, [kind])
  useEffect(() => { refreshSessions() }, [])

  const doDelete = async (id) => {
    if (!confirm(`Deletar run ${id}?`)) return
    await deleteRun(id)
    refresh()
  }

  const saveLabel = async () => {
    if (!editing) return
    await updateRunLabel(editing.id, editing.value)
    setEditing(null)
    refresh()
  }

  const deleteSession = async (id) => {
    if (!confirm(`Deletar coleta ${id} e todos os passes?`)) return
    try {
      await deleteLiveSession(id)
      refreshSessions()
      toast.success('Coleta deletada', `Session ${id}`)
    } catch (e) { toast.error('Falha ao deletar', errorMessage(e)) }
  }

  const openTop = async (sessionId) => {
    const nStr = prompt('Quantos passes abrir como runs individuais?', '10')
    if (!nStr) return
    const n = parseInt(nStr, 10)
    if (!n || n < 1) return
    setSessionLoading(true); setSessionError('')
    try {
      const created = await openTopAsRuns(sessionId, {
        sort_key: 'sortino_ratio',
        top_n: n,
        ascending: false,
      })
      toast.success(`${created.length} runs criados`, 'Aparecem na lista abaixo — clique Abrir pra análise individual.')
      refresh()
    } catch (e) { toast.error('Falha', errorMessage(e)) }
    finally { setSessionLoading(false) }
  }

  const toTriage = async (sessionId) => {
    setSessionLoading(true); setSessionError('')
    try {
      const r = await sessionToTriage(sessionId, 'sortino_ratio')
      const topMsg = r.passes.slice(0, 3).map(p =>
        `#${p.pass_idx}: robust=${p.robust_score?.toFixed(2)}`
      ).join(' · ')
      toast.info(`Triagem: ${r.num_passes} passes`, `Top: ${topMsg}`)
    } catch (e) { toast.error('Falha na triagem', errorMessage(e)) }
    finally { setSessionLoading(false) }
  }

  const computePBO = async (s) => {
    setSessionLoading(true)
    try {
      const r = await sessionPBO(s.id, 16, 20)
      const color = r.pbo < 0.25 ? 'success' : r.pbo < 0.5 ? 'info' : r.pbo < 0.75 ? 'gold' : 'error'
      toast[color === 'success' ? 'success' : color === 'error' ? 'error' : 'info'](
        `PBO = ${(r.pbo * 100).toFixed(1)}%`,
        `${r.n_combinations} combos CSCV · ${r.n_candidates} candidatos · ${r.interpretation}`,
        { duration: 12000 }
      )
    } catch (e) {
      toast.error('Falha no PBO', errorMessage(e))
    } finally { setSessionLoading(false) }
  }

  const toggleSessionFav = async (s) => {
    try {
      await setSessionFavorite(s.id, !s.favorite)
      refreshSessions()
    } catch (e) { toast.error('Falha ao favoritar', errorMessage(e)) }
  }

  const toggleRunFav = async (r) => {
    try {
      await setRunFavorite(r.id, !r.favorite)
      refresh()
    } catch (e) { toast.error('Falha ao favoritar', errorMessage(e)) }
  }

  const exportSessionCSV = async (s) => {
    try {
      const d = await getLiveSessionPasses(s.id)
      const rows = (d.passes || []).map(p => ({
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
      if (!rows.length) { toast.error('Session sem passes'); return }
      const fname = `${s.robot_name || 'aura'}_${s.symbol || ''}_${s.timeframe || ''}_${s.id}.csv`
      downloadCSV(rows, fname)
      toast.success('CSV exportado', `${rows.length} linhas — ${fname}`)
    } catch (e) { toast.error('Falha ao exportar', errorMessage(e)) }
  }

  const exportRunsCSV = () => {
    const rows = filteredRuns.map(r => ({
      id: r.id, label: r.label, kind: r.kind,
      symbol: r.symbol, timeframe: r.timeframe,
      from_date: r.from_date, to_date: r.to_date,
      created_at: r.created_at, favorite: r.favorite ? 1 : 0,
      ...(r.metrics_parsed || {}),
    }))
    if (!rows.length) { toast.error('Nenhum run pra exportar'); return }
    downloadCSV(rows, `aurabacktest_runs_${new Date().toISOString().slice(0,10)}.csv`)
    toast.success('CSV exportado', `${rows.length} runs`)
  }

  const filteredRuns = onlyFavorites ? runs.filter(r => r.favorite) : runs
  const filteredSessions = onlyFavorites ? sessions.filter(s => s.favorite) : sessions

  return (
    <div>
      <div className="card">
        <h2>Coletas ao vivo (sessions)</h2>
        <div className="row">
          <div className="fit" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input type="checkbox" checked={onlyFavorites}
              onChange={e => setOnlyFavorites(e.target.checked)} />
            <span className="small muted">só favoritos ⭐</span>
          </div>
          <div className="fit">
            <button onClick={refreshSessions} disabled={sessionLoading}>
              {sessionLoading ? '...' : 'Atualizar'}
            </button>
          </div>
        </div>
        <table style={{ marginTop: 14 }}>
          <thead>
            <tr>
              <th style={{ width: 32 }}></th>
              <th>Label / robô</th><th>Símbolo</th><th>TF</th>
              <th>Passes</th><th>Início</th><th>Fim</th>
              <th>Session ID</th><th></th>
            </tr>
          </thead>
          <tbody>
            {filteredSessions.map(s => (
              <tr key={s.id}>
                <td>
                  <button className={`star-btn ${s.favorite ? 'active' : ''}`}
                    onClick={() => toggleSessionFav(s)}
                    title={s.favorite ? 'Remover dos favoritos' : 'Marcar como favorito'}>
                    {s.favorite ? '★' : '☆'}
                  </button>
                </td>
                <td>
                  {s.label?.trim() || s.robot_name || <span className="muted">sem label</span>}
                  {s.favorite && <span className="pill gold" style={{ marginLeft: 8 }}>golden</span>}
                </td>
                <td><b>{s.symbol || '—'}</b></td>
                <td><b>{s.timeframe || '—'}</b></td>
                <td>{s.pass_count}</td>
                <td className="small muted">{s.started_at}</td>
                <td className="small muted">{s.ended_at || '(em andamento)'}</td>
                <td className="small muted"><code>{s.id}</code></td>
                <td>
                  <button className="ghost" style={{ marginRight: 6 }}
                    disabled={!s.pass_count}
                    onClick={() => openTop(s.id)}>
                    Abrir top N
                  </button>
                  <button className="ghost" style={{ marginRight: 6 }}
                    disabled={!s.pass_count}
                    onClick={() => toTriage(s.id)}>
                    Triagem
                  </button>
                  <button className="ghost" style={{ marginRight: 6 }}
                    disabled={!s.pass_count || s.pass_count < 2}
                    onClick={() => computePBO(s)}
                    title="Probability of Backtest Overfitting via CSCV">
                    PBO
                  </button>
                  <button className="ghost" style={{ marginRight: 6 }}
                    disabled={!s.pass_count}
                    onClick={() => exportSessionCSV(s)}>
                    CSV
                  </button>
                  <button className="ghost" onClick={() => deleteSession(s.id)}>
                    Deletar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filteredSessions.length === 0 && (
          <p className="muted small" style={{ marginTop: 10 }}>
            {onlyFavorites ? 'Nenhuma coleta favorita.' : 'Nenhuma coleta registrada. Vá na aba Coleta ao vivo pra iniciar.'}
          </p>
        )}
        {sessionError && <div className="errbox" style={{ marginTop: 10 }}>{sessionError}</div>}
      </div>

      <div className="card">
        <h2>Histórico de Runs</h2>
        <div className="row">
          <div>
            <label>Filtrar por tipo</label>
            <select value={kind} onChange={e => setKind(e.target.value)}>
              <option value="">todos</option>
              <option value="single">single</option>
              <option value="optimization">optimization</option>
              <option value="wfa">wfa</option>
              <option value="live_pass">live_pass</option>
            </select>
          </div>
          <div className="fit">
            <button onClick={refresh} disabled={loading}>{loading ? '...' : 'Atualizar'}</button>
          </div>
          <div className="fit">
            <button className="ghost" disabled={!filteredRuns.length} onClick={exportRunsCSV}>
              Exportar CSV
            </button>
          </div>
        </div>

        <table style={{ marginTop: 14 }}>
          <thead>
            <tr>
              <th style={{ width: 32 }}></th>
              <th>Nome / robô</th><th>Ativo</th><th>TF</th><th>Fingerprint</th>
              <th>Tipo</th><th>Período</th><th>Criado</th><th>ID</th><th></th>
            </tr>
          </thead>
          <tbody>
            {filteredRuns.map(r => (
              <tr key={r.id}>
                <td>
                  <button className={`star-btn ${r.favorite ? 'active' : ''}`}
                    onClick={() => toggleRunFav(r)}
                    title={r.favorite ? 'Remover dos favoritos' : 'Marcar como favorito'}>
                    {r.favorite ? '★' : '☆'}
                  </button>
                </td>
                <td>
                  {editing?.id === r.id ? (
                    <input autoFocus value={editing.value}
                      onChange={e => setEditing({ ...editing, value: e.target.value })}
                      onBlur={saveLabel}
                      onKeyDown={e => {
                        if (e.key === 'Enter') saveLabel()
                        if (e.key === 'Escape') setEditing(null)
                      }}
                      style={{ width: '100%' }} />
                  ) : (
                    <span style={{ cursor: 'pointer' }} title="Clique para renomear"
                      onClick={() => setEditing({ id: r.id, value: r.label || '' })}>
                      {r.label?.trim() || <span className="muted">— clique pra nomear —</span>}
                      {r.favorite && <span className="pill gold" style={{ marginLeft: 8 }}>golden</span>}
                    </span>
                  )}
                </td>
                <td><b>{r.symbol || '—'}</b></td>
                <td><b>{r.timeframe || '—'}</b></td>
                <td className="small muted">{r.params_hash ? <code>#{r.params_hash}</code> : '—'}</td>
                <td><span className="pill">{r.kind}</span></td>
                <td className="small muted">{r.from_date} → {r.to_date}</td>
                <td className="small muted">{r.created_at}</td>
                <td className="small muted"><code>{r.id}</code></td>
                <td>
                  <button className="ghost" style={{ marginRight: 6 }} onClick={() => onOpenRun && onOpenRun(r.id)}>Abrir</button>
                  <button className="ghost" onClick={() => doDelete(r.id)}>Deletar</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filteredRuns.length === 0 && (
          <p className="muted small" style={{ marginTop: 10 }}>
            {onlyFavorites ? 'Nenhum run favorito.' : 'Sem runs registrados.'}
          </p>
        )}
      </div>
    </div>
  )
}
