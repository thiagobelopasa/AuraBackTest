/**
 * Geração client-side de CSV. Sem dep externa: escape básico + BOM UTF-8 pra
 * Excel reconhecer acentos.
 */

function escapeCell(v) {
  if (v === null || v === undefined) return ''
  const s = typeof v === 'object' ? JSON.stringify(v) : String(v)
  if (/[",\n;]/.test(s)) return `"${s.replace(/"/g, '""')}"`
  return s
}

/**
 * Converte array de objetos em CSV.
 * Se `columns` não for passado, usa todas as chaves unificadas dos objetos.
 */
export function toCSV(rows, columns = null) {
  if (!rows || !rows.length) return ''
  const cols = columns || Array.from(rows.reduce((s, r) => {
    Object.keys(r).forEach(k => s.add(k))
    return s
  }, new Set()))
  const lines = [cols.join(',')]
  for (const r of rows) {
    lines.push(cols.map(c => escapeCell(r[c])).join(','))
  }
  return '﻿' + lines.join('\r\n')
}

/** Dispara download de um conteúdo textual como arquivo. */
export function downloadText(content, filename, mime = 'text/csv;charset=utf-8') {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 500)
}

/** Shortcut: converte rows em CSV e dispara download. */
export function downloadCSV(rows, filename, columns = null) {
  const csv = toCSV(rows, columns)
  downloadText(csv, filename)
}
