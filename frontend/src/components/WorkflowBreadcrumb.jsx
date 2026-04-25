import './WorkflowBreadcrumb.css'

export function WorkflowBreadcrumb({ currentTab }) {
  const tabs = [
    { id: 'liveopt', label: '1. Otimização ao vivo', color: 'var(--gold)' },
    { id: 'triage', label: '2. Análise de Otimização', color: '#22c55e' },
    { id: 'analysis', label: '3. Backtest Individual', color: '#06b6d4' },
  ]

  return (
    <div className="workflow-breadcrumb">
      {tabs.map((tab, idx) => (
        <div key={tab.id}>
          <div
            className={`breadcrumb-step ${currentTab === tab.id ? 'active' : ''}`}
            style={{
              borderColor: currentTab === tab.id ? tab.color : 'var(--border)',
              backgroundColor: currentTab === tab.id ? `${tab.color}10` : 'transparent',
            }}
          >
            <span className="step-label" style={{ color: currentTab === tab.id ? tab.color : 'var(--muted)' }}>
              {tab.label}
            </span>
          </div>
          {idx < tabs.length - 1 && (
            <div className="breadcrumb-arrow">→</div>
          )}
        </div>
      ))}
    </div>
  )
}
