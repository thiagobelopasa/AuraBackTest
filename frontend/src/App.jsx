import { useEffect, useState } from 'react'
import './App.css'
import { HomePage } from './pages/HomePage'
import { BacktestPage } from './pages/BacktestPage'
import { AnalysisPage } from './pages/AnalysisPage'
import { HistoryPage } from './pages/HistoryPage'
import { TriagePage } from './pages/TriagePage'
import { LiveOptPage } from './pages/LiveOptPage'
import { PortfolioPage } from './pages/PortfolioPage'
import { WFAPage } from './pages/WFAPage'
import { ImportPage } from './pages/ImportPage'
import { LicenseActivationPage } from './pages/LicenseActivationPage'
import { TrialBanner } from './components/TrialBanner'
import { BackendStatus } from './components/BackendStatus'
import { UpdateBanner } from './components/UpdateBanner'
import { ToastProvider } from './components/Toast'
import { OnboardingGuide } from './components/OnboardingGuide'
import { WorkflowBreadcrumb } from './components/WorkflowBreadcrumb'
import { QuickStart } from './components/QuickStart'

// Abas permitidas em cada estado da licença.
// - ACTIVE: tudo
// - READONLY: só Histórico e Análise (visualização de runs antigos), sem novos imports/runs
// - BLOCKED: nenhuma (tela de ativação ocupa toda a janela)
const ALL_TABS = [
  { id: 'home', label: 'Começar' },
  { id: 'import', label: 'Importar CSV' },
  { id: 'liveopt', label: 'Otimização ao vivo' },
  { id: 'triage', label: 'Análise de Otimização' },
  { id: 'backtest', label: 'Backtest Aura' },
  { id: 'analysis', label: 'Backtest Individual' },
  { id: 'portfolio', label: 'Portfólio' },
  { id: 'wfa', label: 'Walk-Forward' },
  { id: 'history', label: 'Histórico' },
]

const READONLY_TABS = new Set(['home', 'analysis', 'history'])

function App() {
  const [tab, setTab] = useState('home')
  const [currentRunId, setCurrentRunId] = useState('')
  const [quickStartOpen, setQuickStartOpen] = useState(false)
  const [triagePreloadedData, setTriagePreloadedData] = useState(null)

  // Estado da licença: null = ainda carregando; { state, reason?, info? } depois
  const [license, setLicense] = useState(null)

  const refreshLicense = async () => {
    if (window.aura?.license) {
      try {
        const s = await window.aura.license.status()
        setLicense(s)
      } catch {
        setLicense({ state: 'READONLY', reason: 'unknown_error' })
      }
    } else {
      // Modo dev sem Electron — libera tudo
      setLicense({ state: 'ACTIVE', info: { product_title: 'AuraBackTest (dev)' } })
    }
  }

  useEffect(() => { refreshLicense() }, [])

  // Revalida a cada 10 minutos enquanto o app está aberto
  useEffect(() => {
    const id = setInterval(refreshLicense, 10 * 60 * 1000)
    return () => clearInterval(id)
  }, [])

  const handleActivated = () => {
    refreshLicense().then(() => setTab('home'))
  }

  const openRun = (id) => {
    setCurrentRunId(id)
    setTab('analysis')
  }

  const navigateToTriage = (data) => {
    setTriagePreloadedData(data)
    setTab('triage')
  }

  // Aguardando carregar
  if (!license) {
    return (
      <div style={{
        position: 'fixed', inset: 0, background: '#0d1117', color: '#8b949e',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      }}>
        Carregando…
      </div>
    )
  }

  // Bloqueado — tela de ativação ocupa tudo
  if (license.state === 'BLOCKED') {
    return (
      <LicenseActivationPage
        onActivated={handleActivated}
        initialReason={license.reason !== 'no_key' ? license.reason : null}
      />
    )
  }

  const isReadonly = license.state === 'READONLY'
  const visibleTabs = isReadonly
    ? ALL_TABS.filter(t => READONLY_TABS.has(t.id))
    : ALL_TABS

  // Se está em readonly e a aba ativa não é permitida, redireciona
  if (isReadonly && !READONLY_TABS.has(tab)) {
    setTab('history')
    return null
  }

  return (
    <ToastProvider>
    <div className="app">
      <TrialBanner license={license} onDeactivate={refreshLicense} />
      <UpdateBanner />
      <div className="topbar">
        <div className="brand">
          <div className="brand-logo">A</div>
          <div className="brand-text">
            <h1>Aura<span className="accent">BackTest</span></h1>
            <div className="subtitle">Otimização de automação para traders profissionais</div>
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
        {visibleTabs.map(t => (
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
        {tab === 'import' && <ImportPage onRunSaved={openRun} />}
        {tab === 'backtest' && <BacktestPage onRunSaved={openRun} />}
        {tab === 'analysis' && <AnalysisPage currentRunId={currentRunId} onRunIdChange={setCurrentRunId} />}
        {tab === 'liveopt' && <LiveOptPage onOpenRun={openRun} onNavigateToTriage={navigateToTriage} />}
        {tab === 'triage' && <TriagePage onOpenRun={openRun} preloadedData={triagePreloadedData} onClearPreload={() => setTriagePreloadedData(null)} />}
        {tab === 'portfolio' && <PortfolioPage />}
        {tab === 'wfa' && <WFAPage onOpenRun={openRun} />}
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
