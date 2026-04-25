import { useMemo } from 'react'

/**
 * Parallel coordinates — uma linha por candidato através de todos os parâmetros.
 * Candidatos robustos formam feixes grossos; picos isolados = linhas solitárias.
 * Excluídos pelo filtro ficam esmaecidos.
 */
export function ParallelCoords({ passes, params, metricKey, filter }) {
  const data = useMemo(() => {
    if (!passes?.length || !params?.length) return null
    const scales = params.map(p => {
      const vals = passes.map(x => x.parameters[p]).filter(v => typeof v === 'number')
      return { param: p, min: Math.min(...vals), max: Math.max(...vals) }
    })
    const metrics = passes.map(p =>
      metricKey === 'robust_score' ? p.robust_score
      : metricKey === 'stability' ? p.stability
      : p.metrics?.[metricKey] ?? 0
    )
    const mMin = Math.min(...metrics), mMax = Math.max(...metrics)
    return { scales, mMin, mMax }
  }, [passes, params, metricKey])

  const top5 = useMemo(() => {
    if (!passes?.length) return []
    const getM = (p) =>
      metricKey === 'robust_score' ? p.robust_score
      : metricKey === 'stability' ? p.stability
      : p.metrics?.[metricKey] ?? 0
    const pool = filter ? passes.filter(filter) : passes
    return [...pool].sort((a, b) => getM(b) - getM(a)).slice(0, 5)
  }, [passes, metricKey, filter])

  const topRegion = useMemo(() => {
    if (!top5.length || !params?.length) return null
    const region = {}
    for (const k of params) {
      const vals = top5.map(p => p.parameters[k]).filter(v => typeof v === 'number')
      if (!vals.length) continue
      const min = Math.min(...vals), max = Math.max(...vals)
      const mean = vals.reduce((s, v) => s + v, 0) / vals.length
      region[k] = { min, max, mean }
    }
    return region
  }, [top5, params])

  if (!data) return <p className="muted small">Sem dados.</p>

  const { scales, mMin, mMax } = data
  const topIds = new Set(top5.map(p => p.pass_idx))
  const padL = 60, padR = 20, padT = 30, padB = 40
  const plotW = Math.max(600, params.length * 120)
  const plotH = 360
  const w = padL + plotW + padR
  const h = padT + plotH + padB

  const axisX = (i) => padL + (plotW * i) / (params.length - 1 || 1)
  const scaleY = (s, v) => {
    if (s.max === s.min) return padT + plotH / 2
    return padT + plotH - ((v - s.min) / (s.max - s.min)) * plotH
  }

  const colorFor = (m) => {
    if (mMax === mMin) return '#3fb950'
    const t = (m - mMin) / (mMax - mMin)
    const r = Math.round(30 + t * 225)
    const g = Math.round(80 + t * 150)
    const b = Math.round(200 - t * 180)
    return `rgb(${r},${g},${b})`
  }

  // Ordena: excluídos primeiro (ficam atrás), depois por métrica crescente (melhores no topo)
  const sorted = [...passes].sort((a, b) => {
    const aEx = filter ? !filter(a) : false
    const bEx = filter ? !filter(b) : false
    if (aEx !== bEx) return aEx ? -1 : 1
    const am = metricKey === 'robust_score' ? a.robust_score
      : metricKey === 'stability' ? a.stability
      : a.metrics?.[metricKey] ?? 0
    const bm = metricKey === 'robust_score' ? b.robust_score
      : metricKey === 'stability' ? b.stability
      : b.metrics?.[metricKey] ?? 0
    return am - bm
  })

  return (
    <div style={{ overflow: 'auto', maxWidth: '100%' }}>
      <svg width={w} height={h} style={{ background: '#0d1117', borderRadius: 4 }}>
        {scales.map((s, i) => (
          <g key={s.param}>
            <line x1={axisX(i)} y1={padT} x2={axisX(i)} y2={padT + plotH}
              stroke="#30363d" />
            <text x={axisX(i)} y={padT - 8} fill="#ccc" fontSize="11"
              textAnchor="middle">{s.param}</text>
            <text x={axisX(i)} y={padT + plotH + 14} fill="#666" fontSize="9"
              textAnchor="middle">{s.min}</text>
            <text x={axisX(i)} y={padT - 18} fill="#666" fontSize="9"
              textAnchor="middle">{s.max}</text>
          </g>
        ))}

        {sorted.map((p, idx) => {
          const m = metricKey === 'robust_score' ? p.robust_score
            : metricKey === 'stability' ? p.stability
            : p.metrics?.[metricKey] ?? 0
          const excluded = filter ? !filter(p) : false
          const pts = scales.map((s, i) => {
            const v = p.parameters[s.param]
            if (typeof v !== 'number') return null
            return `${axisX(i)},${scaleY(s, v)}`
          }).filter(Boolean).join(' ')
          const isTop = topIds.has(p.pass_idx)
          return (
            <polyline key={idx} points={pts}
              fill="none"
              stroke={isTop ? '#ff4fd8' : colorFor(m)}
              strokeWidth={isTop ? 2.5 : excluded ? 0.5 : 1}
              opacity={isTop ? 1 : excluded ? 0.08 : 0.4} />
          )
        })}

        <g transform={`translate(${padL}, ${h - 18})`}>
          <text x={0} y={0} fill="#888" fontSize="10">
            Cor = {metricKey} ({mMin.toFixed(1)} → {mMax.toFixed(1)}) ·
          </text>
          <text x={200} y={0} fill="#ff4fd8" fontSize="10" fontWeight="600">
            magenta = top 5
          </text>
        </g>
      </svg>
      {topRegion && (
        <div style={{ marginTop: 10, padding: 10, border: '1px solid #ff4fd855',
          borderRadius: 6, background: 'rgba(255,79,216,0.06)' }}>
          <div style={{ color: '#ff4fd8', fontWeight: 600, marginBottom: 6, fontSize: 13 }}>
            Região do top 5 (inputs recomendados)
          </div>
          <table style={{ fontSize: 12 }}>
            <thead><tr><th>Parâmetro</th><th>Mín</th><th>Média</th><th>Máx</th></tr></thead>
            <tbody>
              {Object.entries(topRegion).map(([k, r]) => (
                <tr key={k}>
                  <td><code>{k}</code></td>
                  <td>{r.min.toFixed(3)}</td>
                  <td><b>{r.mean.toFixed(3)}</b></td>
                  <td>{r.max.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small" style={{ marginTop: 6 }}>
            Se os 5 melhores convergem num intervalo estreito = região robusta.
            Se min/máx são muito distantes, o "top" é provavelmente ruído de otimização.
          </p>
        </div>
      )}
    </div>
  )
}
