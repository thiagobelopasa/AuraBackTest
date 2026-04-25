import { useState } from 'react'
import './App.css'
import { HomePage } from './pages/HomePage'
import { BacktestPage } from './pages/BacktestPage'
import { AnalysisPage } from './pages/AnalysisPage'
import { HistoryPage } from './pages/HistoryPage'
import { TriagePage } from './pages/TriagePage'
import { LiveOptPage } from './pages/LiveOptPage'
import { PortfolioPage } from './pages/PortfolioPage'
import { TrialBanner } from './components/TrialBanner'
import { BackendStatus } from './components/BackendStatus'
import { UpdateBanner } from './components/UpdateBanner'
import { ToastProvider } from './components/Toast'
import { OnboardingGuide } from './components/OnboardingGuide'
import { WorkflowBreadcrumb } from './components/WorkflowBreadcrumb'
import { QuickStart } from './components/QuickStart'

const TABS = [
  { id: 'home', label: 'Começar' },
  { id: 'liveopt', label: 'Otimização ao vivo' },
  { id: 'triage', label: 'Análise de Otimização' },
  { id: 'backtest', label: 'Backtest Aura' },
  { id: 'analysis', label: 'Backtest Individual' },
  { id: 'portfolio', label: 'Portfólio' },
  { id: 'history', label: 'Histórico' },
]

function App() {
  const [tab, setTab] = useState('home')
  const [currentRunId, setCurrentRunId] = useState('')
  const [quickStartOpen, setQuickStartOpen] = useState(false)

  const openRun = (id) => {
    setCurrentRunId(id)
    setTab('analysis')
  }

  return (
    <ToastProvider>
    <div className="app">
      <TrialBanner />
      <UpdateBanner />
      <div className="topbar">
        <div className="brand">
          <div className="brand-logo">A</div>
          <div className="brand-text">
            <h1>Aura<span className="accent">BackTest</span></h1>
            <div className="subtitle">Analytics para traders profissionais</div>
          </div>
        </div>
        <div className="topbar-right">
          <button
            className="quickstart-btn"
            onClick={() => setQuickStartOpen(!quickStartOpen)}
            title="Painel de início rápido"
          >
            📌
          </button>
          <OnboardingGuide onPhaseChange={setTab} currentTab={tab} />
          <BackendStatus />
        </div>
      </div>
      <div className="tabs">
        {TABS.map(t => (
          <button
            key={t.id}
            className={'tab' + (tab === t.id ? ' active' : '')}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="content">
        {(tab === 'liveopt' || tab === 'triage' || tab === 'analysis') && (
          <WorkflowBreadcrumb currentTab={tab} />
        )}
        {tab === 'home' && <HomePage onNavigate={setTab} />}
        {tab === 'backtest' && <BacktestPage onRunSaved={openRun} />}
        {tab === 'analysis' && <AnalysisPage currentRunId={currentRunId} onRunIdChange={setCurrentRunId} />}
        {tab === 'liveopt' && <LiveOptPage onOpenRun={openRun} />}
        {tab === 'triage' && <TriagePage onOpenRun={openRun} />}
        {tab === 'portfolio' && <PortfolioPage />}
        {tab === 'history' && <HistoryPage onOpenRun={openRun} />}
      </div>

      <QuickStart
        isOpen={quickStartOpen}
        onClose={() => setQuickStartOpen(false)}
        onNavigate={setTab}
      />
    </div>
    </ToastProvider>
  )
}

export default App
