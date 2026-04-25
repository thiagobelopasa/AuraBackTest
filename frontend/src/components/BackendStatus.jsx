import { useEffect, useState, useCallback } from 'react'
import { api } from '../services/api'

/**
 * Indicador de saúde do backend. Pinga /health via HTTP (funciona em dev-web
 * e em Electron). Em Electron, oferece botão de reiniciar o serviço Python.
 */
export function BackendStatus() {
  const [state, setState] = useState({ ok: null, info: '', restarting: false })

  const check = useCallback(async () => {
    try {
      const r = await api.get('/health', { timeout: 3000 })
      setState(s => ({ ...s, ok: r.status === 200, info: '' }))
    } catch (e) {
      setState(s => ({
        ...s,
        ok: false,
        info: e?.code || e?.message || 'sem resposta',
      }))
    }
  }, [])

  useEffect(() => {
    check()
    const id = setInterval(check, 10000)
    return () => clearInterval(id)
  }, [check])

  const restart = async () => {
    if (!window.aura?.restartBackend) return
    setState(s => ({ ...s, restarting: true }))
    try {
      const r = await window.aura.restartBackend()
      if (r.ok) {
        await check()
      } else {
        setState(s => ({ ...s, ok: false, info: `restart falhou: ${r.error}` }))
      }
    } finally {
      setState(s => ({ ...s, restarting: false }))
    }
  }

  const dotColor =
    state.ok === null ? '#8b949e' : state.ok ? '#3fb950' : '#f85149'
  const title = state.ok === null
    ? 'Verificando backend…'
    : state.ok
      ? 'Backend respondendo'
      : `Backend indisponível (${state.info})`

  return (
    <div
      title={title}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        fontSize: 12,
        color: 'var(--muted)',
      }}
    >
      <span
        style={{
          width: 9,
          height: 9,
          borderRadius: '50%',
          background: dotColor,
          boxShadow: state.ok ? `0 0 8px ${dotColor}` : 'none',
          transition: 'background 200ms, box-shadow 200ms',
        }}
      />
      <span>
        {state.ok === null ? '…' : state.ok ? 'online' : 'offline'}
      </span>
      {state.ok === false && window.aura?.restartBackend && (
        <button
          onClick={restart}
          disabled={state.restarting}
          style={{ padding: '3px 8px', fontSize: 11 }}
        >
          {state.restarting ? 'reiniciando…' : 'reiniciar'}
        </button>
      )}
    </div>
  )
}
