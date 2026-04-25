import { useEffect, useState } from 'react'

const DEFAULT_TRIAL_END = '2026-05-30T23:59:59-03:00'

export function TrialBanner() {
  const [info, setInfo] = useState(null)
  const [update, setUpdate] = useState(null)

  useEffect(() => {
    if (typeof window !== 'undefined' && window.aura) {
      window.aura.getInfo().then(setInfo).catch(() => {})
      const off = window.aura.onUpdateStatus(setUpdate)
      return off
    } else {
      setInfo({ version: 'dev', trialEndIso: DEFAULT_TRIAL_END })
    }
  }, [])

  if (!info) return null

  const end = new Date(info.trialEndIso)
  const now = new Date()
  const daysLeft = Math.ceil((end.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
  const expired = daysLeft <= 0
  const warning = daysLeft <= 14

  const bg = expired ? '#f85149' : warning ? '#d29922' : '#3fb950'
  const txt = expired
    ? 'Período de avaliação encerrado'
    : `Uso gratuito até ${end.toLocaleDateString('pt-BR')} (${daysLeft} ${daysLeft === 1 ? 'dia' : 'dias'} restantes)`

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
      background: `${bg}22`, borderBottom: `1px solid ${bg}`, color: '#e6edf3',
    }}>
      <span>
        <span style={{
          display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
          background: bg, marginRight: 6, verticalAlign: 'middle',
        }} />
        AuraBackTest v{info.version} · <b>{txt}</b>
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
