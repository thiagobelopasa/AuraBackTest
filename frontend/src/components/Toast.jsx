import { createContext, useCallback, useContext, useState } from 'react'

const ToastContext = createContext(null)

let idCounter = 0

/**
 * Sistema global de toasts. Uso:
 *   const { toast } = useToast()
 *   toast.success('Ação concluída')
 *   toast.error('Falha', 'Detalhe opcional')
 *   toast.info('Baixando…', null, { duration: 10000 })
 *   toast.gold('Backtest completo', 'Seu top 10 está pronto')
 */
export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const dismiss = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const push = useCallback((kind, title, message = null, opts = {}) => {
    const id = ++idCounter
    const duration = opts.duration ?? (kind === 'error' ? 8000 : 4500)
    setToasts(prev => [...prev, { id, kind, title, message }])
    if (duration > 0) {
      setTimeout(() => dismiss(id), duration)
    }
    return id
  }, [dismiss])

  const api = {
    success: (title, message, opts) => push('success', title, message, opts),
    error: (title, message, opts) => push('error', title, message, opts),
    info: (title, message, opts) => push('info', title, message, opts),
    gold: (title, message, opts) => push('gold', title, message, opts),
    dismiss,
  }

  return (
    <ToastContext.Provider value={{ toast: api }}>
      {children}
      <div className="toast-container">
        {toasts.map(t => (
          <div key={t.id} className={`toast ${t.kind}`}>
            <div className="toast-body">
              <div className="toast-title">{t.title}</div>
              {t.message && <div className="toast-message">{t.message}</div>}
            </div>
            <button className="toast-close" onClick={() => dismiss(t.id)}>×</button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast deve ser usado dentro de <ToastProvider>')
  return ctx
}
