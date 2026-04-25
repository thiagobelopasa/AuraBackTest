import { useEffect, useState } from 'react'
import {
  ResponsiveContainer, ScatterChart, Scatter, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceLine, BarChart, Bar, Cell,
} from 'recharts'
import { getMaeMfeTicks, fetchRunTicks, errorMessage } from '../services/api'

const axisProps = { stroke: '#8b98a5', tick: { fontSize: 11 } }
const tooltipStyle = {
  contentStyle: { background: '#0b0f14', border: '1px solid #1f2a37', fontSize: 12 },
}

function ScatterTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload
  if (!d) return null
  return (
    <div style={{ background: '#0b0f14', border: '1px solid #1f2a37', padding: '8px 12px', fontSize: 12 }}>
      <div>Trade #{d.trade_num} · <b>{d.side}</b></div>
      <div>Profit: <span style={{ color: d.is_win ? '#3fb950' : '#f85149' }}>{d.profit.toFixed(2)}</span></div>
      <div>Duração: {(d.duration_sec / 60).toFixed(0)} min</div>
      <div>R-múltiplo: {d.r_multiple.toFixed(2)}</div>
    </div>
  )
}

function buildScatterSeries(data) {
  return {
    buyWin: data.filter(d => d.side === 'buy' && d.is_win),
    buyLoss: data.filter(d => d.side === 'buy' && !d.is_win),
    sellWin: data.filter(d => d.side === 'sell' && d.is_win),
    sellLoss: data.filter(d => d.side === 'sell' && !d.is_win),
  }
}

function buildRHist(data) {
  const vals = data.map(d => d.r_multiple)
  if (!vals.length) return []
  const min = Math.floor(Math.min(...vals))
  const max = Math.ceil(Math.max(...vals))
  const bins = 20
  const step = (max - min) / bins || 1
  const buckets = Array.from({ length: bins }, (_, i) => ({
    label: (min + i * step).toFixed(1),
    count: 0,
    positive: (min + i * step) >= 0,
  }))
  vals.forEach(v => {
    const idx = Math.min(bins - 1, Math.floor((v - min) / step))
    if (idx >= 0) buckets[idx].count++
  })
  return buckets
}

function TickLoader({ runId, ticksPath, onLoad }) {
  const [path, setPath] = useState(ticksPath || '')
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => { if (ticksPath) setPath(ticksPath) }, [ticksPath])

  const doFetch = async () => {
    setLoading(true); setErr('')
    try {
      const r = await fetchRunTicks(runId)
      setPath(r.parquet_path)
      const result = await getMaeMfeTicks(runId, r.parquet_path)
      onLoad(result)
    } catch (e) {
      setErr(errorMessage(e))
    } finally { setLoading(false) }
  }

  const doCalc = async () => {
    if (!path || !runId) return
    setLoading(true); setErr('')
    try {
      const result = await getMaeMfeTicks(runId, path)
      onLoad(result)
    } catch (e) {
      setErr(errorMessage(e))
    } finally { setLoading(false) }
  }

  return (
    <div style={{ marginTop: 12, padding: '10px 14px', background: 'rgba(88,166,255,0.05)', borderRadius: 6, border: '1px solid #1f2a37' }}>
      <div className="muted small" style={{ marginBottom: 8 }}>
        Calcular MAE/MFE reais com dados de tick (mais preciso que proxy)
      </div>
      {path ? (
        <div className="row" style={{ gap: 8 }}>
          <div style={{ flex: 4, fontSize: 12, color: '#3fb950', display: 'flex', alignItems: 'center', gap: 6 }}>
            ✓ <code style={{ color: '#8b98a5', fontSize: 11 }}>{path}</code>
            <button className="ghost" style={{ fontSize: 11, padding: '2px 6px' }}
              onClick={() => setPath('')}>trocar</button>
          </div>
          <div className="fit">
            <button disabled={loading} onClick={doCalc} style={{ fontSize: 12 }}>
              {loading ? 'Calculando...' : 'Recalcular com ticks'}
            </button>
          </div>
        </div>
      ) : (
        <div className="row" style={{ gap: 8 }}>
          <button disabled={loading || !runId} style={{ fontSize: 12 }} onClick={doFetch}>
            {loading ? 'Baixando e calculando…' : 'Buscar ticks e calcular'}
          </button>
          <div style={{ flex: 4 }}>
            <input value={path} onChange={e => setPath(e.target.value)}
              placeholder="ou informe caminho manual: C:/ticks/WIN/ticks.parquet"
              style={{ width: '100%', fontSize: 12 }} />
          </div>
          {path && (
            <button disabled={loading} onClick={doCalc} style={{ fontSize: 12 }}>
              {loading ? 'Calculando...' : 'Calcular'}
            </button>
          )}
        </div>
      )}
      {err && <div className="errbox" style={{ marginTop: 6, fontSize: 12 }}>{err}</div>}
    </div>
  )
}

