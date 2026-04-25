import { useState } from 'react'
import { MT5Diagnostics } from '../components/MT5Diagnostics'

export function HomePage({ onNavigate }) {
  const [expandedPhase, setExpandedPhase] = useState(0)
  const [showDiagnostics, setShowDiagnostics] = useState(false)

  const phases = [
    {
      id: 'optimization',
      title: '1. Otimização ao vivo',
      icon: '⚙️',
      color: 'var(--gold)',
      tasks: [
        { text: 'Inicie a otimização no MT5', done: false },
        { text: 'Monitore passes em tempo real', done: false },
        { text: 'Identifique os melhores resultados', done: false }
      ],
      nextAction: 'Ir para Otimização ao vivo',
      tab: 'liveopt'
    },
    {
      id: 'triage',
      title: '2. Análise de Otimização',
      icon: '📊',
      color: '#22c55e',
      tasks: [
        { text: 'Veja as sugestões automáticas', done: false },
        { text: 'Analise os passes mais promissores', done: false },
        { text: 'Selecione o candidato a vencedor', done: false }
      ],
      nextAction: 'Ir para Triagem',
      tab: 'triage'
    },
    {
      id: 'backtest',
      title: '3. Backtest Aura',
      icon: '📈',
      color: '#f59e0b',
      tasks: [
        { text: 'Carregue um relatório MT5', done: false },
        { text: 'Deixe o sistema analisar', done: false },
        { text: 'Salve para análise posterior', done: false }
      ],
      nextAction: 'Ir para Backtest Aura',
      tab: 'backtest'
    },
    {
      id: 'analysis',
      title: '4. Backtest Individual',
      icon: '🔍',
      color: '#06b6d4',
      tasks: [
        { text: 'Execute robustez completa', done: false },
        { text: 'Valide com Monte Carlo', done: false },
        { text: 'Aprove ou descarte o sistema', done: false }
      ],
      nextAction: 'Ir para Análise',
      tab: 'analysis'
    }
  ]

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: '24px' }}>
      <div className="card" style={{ marginBottom: 24 }}>
        <h2 style={{ marginTop: 0 }}>Bem-vindo ao AuraBackTest</h2>
        <p className="muted">
          Siga os 4 passos abaixo para completar sua análise de trading.
          Cada etapa se baseia na anterior.
        </p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {phases.map((phase, idx) => (
          <div key={phase.id} style={{
            background: 'var(--panel)',
            border: '1px solid var(--border)',
            borderRadius: 12,
            overflow: 'hidden'
          }}>
            <div
              onClick={() => setExpandedPhase(expandedPhase === idx ? -1 : idx)}
              style={{
                padding: '16px 20px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                borderLeft: `4px solid ${phase.color}`,
                background: 'var(--panel-2)',
                transition: 'all 150ms'
              }}
            >
              <span style={{ fontSize: 20 }}>{phase.icon}</span>
              <span style={{ flex: 1, fontWeight: 600, color: 'var(--text)' }}>
                {phase.title}
              </span>
              <span style={{
                color: 'var(--muted)',
                transition: 'transform 200ms',
                transform: expandedPhase === idx ? 'rotateZ(180deg)' : 'rotateZ(0deg)'
              }}>
                ▼
              </span>
            </div>

            {expandedPhase === idx && (
              <div style={{ padding: '16px 20px', borderTop: '1px solid var(--border)' }}>
                <div style={{ marginBottom: 16 }}>
                  {phase.tasks.map((task, tidx) => (
                    <div key={tidx} style={{
                      display: 'flex',
                      gap: 8,
                      padding: '8px 0',
                      fontSize: 13,
                      color: 'var(--text-2)',
                      lineHeight: 1.5
                    }}>
                      <span style={{ color: 'var(--muted)', flexShrink: 0, marginTop: 2 }}>→</span>
                      <span>{task.text}</span>
                    </div>
                  ))}
                </div>
                <button
                  onClick={() => onNavigate(phase.tab)}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    backgroundColor: phase.color,
                    color: '#1A1208',
                    border: 'none',
                    borderRadius: 8,
                    fontWeight: 600,
                    fontSize: 13,
                    cursor: 'pointer',
                    transition: 'all 150ms'
                  }}
                  onMouseEnter={(e) => e.target.style.opacity = '0.9'}
                  onMouseLeave={(e) => e.target.style.opacity = '1'}
                >
                  {phase.nextAction}
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="card" style={{ marginTop: 32 }}>
        <h3 style={{ color: 'var(--gold)', marginTop: 0 }}>📌 Fluxo Completo</h3>
        <ol style={{ fontSize: 13, lineHeight: 1.8, color: 'var(--text-2)' }}>
          <li>Inicie uma otimização no MT5 (Strategy Tester → Optimization)</li>
          <li>Vá para "Otimização ao vivo" e veja os passes sendo coletados em tempo real</li>
          <li>Quando terminar, vá para "Análise de Otimização"</li>
          <li>Escolha o melhor resultado baseado nas sugestões automáticas</li>
          <li>Rode-o individualmente em "Backtest Individual"</li>
          <li>Analise robustez: Monte Carlo, Walk-Forward, MAE/MFE, validações</li>
          <li>Pronto! Seu sistema foi validado com dados reais</li>
        </ol>
      </div>

      <div className="card" style={{ marginTop: 24, background: 'rgba(212,175,95,0.08)', border: '1px solid rgba(212,175,95,0.2)' }}>
        <h3 style={{ color: 'var(--gold)', marginTop: 0 }}>💡 Dicas Rápidas</h3>
        <ul style={{ fontSize: 13, lineHeight: 1.8, color: 'var(--text-2)', marginBottom: 0 }}>
          <li><strong>Não tem dados ainda?</strong> Comece em "Backtest Aura" para carregar um relatório MT5</li>
          <li><strong>MT5 offline?</strong> Verifique se o terminal64.exe está rodando e tente reconectar</li>
          <li><strong>Coleta em tempo real:</strong> Abre em "Otimização ao vivo" enquanto MT5 executa a otimização</li>
          <li><strong>Parado?</strong> Clique no ℹ️ no canto superior direito para o guia interativo</li>
        </ul>
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid rgba(212,175,95,0.3)' }}>
          <button
            onClick={() => setShowDiagnostics(true)}
            style={{
              padding: '8px 12px',
              background: 'rgba(212,175,95,0.2)',
              border: '1px solid rgba(212,175,95,0.4)',
              color: 'var(--gold)',
              borderRadius: 6,
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 150ms'
            }}
            onMouseEnter={(e) => e.target.style.background = 'rgba(212,175,95,0.3)'}
            onMouseLeave={(e) => e.target.style.background = 'rgba(212,175,95,0.2)'}
          >
            🔧 Diagnóstico MT5
          </button>
        </div>
      </div>

      {showDiagnostics && (
        <MT5Diagnostics onClose={() => setShowDiagnostics(false)} />
      )}
    </div>
  )
}
