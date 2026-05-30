import { useState } from 'react'

/**
 * Instruções passo-a-passo de como exportar o CSV em cada plataforma.
 * Tabs por plataforma. Conteúdo em PT-BR.
 */
const TABS = [
  { id: 'profitchart', label: 'ProfitChart Pro' },
  { id: 'tradelocker', label: 'TradeLocker' },
  { id: 'mt5', label: 'MT5 (usar outra aba)' },
]

const CONTENT = {
  profitchart: {
    title: 'Como exportar do ProfitChart Pro (Nelogica)',
    steps: [
      'Abra o ProfitChart Pro e carregue o gráfico do ativo que quer testar.',
      'Vá em Ferramentas → Editor de Estratégias.',
      'Carregue ou escreva sua estratégia em NTSL.',
      'Clique em Backtest e configure o período de análise.',
      'Após rodar, abra a aba Operações no painel de resultados.',
      'No menu inferior da aba Operações, clique em Exportar Lista de Ordens CSV.',
      'Salve o arquivo .csv em qualquer pasta.',
      'Volte aqui e clique em Selecionar arquivo abaixo. Pronto.',
    ],
    tips: [
      'O CSV exportado costuma ter encoding CP1252 e separador ponto-e-vírgula — o parser detecta automaticamente.',
      'Decimais com vírgula (padrão BR) também são reconhecidos automaticamente.',
      'Se você quiser preservar swap/comissão na análise, certifique-se de que essas colunas estão habilitadas nas configurações do backtest do Profit antes de exportar.',
    ],
    warn: 'Se o CSV exportado não tiver as colunas de Data Entrada, Data Saída, Lado/Operação e Lucro, o parser não conseguirá processá-lo. Reconfigure a tabela no ProfitChart e exporte novamente.',
  },
  tradelocker: {
    title: 'Como exportar do TradeLocker',
    steps: [
      'Faça login no TradeLocker (web ou desktop).',
      'Clique em Accounts no menu lateral e selecione View account na conta desejada.',
      'Role até a seção Trade History.',
      'Selecione o período (datas) que quer exportar.',
      'Clique no ícone ⋮ (três pontos verticais) ao lado do número da conta, acima da tabela.',
      'Selecione Export account History.',
      'O TradeLocker gera um arquivo .csv que será baixado.',
      'Volte aqui e clique em Selecionar arquivo abaixo. Pronto.',
    ],
    tips: [
      'O CSV exportado vem em UTF-8 com separador vírgula e datas no padrão internacional.',
      'O parser reconhece tanto trades fechados quanto operações forex/CFD com swap.',
      'Para análises mais completas, exporte um período de pelo menos 100 operações.',
    ],
    warn: 'O parser foi desenvolvido sem acesso direto à plataforma. Se o CSV exportado pelo seu broker tiver formato diferente (alguns brokers customizam o TradeLocker), use a tela de preview para confirmar antes de salvar.',
  },
  mt5: {
    title: 'Para MetaTrader 5, use a aba específica',
    steps: [
      'Para importar relatórios .htm do MT5, use a aba Backtest Aura ao invés desta.',
      'A aba Backtest Aura tem parser dedicado para o formato HTM do MT5 com todas as métricas nativas.',
    ],
    tips: [
      'Se você só tem CSV exportado manualmente do MT5, esta aba também aceita, mas o resultado pode não ter parâmetros do EA — use o HTM sempre que possível.',
    ],
    warn: '',
  },
}

export function PlatformInstructions() {
  const [active, setActive] = useState('profitchart')
  const c = CONTENT[active]

  return (
    <div className="card">
      <h2>Como exportar o CSV da sua plataforma</h2>
      <div style={{ display: 'flex', gap: 4, marginBottom: 14, flexWrap: 'wrap' }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setActive(t.id)}
            style={{
              padding: '6px 14px', fontSize: 13,
              background: active === t.id ? '#238636' : 'transparent',
              border: '1px solid ' + (active === t.id ? '#3fb950' : '#30363d'),
              color: active === t.id ? '#fff' : '#8b949e',
              borderRadius: 6, cursor: 'pointer',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <h3 style={{ color: '#58a6ff', fontSize: 14, marginBottom: 8 }}>{c.title}</h3>

      <ol style={{ paddingLeft: 22, marginBottom: 12 }}>
        {c.steps.map((step, i) => (
          <li key={i} style={{ marginBottom: 4, fontSize: 13, lineHeight: 1.5 }}>
            {step}
          </li>
        ))}
      </ol>

      {c.tips.length > 0 && (
        <div style={{
          padding: '8px 12px', background: 'rgba(88,166,255,0.08)',
          border: '1px solid rgba(88,166,255,0.3)', borderRadius: 6,
          marginBottom: 8, fontSize: 12,
        }}>
          <b style={{ color: '#58a6ff' }}>💡 Dicas:</b>
          <ul style={{ paddingLeft: 18, margin: '4px 0' }}>
            {c.tips.map((tip, i) => (
              <li key={i} style={{ marginBottom: 3 }}>{tip}</li>
            ))}
          </ul>
        </div>
      )}

      {c.warn && (
        <div style={{
          padding: '8px 12px', background: 'rgba(210,153,34,0.08)',
          border: '1px solid rgba(210,153,34,0.3)', borderRadius: 6,
          fontSize: 12, color: '#d6cda2',
        }}>
          <b style={{ color: '#d29922' }}>⚠️ Atenção:</b> {c.warn}
        </div>
      )}
    </div>
  )
}
