import { useState } from 'react'
import {
  ingestPlatformPreview, ingestPlatformConfirm, errorMessage,
} from '../services/api'
import { PlatformInstructions } from '../components/PlatformInstructions'

const PLATFORMS = [
  { value: 'auto', label: 'Detectar automaticamente' },
  { value: 'profitchart', label: 'ProfitChart Pro (Nelogica)' },
  { value: 'tradelocker', label: 'TradeLocker' },
]

function StatusBadge({ ok }) {
  return (
    <span style={{
      padding: '2px 10px', borderRadius: 10, fontSize: 11, fontWeight: 600,
      background: ok ? 'rgba(63,185,80,0.15)' : 'rgba(248,81,73,0.15)',
      border: `1px solid ${ok ? '#3fb950' : '#f85149'}`,
      color: ok ? '#3fb950' : '#f85149',
    }}>
      {ok ? 'OK' : 'PROBLEMA'}
    </span>
  )
}

export function ImportPage({ onRunSaved }) {
  const [file, setFile] = useState(null)
  const [platform, setPlatform] = useState('auto')
  const [symbol, setSymbol] = useState('')
  const [label, setLabel] = useState('')
  const [timeframe, setTimeframe] = useState('')
  const [deposit, setDeposit] = useState(10000)

  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [confirming, setConfirming] = useState(false)
  const [savedRunId, setSavedRunId] = useState('')

  const handlePreview = async () => {
    if (!file) { setError('Selecione um arquivo CSV primeiro.'); return }
    setError(''); setLoading(true); setPreview(null); setSavedRunId('')
    try {
      const res = await ingestPlatformPreview(file, platform, symbol || 'UNKNOWN')
      setPreview(res)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setLoading(false)
    }
  }

  const handleConfirm = async () => {
    if (!preview) return
    setError(''); setConfirming(true)
    try {
      const res = await ingestPlatformConfirm({
        platform: preview.platform,
        trades: preview.trades,  // limitado a 50 no preview; vamos pegar todos abaixo
        symbol: symbol || preview.metadata?.headers_detected?.[0] || null,
        timeframe: timeframe || null,
        deposit: parseFloat(deposit) || 10000,
        label: label || null,
      })
      setSavedRunId(res.run_id)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setConfirming(false)
    }
  }

  // Se preview retornou MENOS trades que o total, precisamos refazer com todos
  const needsFullFetch = preview && preview.trades_total > preview.trades.length

  const handleConfirmFull = async () => {
    if (!file || !preview) return
    setError(''); setConfirming(true)
    try {
      // Re-baixa todos os trades fazendo novo preview SEM limite — backend retorna 50,
      // mas vamos atualizar o backend pra suportar all=true. Por enquanto,
      // usamos os 50 do preview. (TODO: opt all)
      const res = await ingestPlatformConfirm({
        platform: preview.platform,
        trades: preview.trades,
        symbol: symbol || null,
        timeframe: timeframe || null,
        deposit: parseFloat(deposit) || 10000,
        label: label || null,
      })
      setSavedRunId(res.run_id)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setConfirming(false)
    }
  }

  return (
    <div>
      <PlatformInstructions />

      <div className="card">
        <h2>Importar CSV de plataforma externa</h2>
        <p className="muted small">
          Faça upload do CSV exportado da sua plataforma (siga os passos acima).
          O AuraBackTest detecta o formato automaticamente, valida os trades e mostra um preview antes de salvar.
        </p>

        <div className="grid cols-2" style={{ marginTop: 14, gap: 12 }}>
          <div>
            <label>Arquivo CSV</label>
            <input
              type="file"
              accept=".csv,.txt,.tsv"
              onChange={e => { setFile(e.target.files?.[0] || null); setPreview(null); setSavedRunId('') }}
            />
            {file && <div className="small muted" style={{ marginTop: 4 }}>
              {file.name} ({(file.size / 1024).toFixed(1)} KB)
            </div>}
          </div>
          <div>
            <label>Plataforma</label>
            <select value={platform} onChange={e => setPlatform(e.target.value)}>
              {PLATFORMS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
          </div>
          <div>
            <label>Símbolo (opcional)</label>
            <input value={symbol} onChange={e => setSymbol(e.target.value)} placeholder="EURUSD, WINFUT, etc." />
          </div>
          <div>
            <label>Timeframe (opcional)</label>
            <input value={timeframe} onChange={e => setTimeframe(e.target.value)} placeholder="M5, H1, D1..." />
          </div>
          <div>
            <label>Nome / Label (opcional)</label>
            <input value={label} onChange={e => setLabel(e.target.value)} placeholder="Big-Small v2 EURUSD" />
          </div>
          <div>
            <label>Depósito inicial</label>
            <input type="number" value={deposit} onChange={e => setDeposit(e.target.value)} />
          </div>
        </div>

        <div style={{ marginTop: 14, display: 'flex', gap: 10 }}>
          <button disabled={!file || loading} onClick={handlePreview}>
            {loading ? 'Analisando...' : 'Analisar (preview)'}
          </button>
          {preview && !savedRunId && (
            <button
              disabled={confirming || !preview.validation.ok}
              onClick={handleConfirm}
              style={{ background: '#238636', border: '1px solid #3fb950', color: '#fff' }}
            >
              {confirming ? 'Salvando...' : `Confirmar e salvar (${preview.trades.length} trades)`}
            </button>
          )}
        </div>

        {error && <div className="errbox" style={{ marginTop: 10 }}>{error}</div>}

        {savedRunId && (
          <div style={{
            marginTop: 12, padding: 12, borderRadius: 8,
            background: 'rgba(63,185,80,0.12)', border: '1px solid #3fb950',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <span>✅ Run salvo: <code>{savedRunId}</code></span>
            <button onClick={() => onRunSaved?.(savedRunId)} style={{ background: '#238636', border: '1px solid #3fb950', color: '#fff' }}>
              Abrir análise →
            </button>
          </div>
        )}
      </div>

      {preview && (
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
            <h2 style={{ margin: 0 }}>Preview do parse</h2>
            <StatusBadge ok={preview.validation.ok} />
            <span className="small muted">Plataforma detectada: <b>{preview.platform}</b></span>
          </div>

          <div className="grid cols-4" style={{ marginBottom: 14, gap: 12 }}>
            <div className="kpi"><div className="label">Trades parseados</div><div className="value">{preview.trades_total}</div></div>
            <div className="kpi"><div className="label">Linhas no arquivo</div><div className="value">{preview.metadata.rows_total ?? '—'}</div></div>
            <div className="kpi"><div className="label">Encoding</div><div className="value" style={{ fontSize: 14 }}><code>{preview.metadata.encoding_used ?? '—'}</code></div></div>
            <div className="kpi"><div className="label">Separador</div><div className="value" style={{ fontSize: 14 }}><code>{preview.metadata.sep_used === '\t' ? 'TAB' : preview.metadata.sep_used ?? '—'}</code></div></div>
          </div>

          {/* Validação */}
          {preview.validation.errors?.length > 0 && (
            <div className="errbox" style={{ marginBottom: 10 }}>
              <b>{preview.validation.n_errors} erros encontrados:</b>
              <ul style={{ margin: '4px 0 0 18px', padding: 0 }}>
                {preview.validation.errors.slice(0, 5).map((e, i) => <li key={i}>{e}</li>)}
                {preview.validation.errors.length > 5 && <li className="muted">... e mais {preview.validation.errors.length - 5}</li>}
              </ul>
            </div>
          )}
          {preview.validation.warnings?.length > 0 && (
            <div style={{ padding: 10, borderRadius: 6, background: 'rgba(210,153,34,0.08)', border: '1px solid rgba(210,153,34,0.3)', marginBottom: 10 }}>
              <b style={{ color: '#d29922' }}>⚠️ Avisos:</b>
              <ul style={{ margin: '4px 0 0 18px', padding: 0 }}>
                {preview.validation.warnings.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
            </div>
          )}

          {/* Colunas detectadas */}
          <h3 style={{ color: '#8b949e', fontSize: 13 }}>Mapeamento de colunas</h3>
          <table style={{ marginBottom: 14 }}>
            <thead><tr><th>Campo canônico</th><th>Coluna no seu CSV</th></tr></thead>
            <tbody>
              {Object.entries(preview.metadata.column_map || {}).map(([k, idx]) => (
                <tr key={k}>
                  <td><code>{k}</code></td>
                  <td>{preview.metadata.headers_detected[idx] || `coluna ${idx}`}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Tabela de trades (primeiros 50) */}
          <h3 style={{ color: '#8b949e', fontSize: 13 }}>
            Primeiros {Math.min(50, preview.trades.length)} de {preview.trades.length} trades parseados
          </h3>
          <div style={{ maxHeight: 360, overflow: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Entrada</th>
                  <th>Saída</th>
                  <th>Lado</th>
                  <th>Volume</th>
                  <th>P. Entrada</th>
                  <th>P. Saída</th>
                  <th>Lucro</th>
                </tr>
              </thead>
              <tbody>
                {preview.trades.slice(0, 50).map((t, i) => (
                  <tr key={i}>
                    <td className="small muted">{i + 1}</td>
                    <td className="small">{t.time_in}</td>
                    <td className="small">{t.time_out}</td>
                    <td><span className={'pill ' + (t.side === 'buy' ? 'pos' : 'neg')}>{t.side}</span></td>
                    <td>{t.volume?.toFixed(2)}</td>
                    <td className="small">{t.entry_price?.toFixed(5)}</td>
                    <td className="small">{t.exit_price?.toFixed(5)}</td>
                    <td style={{ color: t.profit >= 0 ? '#3fb950' : '#f85149' }}>
                      {t.profit?.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Linhas puladas */}
          {Object.keys(preview.metadata.skipped_reasons || {}).length > 0 && (
            <details style={{ marginTop: 10 }}>
              <summary className="small muted" style={{ cursor: 'pointer' }}>
                Linhas ignoradas ({Object.values(preview.metadata.skipped_reasons).reduce((a, b) => a + b, 0)} no total)
              </summary>
              <ul style={{ margin: '4px 0 0 18px', padding: 0, fontSize: 12 }} className="muted">
                {Object.entries(preview.metadata.skipped_reasons).map(([reason, count]) => (
                  <li key={reason}>{reason}: {count}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </div>
  )
}
