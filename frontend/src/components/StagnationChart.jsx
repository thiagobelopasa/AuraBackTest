import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  Tooltip, CartesianGrid, ReferenceArea,
} from 'recharts'

const axisProps = { stroke: '#8b98a5', tick: { fontSize: 11 } }
const tooltipStyle = {
  contentStyle: { background: '#0b0f14', border: '1px solid #1f2a37', fontSize: 12 },
}

export function StagnationChart({ values, periods = [], height = 260 }) {
  if (!values || values.length === 0) return <div className="muted small">Sem dados</div>
  const data = values.map((v, i) => ({ i, equity: v }))

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data}>
        <CartesianGrid stroke="#1f2a37" strokeDasharray="3 3" />
        <XAxis dataKey="i" {...axisProps} />
        <YAxis {...axisProps} domain={['auto', 'auto']} />
        <Tooltip {...tooltipStyle} />
        {periods.map((p, idx) => (
          <ReferenceArea
            key={idx}
            x1={p.start_idx}
            x2={p.end_idx}
            fill="#f85149"
            fillOpacity={0.08}
          />
        ))}
        <Line type="monotone" dataKey="equity" stroke="#58a6ff" dot={false} strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  )
}
