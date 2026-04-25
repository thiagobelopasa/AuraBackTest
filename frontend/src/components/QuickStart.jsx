import { useState } from 'react'
import './QuickStart.css'

export function QuickStart({ isOpen, onClose, onNavigate }) {
  const [expandedPhase, setExpandedPhase] = useState(0)

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
      id: 'analysis',
      title: '3. Backtest Individual',
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
    <div className={`quickstart-panel ${isOpen ? 'open' : ''}`}>
      <div className="quickstart-header">
        <h3>Começar</h3>
        <button className="quickstart-close" onClick={onClose}>✕</button>
      </div>

      <div className="quickstart-content">
        <div className="quickstart-intro">
          <p>Siga os 3 passos para completar sua análise:</p>
        </div>

        <div className="phases-list">
          {phases.map((phase, idx) => (
            <div key={phase.id} className="phase-card">
              <div
                className="phase-header"
                onClick={() => setExpandedPhase(expandedPhase === idx ? -1 : idx)}
                style={{ borderLeftColor: phase.color }}
              >
                <span className="phase-icon">{phase.icon}</span>
                <span className="phase-title">{phase.title}</span>
                <span className={`phase-toggle ${expandedPhase === idx ? 'open' : ''}`}>
                  ▼
                </span>
              </div>

              {expandedPhase === idx && (
                <div className="phase-body">
                  <div className="task-list">
                    {phase.tasks.map((task, tidx) => (
                      <div key={tidx} className="task-item">
                        <span className="task-check">□</span>
                        <span className="task-text">{task.text}</span>
                      </div>
                    ))}
                  </div>
                  <button
                    className="btn-phase-action"
                    style={{ backgroundColor: phase.color }}
                    onClick={() => {
                      onNavigate(phase.tab)
                      onClose()
                    }}
                  >
                    {phase.nextAction}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="quickstart-example">
          <h4>📌 Exemplo: Como Usar</h4>
          <div className="example-text">
            <ol>
              <li>Inicie uma otimização no MT5</li>
              <li>Vá para "Otimização ao vivo" e veja os passes sendo coletados</li>
              <li>Quando terminar, vá para "Análise de Otimização"</li>
              <li>Escolha o melhor resultado</li>
              <li>Rode-o individualmente em "Backtest Individual"</li>
              <li>Analise robustez, Monte Carlo, MAE/MFE</li>
              <li>Pronto! Seu sistema foi validado</li>
            </ol>
          </div>
        </div>

        <div className="quickstart-tips">
          <h4>💡 Dicas</h4>
          <ul>
            <li><strong>Não tem dados?</strong> Comece em "Backtest Aura" para carregar um relatório</li>
            <li><strong>Coleta em tempo real:</strong> Abre em "Otimização ao vivo" enquanto MT5 roda</li>
            <li><strong>Parado em uma fase?</strong> Clique no ℹ️ no canto superior direito para o guia completo</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
