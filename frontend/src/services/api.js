import axios from 'axios'

// No Electron empacotado o backend sobe em 127.0.0.1:8765; dev-web bate no 8000 local.
const isElectron = typeof window !== 'undefined' && !!window.aura
const baseURL =
  import.meta.env.VITE_API_URL ||
  (isElectron ? 'http://127.0.0.1:8765' : 'http://localhost:8000')

// Sem Content-Type default: axios detecta automaticamente (JSON → application/json,
// FormData → multipart/form-data com boundary). Setar manualmente quebra uploads.
export const api = axios.create({
  baseURL,
  timeout: 6 * 3600 * 1000,
})

// Log detalhado de erros pra diagnosticar "Network Error" (CORS vs backend down vs timeout)
api.interceptors.response.use(
  (r) => r,
  (err) => {
    const cfg = err?.config || {}
    const url = `${cfg.baseURL || ''}${cfg.url || ''}`
    const info = {
      url,
      method: cfg.method,
      code: err?.code,
      message: err?.message,
      status: err?.response?.status,
      statusText: err?.response?.statusText,
    }
    // eslint-disable-next-line no-console
    console.error('[api] request failed', info)
    return Promise.reject(err)
  }
)

/** Extrai mensagem legível de qualquer erro axios/fastapi (inclusive 422). */
export function errorMessage(err) {
  const detail = err?.response?.data?.detail
  if (detail) {
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail.map(d => {
        const loc = Array.isArray(d.loc) ? d.loc.join('.') : d.loc
        return `${loc || 'erro'}: ${d.msg || JSON.stringify(d)}`
      }).join(' | ')
    }
    return JSON.stringify(detail)
  }
  // Sem resposta HTTP = não chegou no backend. Explicitar em vez de só "Network Error".
  if (err?.code === 'ERR_NETWORK' || err?.message === 'Network Error') {
    const url = `${err?.config?.baseURL || ''}${err?.config?.url || ''}`
    return `Sem resposta do backend em ${url}. Verifique se o serviço está rodando (menu Ajuda → Abrir logs).`
  }
  if (err?.code === 'ECONNABORTED') return 'Tempo esgotado aguardando resposta do backend.'
  return err?.message || String(err)
}

// --------------------------------------------------- MT5 / EA
export const listInstallations = () => api.get('/mt5/installations').then(r => r.data)

export const listRunningMT5 = () => api.get('/mt5/running').then(r => r.data)

export const listExperts = (dataFolder, includeCompiled = true) =>
  api.get('/mt5/experts', { params: { data_folder: dataFolder, include_compiled: includeCompiled } })
    .then(r => r.data)

export const parseEA = (eaPath) => api.post('/ea/parse', { path: eaPath }).then(r => r.data)

export const instrumentEA = (payload) =>
  api.post('/ea/instrument', payload).then(r => r.data)

export const inspectTicks = (csvPath) =>
  api.post('/ticks/inspect', { csv_path: csvPath }).then(r => r.data)

export const convertTicks = (payload) =>
  api.post('/ticks/convert', payload).then(r => r.data)

export const runSingle = (payload) =>
  api.post('/mt5/run-single', payload).then(r => r.data)

export const parseReport = (reportPath) =>
  api.post('/mt5/report/parse', { report_path: reportPath }).then(r => r.data)

// --------------------------------------------------- Analysis
export const ingestReport = (payload) =>
  api.post('/analysis/ingest', payload).then(r => r.data)

export const uploadReport = (file, { symbol, timeframe, deposit, label } = {}) => {
  const fd = new FormData()
  fd.append('file', file)
  if (symbol) fd.append('symbol', symbol)
  if (timeframe) fd.append('timeframe', timeframe)
  if (deposit !== undefined) fd.append('deposit', String(deposit))
  if (label) fd.append('label', label)
  // NÃO setar Content-Type manualmente: axios precisa gerar boundary sozinho
  return api.post('/analysis/ingest-upload', fd).then(r => r.data)
}

export const updateRunLabel = (runId, label) =>
  api.patch(`/analysis/runs/${runId}/label`, { label }).then(r => r.data)

export const setRunFavorite = (runId, favorite) =>
  api.patch(`/analysis/runs/${runId}/favorite`, { favorite }).then(r => r.data)

export const setSessionFavorite = (sessionId, favorite) =>
  api.patch(`/live-optimization/sessions/${sessionId}/favorite`, { favorite }).then(r => r.data)

export const analyze = (runId, initialEquity = 10000) =>
  api.post('/analysis/analyze', { run_id: runId, initial_equity: initialEquity })
    .then(r => r.data)

export const runMonteCarlo = (payload) =>
  api.post('/analysis/monte-carlo', payload).then(r => r.data)

export const runRobustnessSuite = (payload) =>
  api.post('/analysis/robustness-suite', payload).then(r => r.data)

export const splitWFA = (payload) =>
  api.post('/analysis/wfa/split', payload).then(r => r.data)

// --------------------------------------------------- Runs history
export const listRuns = (params = {}) =>
  api.get('/analysis/runs', { params }).then(r => r.data)

export const getRunDetail = (runId) =>
  api.get(`/analysis/runs/${runId}`).then(r => r.data)

