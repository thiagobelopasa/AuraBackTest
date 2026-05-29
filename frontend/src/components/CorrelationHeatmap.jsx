/**
 * Heatmap SVG para matriz de correlação simétrica.
 * Props:
 *   matrix  – array 2D N×N de valores em [-1, 1]
 *   labels  – array N de strings (nomes dos runs nos eixos)
 *   runIds  – array N de run_ids (não usado na renderização, mas disponível)
 */
export function CorrelationHeatmap({ matrix, labels }) {
  if (!matrix || !matrix.length || !labels?.length) return null

  const n = matrix.length
  const cellSize = Math.max(40, Math.min(72, Math.floor(420 / n)))
  const padL = 120
  const padT = 16
  const padB = 100
  const padR = 16
  const w = padL + n * cellSize + padR
  const h = padT + n * cellSize + padB

  // vermelho (1) → branco (0) → verde (-1)
  const color = (v) => {
    const clamped = Math.max(-1, Math.min(1, v))
    if (clamped >= 0) {
      // de branco a vermelho
      const t = clamped
      const r = 248
      const g = Math.round(255 - t * (255 - 81))
      const b = Math.round(255 - t * (255 - 73))
      return `rgb(${r},${g},${b})`
    } else {
      // de branco a verde
      const t = -clamped
      const r = Math.round(255 - t * (255 - 63))
      const g = Math.round(255 - t * (255 - 185))
      const b = Math.round(255 - t * (255 - 80))
      return `rgb(${r},${g},${b})`
    }
  }

  const truncLabel = (s) => s.length > 14 ? s.slice(0, 13) + '…' : s

  return (
    <div style={{ overflowX: 'auto', maxWidth: '100%' }}>
      <svg width={w} height={h} style={{ background: '#0d1117', borderRadius: 6, display: 'block' }}>
        {/* Rótulos do eixo Y (linhas) */}
        {labels.map((lbl, i) => (
          <text
            key={`yl${i}`}
            x={padL - 8}
            y={padT + i * cellSize + cellSize / 2 + 4}
            fill="#8b949e"
            fontSize={Math.min(11, cellSize * 0.28)}
            textAnchor="end"
          >
            {truncLabel(lbl)}
          </text>
        ))}

        {/* Rótulos do eixo X (colunas) — rotacionados */}
        {labels.map((lbl, j) => (
          <text
            key={`xl${j}`}
            x={padL + j * cellSize + cellSize / 2}
            y={padT + n * cellSize + 10}
            fill="#8b949e"
            fontSize={Math.min(11, cellSize * 0.28)}
            textAnchor="start"
            transform={`rotate(45, ${padL + j * cellSize + cellSize / 2}, ${padT + n * cellSize + 10})`}
          >
            {truncLabel(lbl)}
          </text>
        ))}

        {/* Células */}
        {matrix.map((row, i) =>
          row.map((v, j) => {
            const isDiag = i === j
            const fill = isDiag ? '#21262d' : color(v)
            const textColor = isDiag ? '#484f58' : (Math.abs(v) > 0.5 ? '#fff' : '#000')
            return (
              <g key={`${i}-${j}`}>
                <rect
                  x={padL + j * cellSize}
                  y={padT + i * cellSize}
                  width={cellSize - 1}
                  height={cellSize - 1}
                  fill={fill}
                  rx={2}
                >
                  <title>{`${labels[i]} × ${labels[j]}: ${v.toFixed(3)}`}</title>
                </rect>
                {cellSize >= 38 && (
                  <text
                    x={padL + j * cellSize + cellSize / 2}
                    y={padT + i * cellSize + cellSize / 2 + 4}
                    fill={isDiag ? '#484f58' : textColor}
                    fontSize={Math.min(10, cellSize * 0.24)}
                    textAnchor="middle"
                    style={{ pointerEvents: 'none' }}
                  >
                    {isDiag ? '—' : v.toFixed(2)}
                  </text>
                )}
              </g>
            )
          })
        )}

        {/* Legenda de escala */}
        <g transform={`translate(${padL}, ${padT + n * cellSize + padB - 22})`}>
          <text x={0} y={-6} fill="#484f58" fontSize={9}>−1 (descorrelacionado)</text>
          {Array.from({ length: 30 }).map((_, k) => {
            const v = -1 + (k / 29) * 2
            return (
              <rect key={k} x={k * 7} y={0} width={7} height={10} fill={color(v)} />
            )
          })}
          <text x={210} y={-6} fill="#484f58" fontSize={9} textAnchor="end">+1 (correlacionado)</text>
        </g>
      </svg>
    </div>
  )
}
