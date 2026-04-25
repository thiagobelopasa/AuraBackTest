import { useState } from 'react'
import { getStatValidation } from '../services/api'

function ScoreBanner({ passes, total, overall }) {
  const bg = overall === 'green' ? 'rgba(56,139,56,0.15)'
    : overall === 'yellow' ? 'rgba(210,153,34,0.15)'
    : 'rgba(248,81,73,0.15)'
  const border = overall === 'green' ? '#388b38'
    : overall === 'yellow' ? '#d29922' : '#f85149'
  const label = overall === 'green' ? 'APROVADO'
    : overall === 'yellow' ? 'ATENÇÃO' : 'REPROVADO'
  return (
    <div style={{ padding: '10px 14px', borderRadius: 8, background: bg, border: `1px solid ${border}`, marginBottom: 14 }}>
      <b style={{ fontSize: 15 }}>
        {overall === 'green' ? '🟢' : overall === 'yellow' ? '🟡' : '🔴'} {label}
        &nbsp;— {passes}/{total} validações Simons passaram
      </b>
    </div>
  )
}

const DESCRIPTIONS = {
  't-stat retornos ≥ 2.5': 'Renaissance: threshold interno estimado em t ≥ 2.5. Abaixo disso, o edge pode ser ruído estatístico.',
  'Sem autocorrelação (Ljung-Box)': 'Retornos com autocorrelação podem indicar look-ahead bias ou regime-dependência. p > 0.05 = independente.',
  'Sequência aleatória (Runs test)': 'Wins clusterizados em um período específico = estratégia regime-dependente. Wald-Wolfowitz test.',
  'Lucrativo sem top 5% trades': 'Se remover os 5 melhores trades mata o sistema, ele não é robusto. Princípio documentado de Simons.',
  'Tail ratio ≥ 1 (cauda direita ≥ esquerda)': 'P95/|P5| > 1 = caudas positivas maiores. Fundos sistemáticos buscam assimetria à direita.',
  'Assimetria positiva (Jarque-Bera)': 'Skewness > 0 = mais ganhos extremos que perdas extremas. Kurtosis alta = fat tails (risco).',
}

export function StatValidation({ runId }) {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState(null)

  const load = async () => {
    if (!runId) return
    setLoading(true); setError('')
    try {
      setResult(await getStatValidation(runId))
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally { setLoading(false) }
  }

  return (
    <div className="card">
      <h2>Validações Estatísticas (Simons-style)</h2>
      <p className="muted small" style={{ marginBottom: 10 }}>
        6 testes inspirados nas práticas da Renaissance Technologies: t-test, Ljung-Box,
        Runs test, Outlier dependency, Tail ratio, Jarque-Bera.
      </p>

      {!result && (
        <button disabled={loading || !runId} onClick={load}>
          {loading ? 'Calculando...' : 'Rodar validações'}
        </button>
      )}
      {error && <div className="errbox" style={{ marginTop: 8 }}>{error}</div>}

      {result && (
        <>
          <ScoreBanner passes={result.passes} total={result.total} overall={result.overall} />

          <table>
            <thead>
              <tr><th>Teste</th><th>Status</th><th>Valor</th><th></th></tr>
            </thead>
            <tbody>
              {result.scorecard.map((c, i) => (
                <>
                  <tr key={i} style={{ cursor: 'pointer' }} onClick={() => setExpanded(expanded === i ? null : i)}>
                    <td><b>{c.name}</b></td>
                    <td>
                      <span className={'pill ' + (c.status === 'pass' ? 'pos' : 'neg')}>
                        {c.status === 'pass' ? 'PASS' : 'FAIL'}
                      </span>
                    </td>
                    <td><code style={{ fontSize: 11 }}>{c.value}</code></td>
                    <td className="muted small">{expanded === i ? '▲' : '▼'}</td>
                  </tr>
                  {expanded === i && (
                    <tr key={`${i}-exp`}>
                      <td colSpan={4} style={{ paddingBottom: 10 }}>
                        <div className="muted small" style={{ padding: '6px 12px', background: 'rgba(255,255,255,0.03)', borderRadius: 4 }}>
                          {c.note}
                          {DESCRIPTIONS[c.name] && (
                            <div style={{ marginTop: 4, color: '#8b98a5' }}>{DESCRIPTIONS[c.name]}</div>
                          )}
                          {c.status === 'fail' && c.suggestion && (
                            <div style={{
                              marginTop: 8, padding: '8px 10px',
                              background: 'rgba(210,153,34,0.08)',
                              border: '1px solid rgba(210,153,34,0.3)',
                              borderRadius: 4, color: '#d6cda2',
                            }}>
                              <b style={{ color: '#d29922' }}>💡 Como melhorar:</b> {c.suggestion}
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>

          {result.outlier_dependency && (
            <div className="muted small" style={{ marginTop: 12 }}>
              {result.outlier_dependency.pct_from_outliers !== undefined && (
                <span>
                  Os top {result.outlier_dependency.removed} trades representam{' '}
                  <b>{(result.outlier_dependency.pct_from_outliers * 100).toFixed(0)}%</b> do lucro total.
                </span>
              )}
            </div>
          )}

          <button style={{ marginTop: 12, fontSize: 12 }} onClick={() => setResult(null)}>
            Recalcular
          </button>
        </>
      )}
    </div>
  )
}
