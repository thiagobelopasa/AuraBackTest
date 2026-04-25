import { useMemo, useState, useEffect } from 'react'

const MAX_POINTS = 3000

/**
 * Visualização 3D dos passes de otimização.
 * mode='sphere'  — planeta com "montanhas" (radius = base + metric normalizada)
 * mode='scatter' — PCA scatter cru (PC1, PC2, PC3)
 *
 * Pontos esmaecidos = excluídos pelos filtros de estabilidade/vizinhos.
 */
export function Planet3D({ projection, passes, filter, mode = 'sphere' }) {
  const [Plot, setPlot] = useState(null)
  const [loadErr, setLoadErr] = useState(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      import('react-plotly.js/factory'),
      import('plotly.js-dist-min'),
    ]).then(([factoryMod, plotlyMod]) => {
      if (cancelled) return
      const createPlotlyComponent = factoryMod.default || factoryMod
      const Plotly = plotlyMod.default || plotlyMod
      setPlot(() => createPlotlyComponent(Plotly))
    }).catch(e => {
      if (!cancelled) setLoadErr(e.message || String(e))
    })
    return () => { cancelled = true }
  }, [])

  const traces = useMemo(() => {
    if (!projection || !passes) return []

    const included = { x: [], y: [], z: [], m: [], text: [] }
    const excluded = { x: [], y: [], z: [], m: [], text: [] }

    // Subsample para evitar travamento do WebGL em datasets grandes.
    const n = passes.length
    const stride = n > MAX_POINTS ? Math.ceil(n / MAX_POINTS) : 1

    for (let i = 0; i < n; i += stride) {
      const p = passes[i]
      const bucket = (filter && !filter(p)) ? excluded : included
      bucket.x.push(projection.x[i])
      bucket.y.push(projection.y[i])
      bucket.z.push(projection.z[i])
      bucket.m.push(projection.metric[i])
      const paramStr = Object.entries(p.parameters)
        .map(([k, v]) => `${k}=${typeof v === 'number' ? v.toFixed(3) : v}`)
        .join('<br>')
      bucket.text.push(
        `${projection.metric_key}: ${projection.metric[i].toFixed(2)}<br>` +
        `estabilidade: ${((p.stability ?? 0) * 100).toFixed(1)}%<br>` +
        `vizinhos: ${p.neighbor_count}<br>` +
        `<br>${paramStr}`
      )
    }

    const t = []
    if (excluded.x.length) {
      t.push({
        type: 'scatter3d',
        mode: 'markers',
        name: 'excluídos',
        x: excluded.x, y: excluded.y, z: excluded.z,
        text: excluded.text,
        hoverinfo: 'text',
        marker: { size: 2, color: '#444', opacity: 0.15 },
      })
    }
    if (included.x.length) {
      t.push({
        type: 'scatter3d',
        mode: 'markers',
        name: 'robustos',
        x: included.x, y: included.y, z: included.z,
        text: included.text,
        hoverinfo: 'text',
        marker: {
          size: 4,
          color: included.m,
          colorscale: 'Viridis',
          showscale: true,
          opacity: 0.9,
          colorbar: { title: projection.metric_key, thickness: 10 },
        },
      })
    }

    // Esfera-base opcional (só no modo sphere)
    if (mode === 'sphere') {
      const res = 16
      const sx = [], sy = [], sz = []
      for (let i = 0; i <= res; i++) {
        const theta = -Math.PI / 2 + (i / res) * Math.PI
        const rowX = [], rowY = [], rowZ = []
        for (let j = 0; j <= res; j++) {
          const phi = (j / res) * 2 * Math.PI
          rowX.push(Math.cos(theta) * Math.cos(phi))
          rowY.push(Math.cos(theta) * Math.sin(phi))
          rowZ.push(Math.sin(theta))
        }
        sx.push(rowX); sy.push(rowY); sz.push(rowZ)
      }
      t.unshift({
        type: 'surface',
        x: sx, y: sy, z: sz,
        showscale: false,
        opacity: 0.15,
        colorscale: [[0, '#1f2937'], [1, '#1f2937']],
        hoverinfo: 'skip',
        name: 'base',
      })
    }

    return t
  }, [projection, passes, filter, mode])

  const layout = {
    autosize: true,
    height: 600,
    paper_bgcolor: '#0d1117',
    plot_bgcolor: '#0d1117',
    font: { color: '#ccc' },
    margin: { l: 0, r: 0, t: 10, b: 0 },
    scene: {
      xaxis: { title: 'PC1', color: '#888', gridcolor: '#30363d' },
      yaxis: { title: 'PC2', color: '#888', gridcolor: '#30363d' },
      zaxis: { title: mode === 'sphere' ? 'altura (métrica)' : 'PC3', color: '#888', gridcolor: '#30363d' },
      aspectmode: 'cube',
      bgcolor: '#0d1117',
    },
    showlegend: false,
  }

  if (loadErr) {
    return <p className="errbox">Erro ao carregar Plotly: {loadErr}</p>
  }
  if (!Plot) {
    return <p className="muted small">Carregando gráfico 3D...</p>
  }
  return (
    <Plot
      data={traces}
      layout={layout}
      config={{ responsive: true, displaylogo: false }}
      style={{ width: '100%' }}
      useResizeHandler
    />
  )
}
