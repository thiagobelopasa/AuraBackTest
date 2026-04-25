import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  Tooltip, CartesianGrid, AreaChart, Area,
} from 'recharts'

const axisProps = { stroke: '#8b98a5', tick: { fontSize: 11 } }
const tooltipStyle = {
  contentStyle: { background: '#0b0f14', border: '1px solid #1f2a37', fontSize: 12 },
}

export function EquityChart({ values, height = 260 }) {
  if (!values || values.length === 0) return <div className="muted small">Sem dados</div>
  const data = values.map((v, i) => ({ i, equity: v }))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data}>
        <CartesianGrid stroke="#1f2a37" strokeDasharray="3 3" />
        <XAxis dataKey="i" {...axisProps} />
        <YAxis {...axisProps} domain={['auto', 'auto']} />
        <Tooltip {...tooltipStyle} />
        <Line type="monotone" dataKey="equity" stroke="#58a6ff" dot={false} strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  )
}

export function DrawdownChart({ values, height = 180 }) {
  if (!values || values.length === 0) return <div className="muted small">Sem dados</div>
  const data = values.map((v, i) => ({ i, dd: -Math.abs(v) }))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data}>
        <CartesianGrid stroke="#1f2a37" strokeDasharray="3 3" />
        <XAxis dataKey="i" {...axisProps} />
        <YAxis {...axisProps} />
        <Tooltip {...tooltipStyle} />
        <Area type="monotone" dataKey="dd" stroke="#f85149" fill="#f85149" fillOpacity={0.18} />
      </AreaChart>
    </ResponsiveContainer>
  )
}

export function HistogramChart({ edges, counts, color = '#58a6ff', height = 200 }) {
  if (!edges || !counts || counts.length === 0) return null
  const data = counts.map((c, i) => ({
    bin: ((edges[i] + edges[i + 1]) / 2).toFixed(1),
    count: c,
  }))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data}>
        <CartesianGrid stroke="#1f2a37" strokeDasharray="3 3" />
        <XAxis dataKey="bin" {...axisProps} />
        <YAxis {...axisProps} />
        <Tooltip {...tooltipStyle} />
        <Area type="step" dataKey="count" stroke={color} fill={color} fillOpacity={0.25} />
      </AreaChart>
    </ResponsiveContainer>
  )
}
