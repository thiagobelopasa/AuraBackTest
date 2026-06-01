import { useEffect, useState } from 'react'

const REASON_MESSAGES = {
  license_not_found: 'Chave não encontrada. Verifique se digitou corretamente.',
  license_revoked: 'Esta licença foi revogada. Entre em contato com o suporte.',
  license_expired: 'Esta licença está expirada. Renove no Marketplace Aura.',
  wrong_product: 'Esta chave é de outro produto. Use uma chave do AuraBackTest.',
  network_error: 'Não foi possível conectar ao servidor de licenças. Verifique sua conexão.',
  timeout: 'Servidor de licenças não respondeu. Tente novamente em alguns segundos.',
  rate_limited: 'Muitas tentativas. Aguarde 1 minuto e tente novamente.',
  parse_error: 'Resposta inválida do servidor.',
  empty_key: 'Cole sua chave de licença.',
  invalid: 'Licença inválida.',
}

function reasonText(reason) {
  return REASON_MESSAGES[reason] || `Erro: ${reason}`
}

/**
 * Tela fullscreen de ativação de licença. Renderizada antes do app principal
 * quando o license:status retorna state=BLOCKED.
 */
export function LicenseActivationPage({ onActivated, initialReason }) {
  const [key, setKey] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(initialReason ? reasonText(initialReason) : '')

  const handleActivate = async () => {
    setError('')
    if (!key.trim()) { setError('Cole sua chave de licença.'); return }
    if (!window.aura?.license) { setError('Esta versão precisa rodar pelo instalador do AuraBackTest.'); return }
    setLoading(true)
    try {
      const res = await window.aura.license.activate(key.trim())
      if (res.ok) {
        onActivated?.(res.info)
      } else {
        setError(reasonText(res.reason))
      }
    } catch (e) {
      setError(`Erro inesperado: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !loading) handleActivate()
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: '#0d1117', color: '#e6edf3',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      zIndex: 9999,
    }}>
      <div style={{ width: 480, padding: 36 }}>
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{
            display: 'inline-block', width: 64, height: 64,
            background: 'linear-gradient(135deg, #3fb950 0%, #238636 100%)',
            borderRadius: 16, color: '#0d1117',
            fontWeight: 800, fontSize: 32, lineHeight: '64px',
            marginBottom: 16,
          }}>A</div>
          <h1 style={{ fontSize: 24, margin: '0 0 6px' }}>
            Aura<span style={{ color: '#3fb950' }}>BackTest</span>
          </h1>
          <p style={{ color: '#8b949e', fontSize: 13, margin: 0 }}>
            Ative sua licença para continuar
          </p>
        </div>

        <div style={{
          background: '#161b22', border: '1px solid #30363d',
          borderRadius: 10, padding: 22,
        }}>
          <label style={{ display: 'block', fontSize: 12, color: '#8b949e', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            Chave de licença
          </label>
          <input
            type="text"
            value={key}
            onChange={e => setKey(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            autoFocus
            spellCheck={false}
            style={{
              width: '100%', padding: '10px 14px',
              background: '#0d1117', border: '1px solid #30363d',
              borderRadius: 6, color: '#e6edf3', fontSize: 13,
              fontFamily: 'monospace', letterSpacing: 0.3,
              outline: 'none',
            }}
          />

          {error && (
            <div style={{
              marginTop: 10, padding: '8px 12px', borderRadius: 6,
              background: 'rgba(248,81,73,0.08)', border: '1px solid rgba(248,81,73,0.3)',
              color: '#f85149', fontSize: 12,
            }}>
              {error}
            </div>
          )}

          <button
            onClick={handleActivate}
            disabled={loading}
            style={{
              width: '100%', marginTop: 14, padding: '11px',
              background: loading ? '#21262d' : '#238636',
              border: '1px solid ' + (loading ? '#30363d' : '#3fb950'),
              color: '#fff', borderRadius: 6, fontSize: 14, fontWeight: 600,
              cursor: loading ? 'wait' : 'pointer', transition: 'opacity 0.15s',
            }}
          >
            {loading ? 'Validando…' : 'Ativar licença'}
          </button>

          <div style={{ textAlign: 'center', marginTop: 18, fontSize: 12, color: '#8b949e' }}>
            Ainda não tem uma chave?
            <br />
            <a
              href="https://marketplace.auraplatforms.net"
              onClick={(e) => {
                e.preventDefault()
                if (window.aura?.openExternal) {
                  window.aura.openExternal('https://marketplace.auraplatforms.net')
                } else {
                  window.open('https://marketplace.auraplatforms.net', '_blank')
                }
              }}
              style={{ color: '#58a6ff', textDecoration: 'none' }}
            >
              Compre em marketplace.auraplatforms.net →
            </a>
          </div>
        </div>

        <div style={{ marginTop: 22, fontSize: 11, color: '#484f58', textAlign: 'center', lineHeight: 1.7 }}>
          Já comprou? Acesse <b>marketplace.auraplatforms.net</b> → Minha Conta → Compras
          <br />para encontrar sua chave.
        </div>
      </div>
    </div>
  )
}
