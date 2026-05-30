/**
 * Conteúdo educativo para tooltips de KPIs e itens do scorecard.
 * Cada chave traz:
 *   plain         – tradução em linguagem cotidiana
 *   ranges        – [{label, range, color}] faixas de valores
 *   howToImprove  – ações para melhorar quando está ruim
 *   howToKeep     – como não regredir quando já está bom
 *   formula       – (opcional) explicação técnica curta
 */

export const HELP = {
  // ============================================================ KPIs principais
  'net-profit': {
    plain: 'Lucro líquido total da estratégia (soma de todos os trades).',
    ranges: [
      { label: 'Ruim', range: '≤ 0', color: '#f85149' },
      { label: 'Bom', range: '+30% do capital', color: '#d29922' },
      { label: 'Excelente', range: '+100% do capital', color: '#3fb950' },
    ],
    howToImprove: 'Aumentar nº de trades ou tamanho da posição (cuidado com risco), elevar Profit Factor com filtros melhores, alongar TP via trailing stop.',
    howToKeep: 'Monitorar Profit Factor mensal; se cair, parar de aumentar position size.',
  },
  'max-dd-pct': {
    plain: 'Maior queda do capital, do pico ao fundo (em %). Mede o "pior pesadelo" do robô.',
    ranges: [
      { label: 'Excelente', range: '< 10%', color: '#3fb950' },
      { label: 'Bom', range: '10–20%', color: '#d29922' },
      { label: 'Ruim', range: '> 25%', color: '#f85149' },
    ],
    howToImprove: 'Reduzir position size, aplicar equity control (parar após N losses), apertar stop loss, evitar regimes ruins via filtros.',
    howToKeep: 'Capital alocado deve aguentar 1.5–2× o DD histórico (DDs futuros costumam ser piores).',
  },
  'sharpe': {
    plain: 'Retorno por unidade de risco (volatilidade). Quanto maior, mais consistente o lucro vs as oscilações.',
    ranges: [
      { label: 'Fraco', range: '< 0.8', color: '#f85149' },
      { label: 'Bom', range: '1.0–1.5', color: '#d29922' },
      { label: 'Excelente', range: '> 2.0', color: '#3fb950' },
    ],
    howToImprove: 'Apertar filtros (entrar só nos sinais bons), reduzir trades perdedores, suavizar curva de equity, diversificar timeframe/símbolo.',
    howToKeep: 'Se Sharpe cai abaixo de 1.0 em rolling window de 6 meses, pausar e reavaliar.',
    formula: 'Sharpe = média(retornos) / desvio_padrão(retornos) × √252',
  },
  'sortino': {
    plain: 'Como o Sharpe, mas penaliza só a volatilidade DOS LOSSES (não pune oscilações para cima).',
    ranges: [
      { label: 'Fraco', range: '< 1.0', color: '#f85149' },
      { label: 'Bom', range: '1.5–2.5', color: '#d29922' },
      { label: 'Excelente', range: '> 3.0', color: '#3fb950' },
    ],
    howToImprove: 'Apertar SL para cortar losses grandes, alongar TP para esticar winners, filtrar entradas de baixa qualidade.',
    howToKeep: 'Geralmente é 1.3–2.0× o Sharpe; se for menor, há losses concentrados.',
  },
  'calmar': {
    plain: 'Retorno anualizado dividido pelo Max DD. Mede quanto lucra para cada % de drawdown sofrido.',
    ranges: [
      { label: 'Fraco', range: '< 0.5', color: '#f85149' },
      { label: 'Bom', range: '1.0–2.0', color: '#d29922' },
      { label: 'Excelente', range: '> 3.0', color: '#3fb950' },
    ],
    howToImprove: 'Reduzir DD (vide max-dd-pct) ou aumentar retorno mantendo DD. Equity control ajuda muito.',
    howToKeep: 'Calmar < 1.0 em live é vermelho — capital travado demais.',
  },
  'profit-factor': {
    plain: 'Total ganho ÷ total perdido. PF = 2 significa que você ganha R$2 para cada R$1 perdido.',
    ranges: [
      { label: 'Ruim', range: '< 1.3', color: '#f85149' },
      { label: 'Bom', range: '1.5–2.0', color: '#d29922' },
      { label: 'Excelente', range: '> 2.5', color: '#3fb950' },
    ],
    howToImprove: 'Apertar SL, alongar TP, filtrar entradas, focar nos setups de maior Payoff Ratio.',
    howToKeep: 'PF > 3 em backtest geralmente cai 30–50% em live por slippage/spread reais.',
  },
  'win-rate': {
    plain: '% de trades vencedores. SOZINHO não diz muito — precisa ser lido junto com Payoff Ratio.',
    ranges: [
      { label: 'Trend-following', range: '30–45% (ok)', color: '#d29922' },
      { label: 'Mean reversion', range: '55–70% (ok)', color: '#3fb950' },
      { label: 'Suspeito', range: '> 85%', color: '#f85149' },
    ],
    howToImprove: 'Subir Win Rate sem cuidado piora o sistema. Foque em Expectancy (média ponderada).',
    howToKeep: 'Win Rate muito alto (>80%) com Payoff < 0.3 é típico de Martingale escondido — perigoso.',
  },
  'payoff-ratio': {
    plain: 'Média do ganho ÷ média da perda. PR = 2 significa que seu trade médio ganhador é 2× a perda média.',
    ranges: [
      { label: 'Mean-rev (típico)', range: '0.5–1.0', color: '#d29922' },
      { label: 'Trend (típico)', range: '1.5–3.0', color: '#3fb950' },
      { label: 'Atenção', range: '< 0.3', color: '#f85149' },
    ],
    howToImprove: 'Trailing stop em winners, TP alongado, SL mais apertado quando o trade vai contra rápido.',
    howToKeep: 'Win Rate × Payoff Ratio = quanto importa. (WR × PR) > (1−WR) = expectativa positiva.',
  },
  'expectancy': {
    plain: 'Quanto você espera ganhar (ou perder) em CADA trade, na média. É o "edge por trade" em $.',
    ranges: [
      { label: 'Negativa', range: '< 0', color: '#f85149' },
      { label: 'Marginal', range: '0–0.1× SL médio', color: '#d29922' },
      { label: 'Saudável', range: '> 0.3× SL médio', color: '#3fb950' },
    ],
    howToImprove: 'Filtrar trades de baixa qualidade (reduz nº mas aumenta expectancy).',
    howToKeep: 'Expectancy precisa ser ≥ 2× custos (spread+slippage+comissão) para sobreviver em live.',
  },
  'recovery-factor': {
    plain: 'Quantas vezes o lucro líquido cobre o maior DD. RF = 5 quer dizer que você lucrou 5× o pior pesadelo.',
    ranges: [
      { label: 'Fraco', range: '< 1.5', color: '#f85149' },
      { label: 'Bom', range: '2.5–5', color: '#d29922' },
      { label: 'Excelente', range: '> 7', color: '#3fb950' },
    ],
    howToImprove: 'Reduzir DD (equity control), ou rodar mais tempo para aumentar profit cumulado.',
    howToKeep: 'RF cresce com tempo; em janelas curtas é normal estar mais baixo.',
  },
  'sqn': {
    plain: 'System Quality Number (Van Tharp). Mede qualidade geral em uma escala de 0 a 10+.',
    ranges: [
      { label: 'Ruim', range: '< 1.6', color: '#f85149' },
      { label: 'Bom', range: '2.5–3.5', color: '#d29922' },
      { label: 'Excelente', range: '> 5.0', color: '#3fb950' },
    ],
    howToImprove: 'SQN é sensível a Expectancy e nº de trades. Aumentar amostra + edge melhora.',
    howToKeep: 'SQN > 7 em backtest com poucos trades é overfitting típico.',
    formula: 'SQN = (Expectancy / std_trades) × √(n_trades), max 100 trades',
  },
  'k-ratio': {
    plain: 'Mede a CONSISTÊNCIA do crescimento da equity (suavidade da curva ao longo do tempo).',
    ranges: [
      { label: 'Ruim', range: '< 0.5', color: '#f85149' },
      { label: 'Bom', range: '0.7–1.0', color: '#d29922' },
      { label: 'Excelente', range: '> 1.5', color: '#3fb950' },
    ],
    howToImprove: 'Suavizar equity = reduzir DD entre trades. Equity control e position sizing por vol ajudam.',
    howToKeep: 'K-Ratio mede a INCLINAÇÃO da regressão da equity; cai se há plateaus longos.',
  },
  'ulcer-index': {
    plain: 'Mede a "dor" do drawdown ao longo do tempo. Quanto MENOR, melhor (DDs leves e curtos).',
    ranges: [
      { label: 'Excelente', range: '< 2', color: '#3fb950' },
      { label: 'Bom', range: '2–5', color: '#d29922' },
      { label: 'Ruim', range: '> 10', color: '#f85149' },
    ],
    howToImprove: 'Recuperar rápido dos DDs (não ficar meses parado), equity control para parar antes de DD profundo.',
    howToKeep: 'Diferente do Max DD, este pune DDs PROLONGADOS — perfeito para medir conforto psicológico.',
  },
  'annual-return': {
    plain: 'Retorno % anualizado, projeção baseada no período testado.',
    ranges: [
      { label: 'Inviável', range: '< 10%', color: '#f85149' },
      { label: 'Bom', range: '20–50%', color: '#d29922' },
      { label: 'Suspeito', range: '> 200%', color: '#f85149' },
    ],
    howToImprove: 'Mais trades ou maior position size. NÃO use overfitting para inflar este número.',
    howToKeep: 'Anualizar período < 6 meses gera distorção. Confirmar com pelo menos 1 ano de dados.',
  },

  // ============================================================ Robustez / WFA
  'pbo': {
    plain: 'Probabilidade do backtest estar "viciado". PBO = 60% significa que em 60% das partições, o "vencedor" do teste vira perdedor fora do teste.',
    ranges: [
      { label: 'Robusto', range: '< 25%', color: '#3fb950' },
      { label: 'Moderado', range: '25–50%', color: '#d29922' },
      { label: 'Overfit', range: '> 50%', color: '#f85149' },
    ],
    howToImprove: 'Reduzir nº de parâmetros otimizados, usar ranges menores, validar em hold-out, NÃO escolher single best (pegar top-N estáveis).',
    howToKeep: 'PBO baixo + DSR alto = sinal verde. PBO baixo + DSR baixo = amostra insuficiente.',
  },
  'stability-score': {
    plain: 'Razão entre o score médio OOS e o score médio IS no Walk-Forward. 100% = OOS tão bom quanto IS.',
    ranges: [
      { label: 'Frágil', range: '< 50%', color: '#f85149' },
      { label: 'Aceitável', range: '50–75%', color: '#d29922' },
      { label: 'Robusto', range: '> 75%', color: '#3fb950' },
    ],
    howToImprove: 'Reduzir overfitting na otimização IS (menos params), aumentar período de cada fold IS.',
    howToKeep: '> 100% (OOS melhor que IS) é suspeito — confirma com mais folds.',
  },
  'consistency': {
    plain: '% dos folds OOS que terminaram positivos. Mede se a estratégia funciona em DIFERENTES regimes.',
    ranges: [
      { label: 'Inconsistente', range: '< 60%', color: '#f85149' },
      { label: 'Razoável', range: '60–80%', color: '#d29922' },
      { label: 'Consistente', range: '> 80%', color: '#3fb950' },
    ],
    howToImprove: 'Filtros de regime (ADX, ATR, hora do dia), evitar otimizar em períodos atípicos.',
    howToKeep: '1–2 folds negativos em 10 é normal. > 3 folds negativos = problema.',
  },
  'degradation': {
    plain: 'Quanto o desempenho CAI ao sair do IS para o OOS. 30% = OOS rende 30% menos que IS.',
    ranges: [
      { label: 'Saudável', range: '< 30%', color: '#3fb950' },
      { label: 'Aceitável', range: '30–60%', color: '#d29922' },
      { label: 'Crítico', range: '> 60%', color: '#f85149' },
    ],
    howToImprove: 'Mesmas ações de overfitting: menos params, mais dados IS, validar em multiple folds.',
    howToKeep: 'Em live, esperar degradação adicional de 20–30% além do OOS — ser conservador.',
  },
  'avg-correlation': {
    plain: 'Correlação MÉDIA entre as curvas de equity dos robôs do portfólio. Quanto MENOR, melhor para diversificação.',
    ranges: [
      { label: 'Bem diversificado', range: '< 0.3', color: '#3fb950' },
      { label: 'Diversificação parcial', range: '0.3–0.6', color: '#d29922' },
      { label: 'Pouca diversificação', range: '> 0.6', color: '#f85149' },
    ],
    howToImprove: 'Combinar estratégias de tipos diferentes (trend + mean-rev + breakout), símbolos descorrelacionados, timeframes diferentes.',
    howToKeep: 'Correlação que era 0.2 pode subir para 0.7 em crash de mercado — testar em períodos de stress.',
  },
  'diversification-ratio': {
    plain: 'Índice 0–100%. 100% = robôs totalmente descorrelacionados; 0% = todos fazem a mesma coisa.',
    ranges: [
      { label: 'Pouco diversificado', range: '< 40%', color: '#f85149' },
      { label: 'Razoável', range: '40–70%', color: '#d29922' },
      { label: 'Bem diversificado', range: '> 70%', color: '#3fb950' },
    ],
    howToImprove: 'Remover robôs redundantes (correlação > 0.7 com outro), incluir estratégias contrárias.',
    howToKeep: 'Calculado como 1 − média(|correlações|). Sensível a outliers em pares específicos.',
  },

  // ============================================================ Skew / Kurt
  'skew': {
    plain: 'Assimetria da distribuição dos retornos. POSITIVO = mais ganhos extremos do que perdas extremas (bom). NEGATIVO = mais perdas raras grandes (ruim).',
    ranges: [
      { label: 'Ruim (vende vol)', range: '< -0.5', color: '#f85149' },
      { label: 'Simétrico', range: '-0.5 a 0.5', color: '#d29922' },
      { label: 'Excelente', range: '> 1.0', color: '#3fb950' },
    ],
    howToImprove: 'SL apertado + TP alongado gera skew positivo. Evitar "vender prêmio" (martingale, anti-trend sem stop).',
    howToKeep: 'Trend-following naturalmente tem skew positivo; mean-reversion tem skew negativo (cuidado!).',
  },
  'kurt': {
    plain: 'Mede "fat tails" da distribuição. ALTO = eventos extremos (cisnes negros) mais frequentes que o esperado. Para retornos financeiros, kurt > 3 é normal.',
    ranges: [
      { label: 'Normal-like', range: '0–3', color: '#3fb950' },
      { label: 'Fat tails moderado', range: '3–10', color: '#d29922' },
      { label: 'Fat tails extremo', range: '> 20', color: '#f85149' },
    ],
    howToImprove: 'Reduzir position size para sobreviver aos extremos, evitar overnight em alta vol, considerar Kelly fracionado.',
    howToKeep: 'Kurt alto + skew negativo = combinação tóxica (perdas extremas frequentes).',
  },

  // ============================================================ Scorecard items
  'probabilistic-sharpe': {
    plain: 'PSR = probabilidade do Sharpe verdadeiro (que você verá em live) ser maior que zero, considerando skew/kurt.',
    ranges: [
      { label: 'Ruim', range: '< 90%', color: '#f85149' },
      { label: 'Bom', range: '90–95%', color: '#d29922' },
      { label: 'Excelente', range: '> 95%', color: '#3fb950' },
    ],
    howToImprove: 'Mais trades (período maior), ajustar SL/TP para skew positiva, reduzir position size se kurt é alta, apertar filtros.',
    howToKeep: 'PSR cai se você roda muitos trials de otimização (vide Deflated Sharpe).',
  },
  'deflated-sharpe': {
    plain: 'Sharpe corrigido pelo número de candidatos testados na otimização. Quanto mais você testa, mais alto o threshold para passar.',
    ranges: [
      { label: 'Reprovado', range: '< 90%', color: '#f85149' },
      { label: 'Bom', range: '90–95%', color: '#d29922' },
      { label: 'Excelente', range: '> 95%', color: '#3fb950' },
    ],
    howToImprove: 'Reduzir espaço de busca (menos parâmetros, ranges menores), validar em walk-forward antes de aceitar o top 1, não pegar single best.',
    howToKeep: 'Sempre informar n_trials real ao calcular DSR. Mentir aqui é só auto-engano.',
  },
  'mintrl': {
    plain: 'Minimum Track Record Length: nº de trades necessário para ter 95% de confiança que o edge é real (não ruído).',
    ranges: [
      { label: 'Suficiente', range: '≤ 500', color: '#3fb950' },
      { label: 'Marginal', range: '500–1500', color: '#d29922' },
      { label: 'Insuficiente', range: '> 2000', color: '#f85149' },
    ],
    howToImprove: 'Aumentar Sharpe per-trade (apertar filtros) reduz MinTRL drasticamente, rodar histórico maior, operar multi-símbolo.',
    howToKeep: 'MinTRL alto + amostra pequena = você não SABE se tem edge — só desconfia.',
  },
  'shuffle-test': {
    plain: 'Embaralha a ordem dos trades 1000s de vezes. Se a estratégia segue lucrativa em ≥90% das ordens, o edge não depende de "sequência mágica".',
    ranges: [
      { label: 'Frágil', range: '< 70%', color: '#f85149' },
      { label: 'Ok', range: '70–90%', color: '#d29922' },
      { label: 'Robusto', range: '> 90%', color: '#3fb950' },
    ],
    howToImprove: 'Cortar dependência de outliers (vide outlier-dependency), aumentar amostra, adicionar filtro de regime.',
    howToKeep: 'Shuffle alto + Outlier-dep ruim = um grande trade resgatou o sistema. Cuidado.',
  },
  'block-bootstrap-dd': {
    plain: 'Reamostra streaks preservando autocorrelação. Mostra o "DD pior provável" (P95) considerando que streaks podem ser piores em live.',
    ranges: [
      { label: 'Seguro', range: 'DD P95 < 1.5× DD hist', color: '#3fb950' },
      { label: 'Atenção', range: '1.5–2.5×', color: '#d29922' },
      { label: 'Perigoso', range: '> 2.5×', color: '#f85149' },
    ],
    howToImprove: 'Dimensionar capital para o P95, não para o histórico. Equity control. Reduzir position size.',
    howToKeep: 'Block bootstrap é mais realista que shuffle em mercados com autocorrelação (forex, índices).',
  },
  'skip-test': {
    plain: 'Remove aleatoriamente 20% dos trades (simulando conexão caindo). Se a estratégia continua lucrativa ≥90% das vezes, ela é robusta.',
    ranges: [
      { label: 'Frágil', range: '< 75%', color: '#f85149' },
      { label: 'Ok', range: '75–90%', color: '#d29922' },
      { label: 'Robusto', range: '> 90%', color: '#3fb950' },
    ],
    howToImprove: 'Endurecer filtros (menos trades ruins compensados por bons), reduzir dependência de outliers, MAE/MFE analysis.',
    howToKeep: 'Em live, é normal perder 5–10% dos trades por questões de execução; estratégia precisa aguentar isso.',
  },
  'noise-test': {
    plain: 'Aplica jitter de ±25% em cada profit (simulando slippage). Se sobrevive ≥90% das vezes, o edge é maior que o custo.',
    ranges: [
      { label: 'Margem fina', range: '< 75%', color: '#f85149' },
      { label: 'Ok', range: '75–90%', color: '#d29922' },
      { label: 'Margem confortável', range: '> 90%', color: '#3fb950' },
    ],
    howToImprove: 'Operar ativos mais líquidos, evitar horários ruins, usar ordens limit, aumentar TP relativamente ao spread.',
    howToKeep: 'Se passa com folga aqui, geralmente live se aproxima bem do backtest.',
  },
  'regime-yearly': {
    plain: 'Verifica se a estratégia é lucrativa em CADA ano do backtest. Anos negativos indicam dependência de regime de mercado.',
    ranges: [
      { label: 'Frágil', range: '< 60% anos +', color: '#f85149' },
      { label: 'Ok', range: '60–90%', color: '#d29922' },
      { label: 'Robusto', range: '100% anos +', color: '#3fb950' },
    ],
    howToImprove: 'Identificar o que diferencia os anos ruins (volatilidade, tendência) e adicionar filtro. Combinar com estratégia contrária.',
    howToKeep: 'Um ano ruim em 5 é tolerável. Múltiplos anos seguidos negativos = estratégia desatualizada.',
  },
  't-stat': {
    plain: 'Mede quão estatisticamente significativo é o lucro médio por trade. t = 2 significa que há 95% de chance do edge ser real (e não sorte).',
    ranges: [
      { label: 'Não significativo', range: '< 2.0', color: '#f85149' },
      { label: 'Significativo', range: '2.0–2.5', color: '#d29922' },
      { label: 'Renaissance-grade', range: '> 2.5', color: '#3fb950' },
    ],
    howToImprove: 'Aumentar nº de trades, adicionar filtro de qualidade (menos trades ruins → maior média), combinar sinais.',
    howToKeep: 't ≥ 2.5 é o threshold lendário interno da Renaissance. ≥ 3.0 é elite.',
    formula: 't = média(retornos) × √n / desvio(retornos)',
  },
  'ljung-box': {
    plain: 'Detecta autocorrelação nos retornos. p > 0.05 = retornos independentes (bom). p < 0.05 = trade atual depende do anterior (suspeito).',
    ranges: [
      { label: 'Suspeito', range: 'p < 0.01', color: '#f85149' },
      { label: 'Marginal', range: 'p 0.01–0.05', color: '#d29922' },
      { label: 'Independente', range: 'p > 0.05', color: '#3fb950' },
    ],
    howToImprove: 'Verificar se há look-ahead bias (indicador usando dado futuro), aumentar cooldown entre trades, reduzir over-trading.',
    howToKeep: 'ACF lag-1 alto positivo = trades muito próximos compartilhando regime. Negativo = over-trading.',
  },
  'runs-test': {
    plain: 'Testa se wins e losses estão clusterizados ("ganha-ganha-ganha-perde-perde-perde"). p > 0.05 = aleatórios (bom). Clustering = regime-dependente.',
    ranges: [
      { label: 'Clusterizado', range: 'p < 0.01', color: '#f85149' },
      { label: 'Marginal', range: 'p 0.01–0.05', color: '#d29922' },
      { label: 'Aleatório', range: 'p > 0.05', color: '#3fb950' },
    ],
    howToImprove: 'Identificar o regime (ADX, vol, hora) e filtrar, usar equity control, segmentar backtest por regime.',
    howToKeep: 'Clustering pode ser ok se VOCÊ entende o regime e tem como detectá-lo em live.',
  },
  'outlier-dependency': {
    plain: 'Verifica se o lucro depende dos 5% melhores trades. Se remover os top 5% e a estratégia ainda lucra, ela é robusta.',
    ranges: [
      { label: 'Frágil', range: 'top 5% > 70% lucro', color: '#f85149' },
      { label: 'Concentrado', range: '40–70%', color: '#d29922' },
      { label: 'Distribuído', range: '< 40%', color: '#3fb950' },
    ],
    howToImprove: 'Trailing stop pra capturar outliers maiores, volatility sizing pra apostar mais nos setups raros, verificar se outliers são reais (não gaps).',
    howToKeep: 'Princípio Simons: edge real é distribuído. Edge concentrado em 5 trades é sorte.',
  },
  'tail-ratio': {
    plain: 'Compara o tamanho dos ganhos extremos (P95) com o das perdas extremas (P5). TR > 1 = ganhos maiores que perdas (assimetria favorável).',
    ranges: [
      { label: 'Desfavorável', range: '< 0.8', color: '#f85149' },
      { label: 'Neutro', range: '0.8–1.2', color: '#d29922' },
      { label: 'Favorável', range: '> 1.5', color: '#3fb950' },
    ],
    howToImprove: 'Apertar SL (corta cauda esquerda), trailing stop para esticar winners, aumentar razão TP:SL.',
    howToKeep: 'Tail ratio < 1 + skew negativo = sistema vende prêmio (perigoso em crash).',
  },
  'jarque-bera': {
    plain: 'Testa a NORMALIDADE da distribuição dos retornos. Em estratégias, queremos NÃO-normal com skew positivo (mais ganhos extremos que perdas).',
    ranges: [
      { label: 'Skew negativa', range: 'skew < 0', color: '#f85149' },
      { label: 'Simétrico', range: '-0.5 a 0.5', color: '#d29922' },
      { label: 'Assimétrico favorável', range: 'skew > 0.5', color: '#3fb950' },
    ],
    howToImprove: 'SL apertado + trailing TP = skew positivo. Cortar trades de pior payoff ratio.',
    howToKeep: 'Kurt > 10 é fat tails extremo → considerar Kelly fracionado para position sizing.',
  },
}

