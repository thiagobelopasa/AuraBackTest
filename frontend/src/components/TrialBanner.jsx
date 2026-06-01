import { useEffect, useState } from 'react'

function formatDate(iso) {
  if (!iso) return null
  try { return new Date(iso).toLocaleDateString('pt-BR') } catch { return iso }
}

function daysUntil(iso) {
  if (!iso) return null
  const ms = new Date(iso).getTime() - Date.now()
  return Math.ceil(ms / (1000 * 60 * 60 * 24))
}

const READONLY_MESSAGES = {
  expired: 'Sua licença expirou — modo somente leitura',
  license_expired: 'Sua licença expirou — modo somente leitura',
  license_revoked: 'Sua licença foi revogada — modo somente leitura',
  revoked: 'Sua licença foi revogada — modo somente leitura',
  offline_grace_expired: 'Sem conexão há mais de 30 dias — modo somente leitura',
  unknown_error: 'Erro ao validar licença — modo somente leitura',
}

/**
 * Banner superior — mostra estado real da licença.
 * Props (passadas pelo App):
 *   license      – { state, reason?, info?, offline? }
 *   onDeactivate – callback após remover a licença
 */
export function TrialBanner({ license, onDeactivate }) {
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

  if (!info || !license) return null

  const updateLabel = (() => {
    if (!update) return null
    if (update.state === 'downloading') return `Baixando atualização ${Math.round(update.percent || 0)}%`
    if (update.state === 'downloaded') return `Atualização ${update.version} pronta — reinicie`
    if (update.state === 'available') return `Nova versão ${update.version} disponível`
    return null
  })()

  const isActive = license.state === 'ACTIVE'
  const isReadonly = license.state === 'READONLY'

  // Cor do banner
  let bg = '#3fb950'  // verde
  let bgFill = '#3fb95022'
  if (isReadonly) {
    bg = '#f85149'
    bgFill = '#f8514922'
  }

  const productName = license.info?.product_title || 'AuraBackTest'
  const expiresIso = license.info?.expires_at
  const daysLeft = expiresIso ? daysUntil(expiresIso) : null
  const dateStr = formatDate(expiresIso)

  let statusText
  if (isActive) {
    if (!expiresIso) {
      statusText = `${productName} · Licença vitalícia ativa`
    } else if (daysLeft <= 7) {
      // Próximo da expiração — alerta sutil
      bg = '#d29922'
      bgFill = '#d2992222'
      statusText = `${productName} · Renova em ${daysLeft} dias (${dateStr})`
    } else {
      statusText = `${productName} · Válida até ${dateStr}`
    }
    if (license.offline) {
      statusText += ` · Offline há ${license.daysOffline}d`
    }
  } else if (isReadonly) {
    statusText = `${productName} · ${READONLY_MESSAGES[license.reason] || 'Modo somente leitura'}`
  } else {
    statusText = `${productName} · Estado desconhecido`
  }

  const handleDeactivate = async () => {
    if (!confirm('Desativar a licença remove a chave deste dispositivo. Você precisará reativar para usar o app. Continuar?')) return
    if (window.aura?.license) {
      await window.aura.license.deactivate()
      onDeactivate?.()
    }
  }

  const openMarketplace = () => {
    if (window.aura?.openExternal) {
      window.aura.openExternal('https://marketplace.auraplatforms.net')
    } else {
      window.open('https://marketplace.auraplatforms.net', '_blank')
    }
  }

  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '4px 14px', fontSize: 11, gap: 12,
      background: bgFill, borderBottom: `1px solid ${bg}`, color: '#e6edf3',
    }}>
      <span>
        <span style={{
          display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
          background: bg, marginRight: 6, verticalAlign: 'middle',
        }} />
        v{info.version} · <b>{statusText}</b>
      </span>
      <span style={{ color: '#8b949e', display: 'flex', gap: 12, alignItems: 'center' }}>
        {updateLabel && <span style={{ color: '#58a6ff' }}>{updateLabel}</span>}
        {isReadonly && (
          <a style={{ color: bg, cursor: 'pointer', fontWeight: 600 }}
            onClick={openMarketplace}>Renovar →</a>
        )}
        {window.aura && (
          <>
            <a style={{ color: '#58a6ff', cursor: 'pointer' }}
              onClick={() => window.aura.checkUpdates()}>Checar atualização</a>
            <a style={{ color: '#8b949e', cursor: 'pointer' }}
              onClick={() => window.aura.openLogs()}>Logs</a>
            {(isActive || isReadonly) && (
              <a style={{ color: '#8b949e', cursor: 'pointer' }}
                onClick={handleDeactivate}>Desativar licença</a>
            )}
          </>
        )}
      </span>
    </div>
  )
}
