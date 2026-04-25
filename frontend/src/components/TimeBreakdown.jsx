import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  Tooltip, CartesianGrid, Cell,
} from 'recharts'

const axisProps = { stroke: '#8b98a5', tick: { fontSize: 11 } }
const tooltipStyle = {
  contentStyle: { background: '#0b0f14', border: '1px solid #1f2a37', fontSize: 12 },
}

function barColor(netProfit) {
  return netProfit >= 0 ? '#3fb950' : '#f85149'
}

function fmtPct(v) { return (v * 100).toFixed(1) + '%' }
function fmtMoney(v) { return v.toFixed(2) }

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div style={{ background: '#0b0f14', border: '1px solid #1f2a37', padding: '8px 12px', fontSize: 12 }}>
      <div><b>{label}</b></div>
      <div>Net Profit: <span style={{ color: barColor(d.net_profit) }}>{fmtMoney(d.net_profit)}</span></div>
      <div>Trades: {d.trades}</div>
      <div>Win Rate: {fmtPct(d.win_rate)}</div>
    </div>
  )
}

function BreakdownChart({ data, xKey, height = 200 }) {
  if (!data?.length) return <div className="muted small">Sem dados</div>
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="#1f2a37" strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey={xKey} {...axisProps} />
        <YAxis {...axisProps} domain={['auto', 'auto']} tickFormatter={v => v.toFixed(0)} />
        <Tooltip content={<CustomTooltip />} {...tooltipStyle} />
        <Bar dataKey="net_profit" maxBarSize={40}>
          {data.map((entry, i) => (
            <Cell key={i} fill={barColor(entry.net_profit)} fillOpacity={0.85} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export function TimeBreakdown({ data }) {
  if (!data) return null
  return (
    <div className="card">
      <h2>Análise Temporal</h2>
      <div className="grid cols-3" style={{ gap: 24 }}>
        <div>
          <div className="muted small" style={{ marginBottom: 6 }}>Por Hora (0–23)</div>
          <BreakdownChart data={data.by_hour} xKey="hour" />
        </div>
        <div>
          <div className="muted small" style={{ marginBottom: 6 }}>Por Dia da Semana</div>
          <BreakdownChart data={data.by_weekday} xKey="weekday" />
        </div>
        <div>
          <div className="muted small" style={{ marginBottom: 6 }}>Por Mês</div>
          <BreakdownChart data={data.by_month} xKey="month" />
        </div>
      </div>
      {data.by_year?.length > 1 && (
        <div style={{ marginTop: 20 }}>
          <div className="muted small" style={{ marginBottom: 6 }}>Por Ano</div>
          <BreakdownChart data={data.by_year} xKey="year" height={180} />
        </div>
      )}
    </div>
  )
}
