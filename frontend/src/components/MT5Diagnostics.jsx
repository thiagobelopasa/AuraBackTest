import { useState, useEffect } from 'react'
import { api } from '../services/api'

export function MT5Diagnostics({ onClose }) {
  const [checks, setChecks] = useState({
    installations: { loading: true, data: null, error: null },
    running: { loading: true, data: null, error: null },
    backend: { loading: true, data: null, error: null },
  })

  useEffect(() => {
    const runChecks = async () => {
      try {
        // Check backend health
        try {
          const health = await api.get('/health')
          setChecks(c => ({
            ...c,
            backend: { loading: false, data: health.data, error: null }
          }))
        } catch (e) {
          setChecks(c => ({
            ...c,
            backend: { loading: false, data: null, error: 'Backend offline' }
          }))
          return // Exit early if backend is offline
        }

        // Check installations
        try {
          const inst = await api.get('/mt5/installations')
          setChecks(c => ({
            ...c,
            installations: { loading: false, data: inst.data, error: null }
          }))
        } catch (e) {
          setChecks(c => ({
            ...c,
            installations: { loading: false, data: null, error: e.message }
          }))
        }

        // Check running MT5
        try {
          const running = await api.get('/mt5/running')
          setChecks(c => ({
            ...c,
            running: { loading: false, data: running.data, error: null }
          }))
        } catch (e) {
          setChecks(c => ({
            ...c,
            running: { loading: false, data: null, error: e.message }
          }))
        }
      } catch (e) {
        console.error('Diagnostics error:', e)
      }
    }

    runChecks()
  }, [])

  const statusIcon = (check) => {
    if (check.loading) return '⏳'
    if (check.error) return '❌'
    if (check.data) return '✅'
    return '❓'
  }

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0,0,0,0.7)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 10001,
    }}>
      <div style={{
        background: 'var(--panel)',
        border: '1px solid var(--border)',
        borderRadius: 16,
        maxWidth: 600,
        maxHeight: '85vh',
        overflow: 'auto',
        padding: 28,
        boxShadow: '0 20px 60px rgba(0,0,0,0.4)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>Diagnóstico MT5</h2>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--muted)',
              fontSize: 24,
              cursor: 'pointer',
              padding: 0,
            }}
          >
            ✕
          </button>
        </div>

        {/* Backend Status */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <span style={{ fontSize: 20 }}>{statusIcon(checks.backend)}</span>
            <span style={{ fontWeight: 600, color: 'var(--text)' }}>Backend</span>
          </div>
          {checks.backend.loading && <p className="muted small">Verificando…</p>}
          {checks.backend.error && <p className="errbox">{checks.backend.error}</p>}
          {checks.backend.data && (
            <div className="okbox">
              Backend respondendo: <code>{JSON.stringify(checks.backend.data)}</code>
            </div>
          )}
        </div>

        {/* Installations */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <span style={{ fontSize: 20 }}>{statusIcon(checks.installations)}</span>
            <span style={{ fontWeight: 600, color: 'var(--text)' }}>Instalações MT5 Detectadas</span>
          </div>
          {checks.installations.loading && <p className="muted small">Verificando…</p>}
          {checks.installations.error && (
            <div className="errbox">{checks.installations.error}</div>
          )}
          {checks.installations.data && checks.installations.data.length > 0 ? (
            <div style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: 1.6 }}>
              {checks.installations.data.map((inst, idx) => (
                <div key={idx} style={{ marginBottom: 12, padding: 10, background: 'var(--panel-2)', borderRadius: 6, border: '1px solid var(--border)' }}>
                  <div><b>{inst.label}</b></div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'monospace', marginTop: 4 }}>
                    {inst.terminal_exe}
                  </div>
                </div>
              ))}
            </div>
          ) : !checks.installations.error && (
            <div className="errbox">
              <b>Nenhuma instalação detectada!</b>
              <p style={{ margin: '8px 0 0 0', fontSize: 12 }}>
                Verifique se MT5 está instalado em <code>C:\Program Files\</code> ou similar.
              </p>
            </div>
          )}
        </div>

        {/* Running MT5 */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <span style={{ fontSize: 20 }}>{statusIcon(checks.running)}</span>
            <span style={{ fontWeight: 600, color: 'var(--text)' }}>MT5 em Execução</span>
          </div>
          {checks.running.loading && <p className="muted small">Verificando…</p>}
          {checks.running.error && <p className="errbox">{checks.running.error}</p>}
          {checks.running.data && (
            <>
              {checks.running.data.running.length > 0 ? (
                <div className="okbox">
                  <b>{checks.running.data.running.length} processo(s) MT5 rodando</b>
                </div>
              ) : (
                <div style={{ padding: 10, background: 'rgba(212,175,95,0.08)', border: '1px solid rgba(212,175,95,0.2)', borderRadius: 6, fontSize: 12 }}>
                  <b>Nenhum MT5 em execução.</b> Abra o MetaTrader 5 para habilitar a coleta ao vivo.
                </div>
              )}
            </>
          )}
        </div>

        {/* Troubleshooting */}
        <div style={{
          padding: 12,
          background: 'rgba(212,175,95,0.08)',
          border: '1px solid rgba(212,175,95,0.2)',
          borderRadius: 8,
          fontSize: 12,
          color: 'var(--text-2)',
          lineHeight: 1.6,
        }}>
          <b style={{ color: 'var(--gold)' }}>💡 Dicas de Resolução:</b>
          <ul style={{ margin: '8px 0 0 0', paddingLeft: 20 }}>
            <li><b>MT5 não detectado?</b> Reinstale MT5 em <code>C:\Program Files\MetaTrader 5\</code></li>
            <li><b>Backend offline?</b> Reinicie o servidor Python em <code>backend/</code></li>
            <li><b>Porta bloqueada?</b> Verifique se outra instância está rodando</li>
            <li><b>Coleta não funciona?</b> Certifique-se de ter <code>AuraBackTestCollector.mqh</code> no seu EA</li>
          </ul>
        </div>

        <div style={{ marginTop: 20, textAlign: 'center' }}>
          <button onClick={onClose} style={{
            padding: '8px 16px',
            background: 'var(--gold)',
            color: '#1A1208',
            border: 'none',
            borderRadius: 6,
            fontWeight: 600,
            fontSize: 12,
            cursor: 'pointer',
          }}>
            Fechar
          </button>
        </div>
      </div>
    </div>
  )
}
