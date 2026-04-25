import { gradeMetric, deltaVs, higherIsBetter } from '../services/grading'

export function Kpi({ label, value, colored, format = 'num', digits = 2, gradeKey, baseline }) {
  const num = typeof value === 'number' ? value : parseFloat(value)
  let display = value
  if (!Number.isNaN(num) && Number.isFinite(num)) {
    if (format === 'pct') display = `${num.toFixed(digits)}%`
    else if (format === 'money') display = num.toLocaleString('pt-BR', {
      minimumFractionDigits: digits, maximumFractionDigits: digits,
    })
    else display = num.toFixed(digits)
  } else if (value === undefined || value === null) {
    display = '—'
  }

  let klass = 'value'
  if (colored && Number.isFinite(num)) {
    if (num > 0) klass += ' pos'
    else if (num < 0) klass += ' neg'
  }

  const grade = gradeKey && Number.isFinite(num) ? gradeMetric(gradeKey, num) : null
  const delta = gradeKey && Number.isFinite(num) && Number.isFinite(baseline)
    ? deltaVs(num, baseline, higherIsBetter(gradeKey))
    : null

  const style = grade && grade.grade !== 'neutral' ? {
    borderLeft: `4px solid ${grade.color}`,
    background: `linear-gradient(90deg, ${grade.color}22 0%, transparent 40%)`,
  } : undefined

  return (
    <div className="kpi" style={style} title={grade?.note || ''}>
      <div className="label">
        {label}
        {grade && grade.grade !== 'neutral' && (
          <span style={{
            marginLeft: 6, fontSize: 10, padding: '1px 6px', borderRadius: 8,
            background: grade.color, color: '#0d1117', fontWeight: 600,
          }}>{grade.grade}</span>
        )}
      </div>
      <div className={klass}>{display}</div>
      {delta && (
        <div style={{ fontSize: 11, color: delta.color, marginTop: 2 }}>
          {delta.arrow} {delta.pct.toFixed(1)}% vs base
        </div>
      )}
      {grade?.note && (
        <div className="small muted" style={{ marginTop: 4, lineHeight: 1.3 }}>
          {grade.note}
        </div>
      )}
    </div>
  )
}