function TickStats({ stats }) {
  if (!stats || !stats.n_trades_with_ticks) return null
  const fmt = v => v != null ? v.toFixed(2) : '—'
  const pct = v => v != null ? (v * 100).toFixed(1) + '%' : '—'
  return (
    <div className="grid cols-4" style={{ marginTop: 14, gap: 12 }}>
      {[
        { label: 'Edge Ratio (MFE/MAE)', value: fmt(stats.edge_ratio), note: '> 1 = MFE > MAE' },
        { label: 'Eficiência média', value: pct(stats.pct_mfe_captured), note: 'Profit / MFE' },
        { label: 'Eficiência entrada', value: pct(stats.avg_entry_efficiency), note: '1 - MAE/MFE' },
        { label: 'TP ótimo estimado (P75)', value: fmt(stats.optimal_tp_estimate), note: 'P75 do MFE ($)' },
        { label: 'SL ótimo estimado (P75)', value: fmt(stats.optimal_sl_estimate), note: 'P75 do MAE ($)' },
        { label: 'Trades com ticks', value: String(stats.n_trades_with_ticks), note: '' },
      ].map(k => (
        <div key={k.label} style={{ background: 'rgba(255,255,255,0.03)', padding: '8px 10px', borderRadius: 6 }}>
          <div className="muted small">{k.label}</div>
          <div style={{ fontSize: 18, fontWeight: 600, marginTop: 2 }}>{k.value}</div>
          {k.note && <div className="muted small">{k.note}</div>}
        </div>
      ))}
    </div>
  )
}

export function MaeMfe({ data, runId, ticksPath }) {
  const [tab, setTab] = useState('scatter')
  const [tickResult, setTickResult] = useState(null)
  if (!data || data.length === 0) return null

  const activeData = tickResult?.trades || data
  const isRealData = !!tickResult

  const series = buildScatterSeries(activeData)
  const rHist = buildRHist(activeData)
  const xMax = Math.max(...activeData.map(d => (d.duration_sec || 0) / 60)) * 1.05 || 100

  return (
    <div className="card">
      <h2>MAE / MFE — Eficiência do SL/TP
        {isRealData && <span className="pill pos" style={{ marginLeft: 10, fontSize: 11 }}>DADOS REAIS DE TICK</span>}
        {!isRealData && <span className="pill" style={{ marginLeft: 10, fontSize: 11, background: 'rgba(210,153,34,0.2)', color: '#d29922' }}>PROXY</span>}
      </h2>
      {!isRealData && <TickLoader runId={runId} ticksPath={ticksPath} onLoad={setTickResult} />}
      {isRealData && <TickStats stats={tickResult?.stats} />}
      <div className="row" style={{ marginBottom: 12, gap: 8, marginTop: 12 }}>
        {['scatter', 'r-multiple'].map(t => (
          <button key={t} className={tab === t ? '' : 'secondary'}
            style={{ fontSize: 12, padding: '4px 12px' }}
            onClick={() => setTab(t)}>
            {t === 'scatter' ? 'Scatter Profit × Duração' : 'Histograma R-Múltiplo'}
          </button>
        ))}
      </div>

      {tab === 'scatter' && (
        <>
          <div className="muted small" style={{ marginBottom: 6 }}>
            Eixo X = duração (min) · Eixo Y = profit · Azul=buy win · Vermelho=buy loss · Verde=sell win · Laranja=sell loss
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="#1f2a37" strokeDasharray="3 3" />
              <XAxis type="number" dataKey="duration_min" name="Duração (min)"
                domain={[0, xMax]} {...axisProps} label={{ value: 'min', position: 'insideRight', fontSize: 10 }} />
              <YAxis type="number" dataKey="profit" name="Profit" {...axisProps} domain={['auto', 'auto']} />
              <ReferenceLine y={0} stroke="#8b98a5" strokeDasharray="4 2" />
              <Tooltip content={<ScatterTooltip />} />
              {series.buyWin.length > 0 && (
                <Scatter name="Buy Win" data={series.buyWin.map(d => ({ ...d, duration_min: d.duration_sec / 60 }))}
                  fill="#58a6ff" opacity={0.7} />
              )}
              {series.buyLoss.length > 0 && (
                <Scatter name="Buy Loss" data={series.buyLoss.map(d => ({ ...d, duration_min: d.duration_sec / 60 }))}
                  fill="#f85149" opacity={0.7} />
              )}
              {series.sellWin.length > 0 && (
                <Scatter name="Sell Win" data={series.sellWin.map(d => ({ ...d, duration_min: d.duration_sec / 60 }))}
                  fill="#3fb950" shape="triangle" opacity={0.7} />
              )}
              {series.sellLoss.length > 0 && (
                <Scatter name="Sell Loss" data={series.sellLoss.map(d => ({ ...d, duration_min: d.duration_sec / 60 }))}
                  fill="#d29922" shape="triangle" opacity={0.7} />
              )}
            </ScatterChart>
          </ResponsiveContainer>
        </>
      )}

      {tab === 'r-multiple' && (
        <>
          <div className="muted small" style={{ marginBottom: 6 }}>
            Distribuição dos R-múltiplos (profit / avg_loss). R&gt;0 = winner, R&lt;0 = loser.
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={rHist} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="#1f2a37" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="label" {...axisProps} />
              <YAxis {...axisProps} />
              <Tooltip contentStyle={tooltipStyle.contentStyle} />
              <ReferenceLine x="0.0" stroke="#8b98a5" strokeDasharray="4 2" />
              <Bar dataKey="count" maxBarSize={30}>
                {rHist.map((entry, i) => (
                  <Cell key={i} fill={entry.positive ? '#3fb950' : '#f85149'} fillOpacity={0.8} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  )
}
