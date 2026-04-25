/**
 * Classificação de métricas de performance com base em literatura quant
 * amplamente citada (Van Tharp, Bailey/López de Prado, QuantAnalyzer defaults).
 *
 * Retorna { grade, color, note } onde grade ∈
 * 'excellent' | 'good' | 'acceptable' | 'poor' | 'bad'
 *
 * Notas são curtas e cite-able. Todas dizem de onde veio o threshold.
 */

const COLORS = {
  excellent: '#3fb950', // verde forte
  good: '#7cc974',      // verde claro
  acceptable: '#d29922', // amarelo
  poor: '#e88b43',      // laranja
  bad: '#f85149',       // vermelho
  neutral: '#8b949e',   // cinza
}

// Thresholds por métrica — ordem: (bad → excellent)
// higherIsBetter: true para métricas em que maior é melhor
const THRESHOLDS = {
  sharpe_ratio: {
    higherIsBetter: true,
    steps: [
      { max: 0, grade: 'bad', note: 'Sharpe ≤ 0 = sem edge (retorno não compensa risco).' },
      { max: 1, grade: 'poor', note: 'Sharpe < 1 é considerado fraco por fundos quant.' },
      { max: 2, grade: 'acceptable', note: 'Sharpe 1–2 é bom para estratégias retail (Van Tharp).' },
      { max: 3, grade: 'good', note: 'Sharpe 2–3 é muito bom; institucionais buscam 2+.' },
      { max: 5, grade: 'excellent', note: 'Sharpe > 3 excepcional. Acima de 5 suspeite de overfit / look-ahead.' },
      { max: Infinity, grade: 'excellent', note: 'Sharpe > 5 muito raro — revise o backtest com cuidado extremo.' },
    ],
  },
  sortino_ratio: {
    higherIsBetter: true,
    steps: [
      { max: 0, grade: 'bad', note: 'Sortino ≤ 0 = perdas dominam.' },
      { max: 1, grade: 'poor', note: 'Sortino < 1 é fraco.' },
      { max: 2, grade: 'acceptable', note: 'Sortino 1–2 é razoável.' },
      { max: 3, grade: 'good', note: 'Sortino 2–3 é bom (tipicamente 20–30% acima do Sharpe).' },
      { max: Infinity, grade: 'excellent', note: 'Sortino > 3 excelente.' },
    ],
  },
  profit_factor: {
    higherIsBetter: true,
    steps: [
      { max: 1, grade: 'bad', note: 'PF ≤ 1: perdas ≥ lucros (insustentável).' },
      { max: 1.3, grade: 'poor', note: 'PF 1–1.3: edge mínimo, custos reais podem zerar.' },
      { max: 1.75, grade: 'acceptable', note: 'PF 1.3–1.75: faixa típica de estratégias retail viáveis (QuantAnalyzer).' },
      { max: 2.5, grade: 'good', note: 'PF 1.75–2.5: consistente e lucrativo.' },
      { max: 4, grade: 'excellent', note: 'PF 2.5–4: excelente.' },
      { max: Infinity, grade: 'excellent', note: 'PF > 4: muito alto, checar overfit (Pardo).' },
    ],
  },
  win_rate: {
    // 0..1 ou 0..100 dependendo de onde vem; assumo 0..1 aqui
    higherIsBetter: null, // não é qualidade sozinho — depende do payoff
    steps: [
      { max: 0.3, grade: 'poor', note: 'WR < 30%: só funciona com payoff muito alto (>3×).' },
      { max: 0.5, grade: 'acceptable', note: 'WR 30–50%: típico de trend-following.' },
      { max: 0.7, grade: 'good', note: 'WR 50–70%: típico de mean-reversion.' },
      { max: 0.85, grade: 'good', note: 'WR 70–85%: checar se não está sendo "catch pennies in front of steamroller".' },
      { max: Infinity, grade: 'acceptable', note: 'WR > 85%: suspeito. Uma perda grande pode zerar meses de lucro.' },
    ],
  },
  max_drawdown_pct: {
    higherIsBetter: false,
    steps: [
      { max: 5, grade: 'excellent', note: 'DD < 5%: excepcional (raro em estratégias reais).' },
      { max: 10, grade: 'good', note: 'DD 5–10%: institutional-grade.' },
      { max: 20, grade: 'acceptable', note: 'DD 10–20%: aceitável para retail.' },
      { max: 35, grade: 'poor', note: 'DD 20–35%: emocionalmente difícil, muitos traders desistem aqui.' },
      { max: Infinity, grade: 'bad', note: 'DD > 35%: risco de ruína real. Compare com hedge funds macro (20–25%).' },
    ],
  },
  recovery_factor: {
    higherIsBetter: true,
    steps: [
      { max: 1, grade: 'bad', note: 'RF < 1: lucro não recupera o pior DD.' },
      { max: 2, grade: 'poor', note: 'RF 1–2: fraco.' },
      { max: 5, grade: 'acceptable', note: 'RF 2–5: aceitável.' },
      { max: 10, grade: 'good', note: 'RF 5–10: bom.' },
      { max: Infinity, grade: 'excellent', note: 'RF > 10: excelente (Van Tharp).' },
    ],
  },
  sqn: {
    // System Quality Number (Van Tharp)
    higherIsBetter: true,
    steps: [
      { max: 1.6, grade: 'bad', note: 'SQN < 1.6: sistema ruim (Van Tharp).' },
      { max: 1.9, grade: 'poor', note: 'SQN 1.6–1.9: abaixo da média.' },
      { max: 2.5, grade: 'acceptable', note: 'SQN 1.9–2.5: médio a bom.' },
      { max: 3.0, grade: 'good', note: 'SQN 2.5–3.0: excelente.' },
      { max: 5.0, grade: 'excellent', note: 'SQN 3.0–5.0: superb.' },
      { max: 7.0, grade: 'excellent', note: 'SQN 5.0–7.0: "holy grail" (Van Tharp).' },
      { max: Infinity, grade: 'acceptable', note: 'SQN > 7: provavelmente overfit. Refaça OOS.' },
    ],
  },
  k_ratio: {
    higherIsBetter: true,
    steps: [
      { max: 0, grade: 'bad', note: 'K-Ratio ≤ 0: retorno inconsistente.' },
      { max: 1, grade: 'poor', note: 'K-Ratio < 1: equity curve volátil.' },
      { max: 2, grade: 'acceptable', note: 'K-Ratio 1–2: linearidade razoável.' },
      { max: 3, grade: 'good', note: 'K-Ratio 2–3: equity bem linear.' },
      { max: Infinity, grade: 'excellent', note: 'K-Ratio > 3: curva muito estável (Kestner).' },
    ],
  },
  calmar_ratio: {
    higherIsBetter: true,
    steps: [
      { max: 0, grade: 'bad', note: 'Calmar ≤ 0: sem retorno.' },
      { max: 1, grade: 'poor', note: 'Calmar < 1: retorno anual < max DD.' },
      { max: 3, grade: 'good', note: 'Calmar 1–3: bom (hedge fund médio ~1.5).' },
      { max: Infinity, grade: 'excellent', note: 'Calmar > 3: excelente, comparável a Medallion.' },
    ],
  },
  ulcer_index: {
    higherIsBetter: false,
    steps: [
      { max: 3, grade: 'excellent', note: 'UI < 3: equity muito estável.' },
      { max: 7, grade: 'good', note: 'UI 3–7: bom.' },
      { max: 15, grade: 'acceptable', note: 'UI 7–15: volatilidade moderada em DDs.' },
      { max: Infinity, grade: 'poor', note: 'UI > 15: DDs prolongados/dolorosos.' },
    ],
  },
  expectancy: {
    higherIsBetter: true,
    steps: [
      { max: 0, grade: 'bad', note: 'Expectancy ≤ 0: perde por trade na média.' },
      { max: Infinity, grade: 'acceptable', note: 'Expectancy > 0: positiva. Compare ao custo por trade.' },
    ],
  },
  payoff_ratio: {
    higherIsBetter: true,
    steps: [
      { max: 1, grade: 'poor', note: 'Payoff < 1: win médio < loss médio (exige WR alto).' },
      { max: 2, grade: 'acceptable', note: 'Payoff 1–2: balanceado.' },
      { max: 3, grade: 'good', note: 'Payoff 2–3: típico trend-following.' },
      { max: Infinity, grade: 'excellent', note: 'Payoff > 3: excelente assimetria.' },
    ],
  },
  annual_return_pct: {
    higherIsBetter: true,
    steps: [
      { max: 0, grade: 'bad', note: 'Retorno anual ≤ 0.' },
      { max: 8, grade: 'poor', note: '< 8%/ano: abaixo de S&P 500 histórico.' },
      { max: 15, grade: 'acceptable', note: '8–15%/ano: aceitável.' },
      { max: 30, grade: 'good', note: '15–30%/ano: bom (fundos top reportam ~20%).' },
      { max: 100, grade: 'excellent', note: '30–100%/ano: excelente — valide OOS.' },
      { max: Infinity, grade: 'acceptable', note: '> 100%/ano: quase certamente overfit ou escala limitada.' },
    ],
  },
  psr_0: {
    higherIsBetter: true,
    steps: [
      { max: 0.75, grade: 'poor', note: 'PSR < 75%: dúvida real se Sharpe verdadeiro > 0.' },
      { max: 0.95, grade: 'acceptable', note: 'PSR 75–95%: provavelmente real mas não certo.' },
      { max: 0.99, grade: 'good', note: 'PSR 95–99%: alta confiança (Bailey & López de Prado).' },
      { max: Infinity, grade: 'excellent', note: 'PSR > 99%: estatisticamente sólido.' },
    ],
  },
  dsr: {
    higherIsBetter: true,
    steps: [
      { max: 0.5, grade: 'bad', note: 'DSR < 50%: Sharpe provavelmente produto de multi-testing (data snooping).' },
      { max: 0.75, grade: 'poor', note: 'DSR 50–75%: suspeita de overfit pela quantidade de trials.' },
      { max: 0.95, grade: 'acceptable', note: 'DSR 75–95%: sobreviveu ao ajuste por seleção.' },
      { max: Infinity, grade: 'excellent', note: 'DSR > 95%: robusto mesmo corrigindo multi-testing.' },
    ],
  },
  mintrl: {
    higherIsBetter: false, // menor é melhor (menos trades reais necessários)
    steps: [
      { max: 100, grade: 'excellent', note: 'MinTRL < 100 trades: edge claro, confirma rápido.' },
      { max: 500, grade: 'good', note: 'MinTRL 100–500: praticável em poucos meses.' },
      { max: 2000, grade: 'acceptable', note: 'MinTRL 500–2000: vai demorar muitos meses pra confirmar.' },
      { max: Infinity, grade: 'poor', note: 'MinTRL > 2000: inviável de confirmar em prazo razoável.' },
    ],
  },
  prob_dd_exceeds_original: {
    higherIsBetter: false,
    steps: [
      { max: 0.1, grade: 'excellent', note: 'Prob. DD pior < 10%: DD histórico é realista.' },
      { max: 0.25, grade: 'good', note: 'Prob. 10–25%: DD futuro pode ser um pouco pior.' },
      { max: 0.5, grade: 'acceptable', note: 'Prob. 25–50%: se prepare pra DD maior que o visto.' },
      { max: Infinity, grade: 'poor', note: 'Prob. > 50%: DD histórico subestimou o risco real.' },
    ],
  },
}

