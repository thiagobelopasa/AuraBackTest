import { useEffect, useState } from 'react'

export function TrialBanner() {
  const [info, setInfo] = useState(null)
  const [update, setUpdate] = useState(null)

  useEffect(() => {
    if (typeof window !== 'undefined' && window.aura) {
      window.aura.getInfo().then(setInfo).catch(() => {})
      const off = window.aura.onUpdateStatus(setUpdate)
      return off
    } else {
      setInfo({ version: 'dev' })
    }
  }, [])

  if (!info) return null

  const updateLabel = (() => {
    if (!update) return null
    if (update.state === 'downloading') return `Baixando atualização ${Math.round(update.percent || 0)}%`
    if (update.state === 'downloaded') return `Atualização ${update.version} pronta — reinicie`
    if (update.state === 'available') return `Nova versão ${update.version} disponível`
    return null
  })()

  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '4px 14px', fontSize: 11, gap: 12,
      background: '#3fb95022', borderBottom: '1px solid #3fb950', color: '#e6edf3',
    }}>
      <span>
        <span style={{
          display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
          background: '#3fb950', marginRight: 6, verticalAlign: 'middle',
        }} />
        AuraBackTest v{info.version} · <b>Licença ativa</b>
      </span>
      <span style={{ color: '#8b949e' }}>
        {updateLabel && <span style={{ color: '#58a6ff', marginRight: 12 }}>{updateLabel}</span>}
        {window.aura && (
          <>
            <a style={{ color: '#58a6ff', cursor: 'pointer', marginRight: 10 }}
              onClick={() => window.aura.checkUpdates()}>Checar atualização</a>
            <a style={{ color: '#8b949e', cursor: 'pointer' }}
              onClick={() => window.aura.openLogs()}>Logs</a>
          </>
        )}
      </span>
    </div>
  )
}
