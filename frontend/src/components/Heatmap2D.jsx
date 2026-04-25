import { useMemo } from 'react'

/**
 * Heatmap 2D para passes de otimização.
 * Props:
 *   passes: [{parameters, metrics, stability, neighbor_count}]
 *   xParam, yParam: nomes dos parâmetros nos eixos
 *   metricKey: chave da métrica (ex 'net_profit' ou 'robust_score' ou 'score')
 *   filter: (p) => bool  — passes que falham ficam esmaecidos
 *   aggregate: 'max' | 'mean'
 */
export function Heatmap2D({ passes, xParam, yParam, metricKey, filter, aggregate = 'max' }) {
  const grid = useMemo(() => {
    if (!passes?.length) return null
    const xs = [...new Set(passes.map(p => p.parameters[xParam]).filter(v => v !== undefined))]
      .sort((a, b) => a - b)
    const ys = [...new Set(passes.map(p => p.parameters[yParam]).filter(v => v !== undefined))]
      .sort((a, b) => a - b)
    if (xs.length < 2 || ys.length < 2) return null

    const cells = {} // key: "x|y" -> {values: [], excluded: bool}
    for (const p of passes) {
      const x = p.parameters[xParam]
      const y = p.parameters[yParam]
      if (x === undefined || y === undefined) continue
      const v = metricKey === 'robust_score' ? p.robust_score
        : metricKey === 'stability' ? p.stability
        : p.metrics?.[metricKey]
      if (v === undefined || v === null) continue
      const k = `${x}|${y}`
      if (!cells[k]) cells[k] = { values: [], excluded: [] }
      cells[k].values.push(v)
      cells[k].excluded.push(filter ? !filter(p) : false)
    }

    let vmin = Infinity, vmax = -Infinity
    for (const k of Object.keys(cells)) {
      const vs = cells[k].values
      const agg = aggregate === 'mean'
        ? vs.reduce((a, b) => a + b, 0) / vs.length
        : Math.max(...vs)
      cells[k].agg = agg
      const allExcluded = cells[k].excluded.every(e => e)
      cells[k].excluded = allExcluded
      if (agg < vmin) vmin = agg
      if (agg > vmax) vmax = agg
    }
    return { xs, ys, cells, vmin, vmax }
  }, [passes, xParam, yParam, metricKey, filter, aggregate])

  if (!grid) return <p className="muted small">Sem dados suficientes para heatmap ({xParam} × {yParam}).</p>

  const { xs, ys, cells, vmin, vmax } = grid
  const cellW = 42, cellH = 28, padL = 90, padT = 40, padR = 20, padB = 60
  const w = padL + xs.length * cellW + padR
  const h = padT + ys.length * cellH + padB

  const color = (v) => {
    if (vmax === vmin) return '#1f6feb'
    const t = (v - vmin) / (vmax - vmin)
    // Azul (baixo) → verde (médio) → amarelo (alto)
    const r = Math.round(t < 0.5 ? 30 + t * 2 * 160 : 190 + (t - 0.5) * 2 * 65)
    const g = Math.round(t < 0.5 ? 80 + t * 2 * 140 : 220 - (t - 0.5) * 2 * 40)
    const b = Math.round(t < 0.5 ? 200 - t * 2 * 100 : 100 - (t - 0.5) * 2 * 80)
    return `rgb(${r},${g},${b})`
  }

  return (
    <div style={{ overflow: 'auto', maxWidth: '100%' }}>
      <svg width={w} height={h} style={{ background: '#0d1117', borderRadius: 4 }}>
        <text x={padL + (xs.length * cellW) / 2} y={18} fill="#aaa"
          fontSize="12" textAnchor="middle">{xParam}</text>
        <text x={14} y={padT + (ys.length * cellH) / 2}
          fill="#aaa" fontSize="12" textAnchor="middle"
          transform={`rotate(-90, 14, ${padT + (ys.length * cellH) / 2})`}>{yParam}</text>

        {ys.map((y, j) => (
          ys.length < 20 || j % Math.ceil(ys.length / 20) === 0 ? (
            <text key={`y${j}`} x={padL - 6} y={padT + j * cellH + cellH / 2 + 4}
              fill="#888" fontSize="10" textAnchor="end">{y}</text>
          ) : null
        ))}
        {xs.map((x, i) => (
          xs.length < 20 || i % Math.ceil(xs.length / 20) === 0 ? (
            <text key={`x${i}`} x={padL + i * cellW + cellW / 2}
              y={padT + ys.length * cellH + 14}
              fill="#888" fontSize="10" textAnchor="middle"
              transform={`rotate(45, ${padL + i * cellW + cellW / 2}, ${padT + ys.length * cellH + 14})`}>{x}</text>
          ) : null
        ))}

        {ys.map((y, j) => xs.map((x, i) => {
          const k = `${x}|${y}`
          const cell = cells[k]
          if (!cell) return null
          const fill = color(cell.agg)
          const opacity = cell.excluded ? 0.12 : 1
          return (
            <g key={k}>
              <rect
                x={padL + i * cellW} y={padT + j * cellH}
                width={cellW - 1} height={cellH - 1}
                fill={fill} opacity={opacity}
              >
                <title>{`${xParam}=${x}\n${yParam}=${y}\n${metricKey}=${cell.agg.toFixed(2)}${cell.excluded ? '\n(excluído)' : ''}`}</title>
              </rect>
              {xs.length <= 15 && ys.length <= 15 && (
                <text x={padL + i * cellW + cellW / 2}
                  y={padT + j * cellH + cellH / 2 + 3}
                  fill={cell.excluded ? '#555' : '#000'}
                  fontSize="9" textAnchor="middle" opacity={opacity}>
                  {cell.agg.toFixed(0)}
                </text>
              )}
            </g>
          )
        }))}

        {/* Legenda */}
        <g transform={`translate(${padL}, ${h - 30})`}>
          <text x={0} y={-4} fill="#888" fontSize="10">{metricKey} ({aggregate})</text>
          {Array.from({ length: 20 }).map((_, i) => (
            <rect key={i} x={i * 10} y={0} width={10} height={10}
              fill={color(vmin + (i / 19) * (vmax - vmin))} />
          ))}
          <text x={0} y={22} fill="#888" fontSize="9">{vmin.toFixed(1)}</text>
          <text x={200} y={22} fill="#888" fontSize="9" textAnchor="end">{vmax.toFixed(1)}</text>
        </g>
      </svg>
    </div>
  )
}