const ALIASES = {
  // aliases comuns pra mesmas métricas
  net_profit_pct: 'annual_return_pct',
  annual_return: 'annual_return_pct',
  sharpe: 'sharpe_ratio',
  sortino: 'sortino_ratio',
}

export function gradeMetric(key, value) {
  const realKey = ALIASES[key] || key
  const def = THRESHOLDS[realKey]
  if (!def || value == null || !Number.isFinite(value)) {
    return { grade: 'neutral', color: COLORS.neutral, note: null }
  }
  for (const step of def.steps) {
    if (value <= step.max) {
      return { grade: step.grade, color: COLORS[step.grade], note: step.note }
    }
  }
  const last = def.steps[def.steps.length - 1]
  return { grade: last.grade, color: COLORS[last.grade], note: last.note }
}

// Comparação delta (vs baseline)
export function deltaVs(value, baseline, higherIsBetter = true) {
  if (!Number.isFinite(value) || !Number.isFinite(baseline) || baseline === 0) {
    return null
  }
  const delta = value - baseline
  const pct = (delta / Math.abs(baseline)) * 100
  const better = higherIsBetter ? delta > 0 : delta < 0
  return {
    delta, pct,
    better,
    color: Math.abs(pct) < 1 ? COLORS.neutral : (better ? COLORS.good : COLORS.bad),
    arrow: delta > 0 ? '▲' : delta < 0 ? '▼' : '•',
  }
}

// higherIsBetter por métrica (fallback pra delta)
export function higherIsBetter(key) {
  const realKey = ALIASES[key] || key
  const def = THRESHOLDS[realKey]
  if (!def) return true
  return def.higherIsBetter !== false
}