export const getRunTrades = (runId) =>
  api.get(`/analysis/runs/${runId}/trades`).then(r => r.data)

export const deleteRun = (runId) =>
  api.delete(`/analysis/runs/${runId}`).then(r => r.data)

export const getTimeBreakdown = (runId) =>
  api.get(`/analysis/runs/${runId}/time-breakdown`).then(r => r.data)

export const runWhatIf = (runId, payload) =>
  api.post(`/analysis/runs/${runId}/whatif`, payload).then(r => r.data)

export const runMMSimulate = (runId, payload) =>
  api.post(`/analysis/runs/${runId}/mm-simulate`, payload).then(r => r.data)

export const runEquityControl = (runId, payload) =>
  api.post(`/analysis/runs/${runId}/equity-control`, payload).then(r => r.data)

export const getStatValidation = (runId) =>
  api.get(`/analysis/runs/${runId}/stat-validation`).then(r => r.data)

export const getMaeMfeTicks = (runId, parquetPath, bufferSeconds = 60) =>
  api.post(`/analysis/runs/${runId}/mae-mfe-ticks`, {
    parquet_path: parquetPath || undefined,
    buffer_seconds: bufferSeconds,
  }).then(r => r.data)

export const fetchRunTicks = (runId, terminalExe) =>
  api.post(`/analysis/runs/${runId}/fetch-ticks`, { terminal_exe: terminalExe })
    .then(r => r.data)

export const runTickMonteCarlo = (runId, payload) =>
  api.post(`/analysis/runs/${runId}/tick-monte-carlo`, payload).then(r => r.data)

// --------------------------------------------------- Optimization
export const runOptimization = (payload) =>
  api.post('/optimization/run', payload).then(r => r.data)

export const parseOptReport = (xmlPath, criterion = 'complex_criterion') =>
  api.post('/optimization/parse', { xml_path: xmlPath, criterion }).then(r => r.data)

export const listPasses = (runId) =>
  api.get(`/optimization/runs/${runId}/passes`).then(r => r.data)

// --------------------------------------------------- Triage
export const uploadTriageXML = (file, scoreKey = 'net_profit') => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post('/triage/upload-xml', fd, { params: { score_key: scoreKey } })
    .then(r => r.data)
}

export const project3D = (payload) =>
  api.post('/triage/project-3d', payload).then(r => r.data)

// --------------------------------------------------- Live optimization
export const startLiveOpt = (payload = {}) =>
  api.post('/live-optimization/start', payload).then(r => r.data)

export const stopLiveOpt = () =>
  api.post('/live-optimization/stop').then(r => r.data)

export const clearLiveOpt = () =>
  api.post('/live-optimization/clear').then(r => r.data)

export const liveOptSnapshot = () =>
  api.get('/live-optimization/snapshot').then(r => r.data)

export const listLiveSessions = (limit = 100) =>
  api.get('/live-optimization/sessions', { params: { limit } }).then(r => r.data)

export const getLiveSessionPasses = (sessionId) =>
  api.get(`/live-optimization/sessions/${sessionId}/passes`).then(r => r.data)

export const deleteLiveSession = (sessionId) =>
  api.delete(`/live-optimization/sessions/${sessionId}`).then(r => r.data)

export const openTopAsRuns = (sessionId, payload) =>
  api.post(`/live-optimization/sessions/${sessionId}/open-top`, payload).then(r => r.data)

export const sessionToTriage = (sessionId, scoreKey = 'sortino_ratio') =>
  api.post(`/live-optimization/sessions/${sessionId}/to-triage`, { score_key: scoreKey })
    .then(r => r.data)

export const sessionPBO = (sessionId, subsets = 16, minTrades = 20) =>
  api.post(`/live-optimization/sessions/${sessionId}/pbo`, {
    subsets, min_trades: minTrades,
  }).then(r => r.data)

export const autoFetchTicks = (payload) =>
  api.post('/ticks/auto-fetch', payload).then(r => r.data)

// Custom metric preview
export const evalCustomFormula = (sessionId, formula) =>
  api.post('/live-optimization/eval-formula', { session_id: sessionId, formula }).then(r => r.data)

// Multi-símbolo
export const runMultiSymbol = (payload) =>
  api.post('/mt5/multi-symbol', payload).then(r => r.data)

// Forward live vs backtest
export const forwardCompare = (payload) =>
  api.post('/analysis/forward-compare', payload).then(r => r.data)

// WFA automático ponta-a-ponta
export const wfaAutoStart = (payload) =>
  api.post('/analysis/wfa-auto/start', payload).then(r => r.data)

export const wfaAutoJob = (jobId) =>
  api.get(`/analysis/wfa-auto/job/${jobId}`).then(r => r.data)

export const wfaAutoJobs = () =>
  api.get('/analysis/wfa-auto/jobs').then(r => r.data)

/** Abre um WebSocket para o stream de passes. Retorna o WebSocket já conectado. */
export const openLiveOptStream = () => {
  const wsUrl = baseURL.replace(/^http/, 'ws') + '/live-optimization/ws'
  return new WebSocket(wsUrl)
}
