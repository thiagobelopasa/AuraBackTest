import { useEffect, useState } from 'react'
import { listInstallations, listRunningMT5, listExperts, parseEA, errorMessage } from '../services/api'

/**
 * Seletor unificado: Instalação MT5 → EA disponível → parsear inputs.
 * Props:
 *   onSelection({ installation, expert, inputs })  — dispara quando muda
 *   initialInstallation (opcional)
 */
export function InstallationPicker({ onSelection }) {
  const [installations, setInstallations] = useState([])
  const [selInstall, setSelInstall] = useState(null)
  const [runningPids, setRunningPids] = useState(new Set())  // exes que estão rodando agora

  const [experts, setExperts] = useState([])
  const [selExpert, setSelExpert] = useState(null)
  const [filter, setFilter] = useState('')
  const [hideExamples, setHideExamples] = useState(true)

  const [inputs, setInputs] = useState([])
  const [parsing, setParsing] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    // Busca instalações + MT5s em execução em paralelo
    Promise.all([listInstallations(), listRunningMT5().catch(() => ({ running: [], active: null }))])
      .then(([installs, running]) => {
        setInstallations(installs)
        const runExes = new Set((running.running || []).map(r => r.terminal_exe))
        setRunningPids(runExes)

        // Prioriza: MT5 ativo (único rodando) > primeiro rodando > primeiro da lista
        if (running.active) {
          const match = installs.find(i => i.terminal_exe === running.active.terminal_exe)
          if (match) { setSelInstall(match); return }
        }
        const firstRunning = installs.find(i => runExes.has(i.terminal_exe))
        if (firstRunning) { setSelInstall(firstRunning); return }
        if (installs.length) setSelInstall(installs[0])
      })
      .catch(e => setError(`Falha ao detectar MT5: ${errorMessage(e)}`))
  }, [])

  useEffect(() => {
    setExperts([]); setSelExpert(null); setInputs([])
    if (!selInstall) return
    listExperts(selInstall.data_folder).then(list => {
      setExperts(list)
    }).catch(e => setError(`Falha ao listar EAs: ${errorMessage(e)}`))
  }, [selInstall])

  useEffect(() => {
    if (!selExpert) { setInputs([]); return }
    if (!selExpert.has_source) {
      // .ex5 sem fonte: não dá pra parsear inputs — user terá que digitar manual
      setInputs([])
      onSelection?.({ installation: selInstall, expert: selExpert, inputs: [] })
      return
    }
    setParsing(true); setError('')
    parseEA(selExpert.absolute_path)
      .then(r => {
        setInputs(r.inputs)
        onSelection?.({ installation: selInstall, expert: selExpert, inputs: r.inputs })
      })
      .catch(e => setError(`Erro parse EA: ${errorMessage(e)}`))
      .finally(() => setParsing(false))
  }, [selExpert])

  const filtered = experts.filter(e => {
    if (hideExamples && (/^Examples\//i.test(e.relative_path) || /^Advisors\//i.test(e.relative_path) || /^Free Robots\//i.test(e.relative_path))) return false
    if (filter && !e.relative_path.toLowerCase().includes(filter.toLowerCase())) return false
    return true
  })

  return (
    <div>
      <div className="row">
        <div style={{ flex: 2 }}>
          <label>
            Instalação MT5 detectada
            {selInstall && runningPids.has(selInstall.terminal_exe) && (
              <span style={{
                marginLeft: 8, color: 'var(--green)',
                fontSize: 10, textTransform: 'none', letterSpacing: 0,
              }}>● rodando agora</span>
            )}
          </label>
          <select
            value={selInstall?.terminal_exe || ''}
            onChange={e => setSelInstall(installations.find(i => i.terminal_exe === e.target.value))}
          >
            {installations.length === 0 && <option value="">nenhuma encontrada</option>}
            {installations.map(i => (
              <option key={i.terminal_exe} value={i.terminal_exe}>
                {runningPids.has(i.terminal_exe) ? '● ' : ''}{i.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {selInstall && (
        <div className="row" style={{ marginTop: 10 }}>
          <div style={{ flex: 3 }}>
            <label>Expert Advisor ({experts.length} encontrados)</label>
            <select
              value={selExpert?.absolute_path || ''}
              onChange={e => setSelExpert(experts.find(x => x.absolute_path === e.target.value))}
            >
              <option value="">-- selecione um EA --</option>
              {filtered.map(e => (
                <option key={e.absolute_path} value={e.absolute_path}>
                  {e.relative_path}  ({e.extension}{e.has_source ? '' : ', sem fonte'})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Filtrar</label>
            <input value={filter} onChange={e => setFilter(e.target.value)} placeholder="nome do robô..." />
          </div>
          <div className="fit" style={{ display: 'flex', alignItems: 'center', gap: 6, paddingBottom: 6 }}>
            <input type="checkbox" style={{ width: 'auto' }} checked={hideExamples} onChange={e => setHideExamples(e.target.checked)} />
            <span className="small muted">Esconder exemplos</span>
          </div>
        </div>
      )}

      {parsing && <p className="muted small">Parseando inputs do EA...</p>}
      {error && <div className="errbox">{error}</div>}
      {selExpert && !selExpert.has_source && (
        <div className="errbox" style={{ background: 'rgba(210,153,34,0.08)', borderColor: 'rgba(210,153,34,0.3)', color: '#f0d27a' }}>
          EA compilado (.ex5) sem código-fonte — inputs não podem ser detectados automaticamente.
          Você ainda pode otimizá-lo, mas vai precisar informar os nomes/defaults dos parâmetros manualmente.
        </div>
      )}
    </div>
  )
}