/**
 * Mapeia nome do scorecard (português) para a chave de help.
 * Usa prefixos/keywords porque os nomes incluem valores dinâmicos
 * (ex: "Sobrevive a remoção de 20% dos trades" varia o pct).
 */
export function matchScorecardKey(name) {
  if (!name) return null
  const n = name.toLowerCase()
  if (n.startsWith('probabilistic sharpe')) return 'probabilistic-sharpe'
  if (n.startsWith('deflated sharpe')) return 'deflated-sharpe'
  if (n.startsWith('mintrl')) return 'mintrl'
  if (n.startsWith('shuffle')) return 'shuffle-test'
  if (n.startsWith('block bootstrap')) return 'block-bootstrap-dd'
  if (n.includes('remoção de') && n.includes('trades')) return 'skip-test'
  if (n.includes('slippage')) return 'noise-test'
  if (n.startsWith('lucrativo em todos os anos')) return 'regime-yearly'
  if (n.startsWith('t-stat')) return 't-stat'
  if (n.includes('ljung-box')) return 'ljung-box'
  if (n.includes('runs test')) return 'runs-test'
  if (n.includes('top 5%')) return 'outlier-dependency'
  if (n.includes('tail ratio')) return 'tail-ratio'
  if (n.includes('jarque-bera') || n.includes('assimetria')) return 'jarque-bera'
  return null
}
