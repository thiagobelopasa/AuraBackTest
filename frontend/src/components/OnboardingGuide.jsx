import { useState, useEffect } from 'react'
import './OnboardingGuide.css'

export function OnboardingGuide({ onPhaseChange, currentTab }) {
  const [isOpen, setIsOpen] = useState(false)
  const [currentPhase, setCurrentPhase] = useState(0)
  const [hasSeenBefore, setHasSeenBefore] = useState(false)

  useEffect(() => {
    const seen = localStorage.getItem('aura_onboarding_seen')
    setHasSeenBefore(!!seen)
  }, [])

  const phases = [
    {
      id: 'optimization',
      title: 'Fase 1: Otimização',
      description: 'Rode a otimização dos parâmetros no MT5',
      details: [
        'Use a aba "Otimização ao vivo" para monitorar passes em tempo real',
        'Veja qual combinação de parâmetros melhor performou',
        'Os dados são coletados automaticamente durante a otimização'
      ],
      action: 'Ir para Otimização ao vivo',
      tab: 'liveopt',
      color: 'var(--gold)'
    },
    {
      id: 'triage',
      title: 'Fase 2: Triagem Automática',
      description: 'Analise qual foi o ganhador',
      details: [
        'A aba "Análise de Otimização" mostra sugestões automáticas',
        'Veja quais passes passaram nos testes de robustez',
        'Selecione o melhor candidato para a próxima fase'
      ],
      action: 'Ir para Triagem',
      tab: 'triage',
      color: '#22c55e'
    },
    {
      id: 'analysis',
      title: 'Fase 3: Robustez Completa',
      description: 'Valide o ganhador com testes profundos',
      details: [
        'Use "Backtest Individual" para rodar o melhor resultado isoladamente',
        'Veja os testes de robustez: Monte Carlo, Walk-Forward, Validações',
        'Verifique MAE/MFE, distribuição de trades, stagnação'
      ],
      action: 'Ir para Backtest Individual',
      tab: 'analysis',
      color: '#06b6d4'
    }
  ]

  const handlePhaseClick = (phaseIndex) => {
    setCurrentPhase(phaseIndex)
  }

  const handleActionClick = () => {
    onPhaseChange(phases[currentPhase].tab)
    setIsOpen(false)
  }

  const handleCompleteOnboarding = () => {
    localStorage.setItem('aura_onboarding_seen', 'true')
    setHasSeenBefore(true)
    setIsOpen(false)
  }

  const phase = phases[currentPhase]

  return (
    <>
      <button
        className="onboarding-toggle"
        onClick={() => setIsOpen(!isOpen)}
        title="Guia de boas-vindas"
      >
        ℹ️
      </button>

      {isOpen && (
        <div className="onboarding-modal-overlay" onClick={() => setIsOpen(false)}>
          <div className="onboarding-modal" onClick={e => e.stopPropagation()}>
            <div className="onboarding-header">
              <h2>Bem-vindo ao AuraBackTest</h2>
              <button
                className="onboarding-close"
                onClick={() => setIsOpen(false)}
              >
                ✕
              </button>
            </div>

            <div className="onboarding-content">
              {/* Phase indicator */}
              <div className="phase-indicator">
                {phases.map((p, idx) => (
                  <div
                    key={p.id}
                    className={`phase-dot ${idx === currentPhase ? 'active' : ''} ${idx < currentPhase ? 'completed' : ''}`}
                    onClick={() => handlePhaseClick(idx)}
                    style={{
                      backgroundColor: idx <= currentPhase ? phase.color : 'var(--border)',
                    }}
                  >
                    {idx < currentPhase ? '✓' : idx + 1}
                  </div>
                ))}
              </div>

              {/* Current phase content */}
              <div className="phase-content">
                <h3 style={{ color: phase.color }}>{phase.title}</h3>
                <p className="phase-description">{phase.description}</p>

                <div className="phase-details">
                  {phase.details.map((detail, idx) => (
                    <div key={idx} className="detail-item">
                      <span className="detail-bullet" style={{ color: phase.color }}>
                        →
                      </span>
                      <span>{detail}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Action buttons */}
              <div className="onboarding-actions">
                <button
                  className="btn-secondary"
                  onClick={() => handlePhaseClick(Math.max(0, currentPhase - 1))}
                  disabled={currentPhase === 0}
                >
                  ← Anterior
                </button>

                <button
                  className="btn-primary"
                  onClick={handleActionClick}
                  style={{ backgroundColor: phase.color }}
                >
                  {phase.action}
                </button>

                <button
                  className="btn-secondary"
                  onClick={() => handlePhaseClick(Math.min(phases.length - 1, currentPhase + 1))}
                  disabled={currentPhase === phases.length - 1}
                >
                  Próximo →
                </button>
              </div>

              {currentPhase === phases.length - 1 && !hasSeenBefore && (
                <button
                  className="btn-done"
                  onClick={handleCompleteOnboarding}
                >
                  Entendi, não mostrar mais
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
