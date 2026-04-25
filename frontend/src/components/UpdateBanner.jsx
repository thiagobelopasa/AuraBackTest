import { useEffect, useState } from 'react'

/**
 * Banner fixo que reage a eventos do electron-updater (main.js → preload.js).
 * Estados emitidos por main.js:
 *   { state: 'available', version }
 *   { state: 'downloading', percent, bps }
 *   { state: 'downloaded', version }
 *   { state: 'error', error }
 *   { state: 'none' }
 */
export function UpdateBanner() {
  const [status, setStatus] = useState(null)
  const [applying, setApplying] = useState(false)

  useEffect(() => {
    if (!window.aura?.onUpdateStatus) return
    return window.aura.onUpdateStatus(setStatus)
  }, [])

  if (!status || status.state === 'none') return null
  if (status.state === 'error') return null // silencia erros (já logados no arquivo)

  const apply = async () => {
    if (!window.aura?.applyUpdate) return
    setApplying(true)
    const r = await window.aura.applyUpdate()
    if (!r.ok) {
      alert(`Falha ao instalar atualização: ${r.error}`)
      setApplying(false)
    }
    // Se OK, app vai fechar e reabrir sozinho.
  }

  const colors = {
    available: { bg: '#1f6feb22', border: '#1f6feb', text: '#58a6ff' },
    downloading: { bg: '#1f6feb22', border: '#1f6feb', text: '#58a6ff' },
    downloaded: { bg: '#3fb95022', border: '#3fb950', text: '#3fb950' },
  }[status.state] || { bg: '#30363d', border: '#30363d', text: '#e6edf3' }

  return (
    <div
      style={{
        padding: '8px 18px',
        background: colors.bg,
        borderBottom: `1px solid ${colors.border}`,
        color: colors.text,
        fontSize: 13,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12,
      }}
    >
      <div>
        {status.state === 'available' && (
          <>Nova versão <b>{status.version}</b> disponível. Baixando…</>
        )}
        {status.state === 'downloading' && (
          <>Baixando atualização: <b>{Math.round(status.percent || 0)}%</b></>
        )}
        {status.state === 'downloaded' && (
          <>Atualização <b>{status.version}</b> pronta. Clique em Instalar para aplicar.</>
        )}
      </div>
      {status.state === 'downloaded' && (
        <button
          onClick={apply}
          disabled={applying}
          style={{
            background: colors.border,
            color: '#0d1117',
            border: 'none',
            padding: '6px 14px',
            borderRadius: 6,
            fontWeight: 600,
            cursor: applying ? 'default' : 'pointer',
          }}
        >
          {applying ? 'Instalando…' : 'Instalar agora'}
        </button>
      )}
    </div>
  )
}
