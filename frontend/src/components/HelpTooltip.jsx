import { useState, useRef, useEffect } from 'react'
import { HELP } from '../services/helpContent'

/**
 * Botão "?" que mostra tooltip educativo ao passar o mouse / clicar.
 *
 * Props:
 *   helpKey  – chave em helpContent.HELP
 *   size     – 'sm' (default) | 'md'
 *   inline   – true = inline com o texto; false = absoluto (default false)
 */
export function HelpTooltip({ helpKey, size = 'sm', inline = false }) {
  const [open, setOpen] = useState(false)
  const [position, setPosition] = useState('bottom')  // 'top' ou 'bottom'
  const wrapperRef = useRef(null)
  const data = HELP[helpKey]

  // Decide se a tooltip vai pra cima ou pra baixo baseado em viewport
  useEffect(() => {
    if (!open || !wrapperRef.current) return
    const rect = wrapperRef.current.getBoundingClientRect()
    const tooltipH = 340  // estimativa
    const spaceBelow = window.innerHeight - rect.bottom
    setPosition(spaceBelow < tooltipH ? 'top' : 'bottom')
  }, [open])

  if (!data) return null

  const dim = size === 'md' ? 18 : 14
  const fontSize = size === 'md' ? 12 : 10

  return (
    <span
      ref={wrapperRef}
      style={{
        position: 'relative',
        display: inline ? 'inline-flex' : 'inline-block',
        alignItems: 'center',
        marginLeft: 6,
        verticalAlign: 'middle',
      }}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setOpen(o => !o) }}
        style={{
          width: dim,
          height: dim,
          padding: 0,
          borderRadius: '50%',
          background: 'transparent',
          border: '1px solid #6e7681',
          color: '#8b949e',
          fontSize,
          fontWeight: 700,
          cursor: 'help',
          lineHeight: 1,
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
        aria-label="Ajuda"
      >
        ?
      </button>

      {open && (
        <div
          style={{
            position: 'absolute',
            [position]: dim + 6,
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 1000,
            width: 320,
            background: '#0d1117',
            border: '1px solid #30363d',
            borderRadius: 8,
            padding: 12,
            boxShadow: '0 8px 24px rgba(0,0,0,0.6)',
            color: '#e6edf3',
            textAlign: 'left',
            fontSize: 12,
            lineHeight: 1.5,
            pointerEvents: 'none',
          }}
        >
          {/* Tradução */}
          <div style={{ fontSize: 11, color: '#8b949e', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 }}>
            Em linguagem simples
          </div>
          <div style={{ marginBottom: 10 }}>{data.plain}</div>

          {/* Faixas de valores */}
          {data.ranges?.length > 0 && (
            <>
              <div style={{ fontSize: 11, color: '#8b949e', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 }}>
                Faixas
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 3, marginBottom: 10 }}>
                {data.ranges.map((r, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: r.color, flexShrink: 0 }} />
                    <span style={{ color: r.color, fontWeight: 600, minWidth: 84, fontSize: 11 }}>{r.label}</span>
                    <span style={{ color: '#c9d1d9', fontSize: 11 }}>{r.range}</span>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Como melhorar */}
          {data.howToImprove && (
            <>
              <div style={{ fontSize: 11, color: '#3fb950', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 }}>
                💡 Como melhorar
              </div>
              <div style={{ marginBottom: 10, color: '#c9d1d9' }}>{data.howToImprove}</div>
            </>
          )}

          {/* Como não piorar */}
          {data.howToKeep && (
            <>
              <div style={{ fontSize: 11, color: '#d29922', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 }}>
                ⚠️ Como não piorar
              </div>
              <div style={{ marginBottom: data.formula ? 10 : 0, color: '#c9d1d9' }}>{data.howToKeep}</div>
            </>
          )}

          {/* Fórmula */}
          {data.formula && (
            <div style={{ fontSize: 11, color: '#6e7681', fontFamily: 'monospace', marginTop: 6, paddingTop: 6, borderTop: '1px solid #21262d' }}>
              {data.formula}
            </div>
          )}
        </div>
      )}
    </span>
  )
}
