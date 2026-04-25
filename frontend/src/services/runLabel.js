/**
 * Formata identificação de um run pro usuário.
 *
 * Queremos sempre mostrar: nome (se houver) · ativo · timeframe · fingerprint.
 * O fingerprint (params_hash) diferencia configs quase iguais mesmo quando o
 * label, ativo e TF são idênticos — ex: dois testes do mesmo robô com TP
 * diferente.
 */

export function runLabel(run) {
  if (!run) return '—'
  const label = run.label?.trim()
  const sym = run.symbol || '—'
  const tf = run.timeframe || '—'
  const head = label || `Run ${run.id}`
  return `${head} · ${sym} · ${tf}`
}

export function runLabelShort(run) {
  if (!run) return '—'
  const label = run.label?.trim()
  const sym = run.symbol || '—'
  const tf = run.timeframe || '—'
  return label ? `${label} (${sym} ${tf})` : `${sym} ${tf} · ${run.id}`
}

export function runFingerprint(run) {
  return run?.params_hash ? `#${run.params_hash}` : ''
}

/** Usado em <select>: devolve um texto com tudo que ajuda o usuário a distinguir. */
export function runOptionText(run) {
  const parts = []
  if (run.label?.trim()) parts.push(run.label.trim())
  parts.push(run.symbol || '—')
  parts.push(run.timeframe || '—')
  if (run.params_hash) parts.push(`#${run.params_hash}`)
  parts.push(run.kind)
  if (run.from_date && run.to_date) parts.push(`${run.from_date}→${run.to_date}`)
  parts.push(run.id)
  return parts.join(' · ')
}
