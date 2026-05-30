"""Gera o Manual Completo do Usuário em PDF.

Uso: python docs/generate_manual.py

Saída: docs/Manual-AuraBackTest.pdf
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.frames import Frame
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate

# ─────────────────────────────────────────────────────────────────────────────
# Cores (paleta do app)
# ─────────────────────────────────────────────────────────────────────────────
BG = HexColor("#0d1117")
SURFACE = HexColor("#161b22")
BORDER = HexColor("#30363d")
TEXT = HexColor("#e6edf3")
MUTED = HexColor("#8b949e")
GREEN = HexColor("#3fb950")
GREEN_DIM = HexColor("#238636")
RED = HexColor("#f85149")
YELLOW = HexColor("#d29922")
BLUE = HexColor("#58a6ff")
GOLD = HexColor("#c4a04a")
PURPLE = HexColor("#a371f7")

OUTPUT_PATH = Path(__file__).resolve().parent / "Manual-AuraBackTest.pdf"

# ─────────────────────────────────────────────────────────────────────────────
# Estilos
# ─────────────────────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()

H1 = ParagraphStyle(
    "H1", parent=styles["Heading1"],
    fontName="Helvetica-Bold", fontSize=22, leading=28,
    textColor=GREEN, spaceBefore=18, spaceAfter=12,
)
H2 = ParagraphStyle(
    "H2", parent=styles["Heading2"],
    fontName="Helvetica-Bold", fontSize=16, leading=22,
    textColor=BLUE, spaceBefore=14, spaceAfter=8,
)
H3 = ParagraphStyle(
    "H3", parent=styles["Heading3"],
    fontName="Helvetica-Bold", fontSize=13, leading=18,
    textColor=TEXT, spaceBefore=10, spaceAfter=6,
)
BODY = ParagraphStyle(
    "Body", parent=styles["BodyText"],
    fontName="Helvetica", fontSize=10.5, leading=15,
    textColor=TEXT, alignment=0, spaceAfter=6,
)
SMALL = ParagraphStyle(
    "Small", parent=BODY,
    fontSize=9, leading=12, textColor=MUTED,
)
CODE = ParagraphStyle(
    "Code", parent=BODY,
    fontName="Courier", fontSize=9, leading=13,
    backColor=SURFACE, textColor=GREEN, leftIndent=8, rightIndent=8,
    borderColor=BORDER, borderWidth=0.5, borderPadding=4,
    spaceBefore=4, spaceAfter=8,
)
TIP = ParagraphStyle(
    "Tip", parent=BODY,
    backColor=HexColor("#1f2a37"), textColor=TEXT,
    borderColor=BLUE, borderWidth=1, borderPadding=8,
    leftIndent=6, rightIndent=6, spaceBefore=6, spaceAfter=8,
)
WARN = ParagraphStyle(
    "Warn", parent=BODY,
    backColor=HexColor("#2a2210"), textColor=TEXT,
    borderColor=YELLOW, borderWidth=1, borderPadding=8,
    leftIndent=6, rightIndent=6, spaceBefore=6, spaceAfter=8,
)
DANGER = ParagraphStyle(
    "Danger", parent=BODY,
    backColor=HexColor("#2a1010"), textColor=TEXT,
    borderColor=RED, borderWidth=1, borderPadding=8,
    leftIndent=6, rightIndent=6, spaceBefore=6, spaceAfter=8,
)
COVER_TITLE = ParagraphStyle(
    "CoverTitle", parent=H1,
    fontSize=42, leading=50, textColor=GREEN,
    alignment=1, spaceBefore=0, spaceAfter=12,
)
COVER_SUB = ParagraphStyle(
    "CoverSub", parent=BODY,
    fontSize=14, leading=22, textColor=MUTED, alignment=1,
)
TOC_ITEM = ParagraphStyle(
    "TocItem", parent=BODY,
    fontSize=11, leading=16, textColor=TEXT,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def p(text: str, style: ParagraphStyle = BODY):
    return Paragraph(text, style)


def bullet_list(items: list[str]):
    out = []
    for it in items:
        out.append(Paragraph(f"• {it}", BODY))
    return out


def numbered_list(items: list[str]):
    out = []
    for i, it in enumerate(items, 1):
        out.append(Paragraph(f"<b>{i}.</b> {it}", BODY))
    return out


def kv_table(rows: list[tuple[str, str]], col_widths=(5 * cm, 11 * cm)):
    data = [[p(f"<b>{k}</b>", BODY), p(v, BODY)] for k, v in rows]
    t = Table(data, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def metric_table(rows: list[tuple[str, str, str, str]]):
    """[(metric, what, range_bad_good, range_excellent), ...]"""
    header = ["Métrica", "O que mede", "Ruim / Bom", "Excelente"]
    data = [[p(f"<b>{c}</b>", BODY) for c in header]]
    for r in rows:
        data.append([p(r[0], BODY), p(r[1], SMALL), p(r[2], SMALL), p(r[3], SMALL)])
    t = Table(data, colWidths=(4 * cm, 6.5 * cm, 3.5 * cm, 2.5 * cm),
              hAlign="LEFT", repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GREEN_DIM),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("BACKGROUND", (0, 1), (-1, -1), SURFACE),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def section_header(num: str, title: str):
    """Cabeçalho de capítulo."""
    return Paragraph(f"<b>{num}</b> &nbsp;&nbsp; {title}", H1)


def tip(text: str):
    return Paragraph(f"<b>💡 Dica:</b> {text}", TIP)


def warn(text: str):
    return Paragraph(f"<b>⚠️ Atenção:</b> {text}", WARN)


def danger(text: str):
    return Paragraph(f"<b>🛑 Importante:</b> {text}", DANGER)


# ─────────────────────────────────────────────────────────────────────────────
# Footer com número da página e capítulo
# ─────────────────────────────────────────────────────────────────────────────
def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(BG)
    canvas.rect(0, 0, A4[0], A4[1], stroke=0, fill=1)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 9)
    # Rodapé
    canvas.drawString(2 * cm, 1.2 * cm, "AuraBackTest — Manual do Usuário")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(2 * cm, 1.6 * cm, A4[0] - 2 * cm, 1.6 * cm)
    # Cabeçalho (linha fina superior)
    canvas.line(2 * cm, A4[1] - 1.5 * cm, A4[0] - 2 * cm, A4[1] - 1.5 * cm)
    canvas.setFillColor(GREEN)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(2 * cm, A4[1] - 1.2 * cm, "AuraBackTest")
    canvas.restoreState()


def on_cover(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(BG)
    canvas.rect(0, 0, A4[0], A4[1], stroke=0, fill=1)
    # Barra dourada lateral
    canvas.setFillColor(GREEN)
    canvas.rect(0, 0, 0.6 * cm, A4[1], stroke=0, fill=1)
    canvas.restoreState()


# ─────────────────────────────────────────────────────────────────────────────
# Conteúdo do manual
# ─────────────────────────────────────────────────────────────────────────────
def build_content():
    story: list = []

    # ===== CAPA =====
    story.append(Spacer(1, 5 * cm))
    story.append(p("AuraBackTest", COVER_TITLE))
    story.append(Spacer(1, 0.4 * cm))
    story.append(p("Manual Completo do Usuário", COVER_SUB))
    story.append(Spacer(1, 5 * cm))
    cover_kv = kv_table([
        ("Versão", "0.5.6 ou superior"),
        ("Plataforma", "Windows 10 / 11 (64-bit)"),
        ("Pré-requisito", "MetaTrader 5 instalado"),
        ("Licença", "Vitalícia (sem mensalidade)"),
        ("Suporte", "thiago.belo.pasa@gmail.com"),
    ], col_widths=(5 * cm, 9 * cm))
    story.append(cover_kv)
    story.append(Spacer(1, 2 * cm))
    story.append(p(
        "<i>Backtesting profissional, validação estatística avançada e análise "
        "quantitativa para traders sistemáticos que querem separar robôs que "
        "<b>sobrevivem no real</b> dos que ficaram bonitos só no backtest.</i>",
        COVER_SUB,
    ))
    story.append(PageBreak())

    # ===== SUMÁRIO =====
    story.append(p("Sumário", H1))
    toc_items = [
        ("1.", "Bem-vindo ao AuraBackTest"),
        ("2.", "Instalação e primeiros passos"),
        ("3.", "Conceitos fundamentais"),
        ("4.", "Tour pela interface"),
        ("5.", "Aba Começar (Home)"),
        ("6.", "Backtest Aura — importar relatório do MT5"),
        ("7.", "Backtest Individual — análise completa"),
        ("8.", "Otimização ao vivo"),
        ("9.", "Análise de Otimização (Triagem)"),
        ("10.", "Portfólio — combinar robôs"),
        ("11.", "Walk-Forward Analysis"),
        ("12.", "Histórico"),
        ("13.", "Tooltips (?) e ajuda contextual"),
        ("14.", "Glossário completo de métricas"),
        ("15.", "Interpretando o scorecard de robustez"),
        ("16.", "Workflows recomendados"),
        ("17.", "Solução de problemas (FAQ)"),
        ("18.", "Atualizações automáticas"),
        ("19.", "Suporte e contato"),
    ]
    for num, title in toc_items:
        story.append(p(f"<b>{num}</b> &nbsp;&nbsp; {title}", TOC_ITEM))
    story.append(PageBreak())

    # ===== CAPÍTULO 1 =====
    story.append(section_header("1", "Bem-vindo ao AuraBackTest"))
    story.append(p(
        "O AuraBackTest é um motor de análise quantitativa para traders sistemáticos "
        "que operam no MetaTrader 5. Ele transforma relatórios de backtest e otimização "
        "em <b>diagnósticos estatísticos rigorosos</b>, no estilo dos fundos quantitativos "
        "como Renaissance Technologies.",
    ))
    story.append(p("Para quem é este produto", H2))
    story.append(p(
        "Você se beneficia do AuraBackTest se:",
    ))
    story += bullet_list([
        "Opera robôs (EAs) em MetaTrader 5 e quer parar de adivinhar se o backtest é confiável.",
        "Faz otimização no MT5 e suspeita que o &quot;melhor pass&quot; é overfit, mas não sabe medir.",
        "Roda múltiplos robôs e quer entender se eles estão realmente diversificados.",
        "Quer saber, antes de colocar dinheiro real, qual é o pior cenário razoável (Monte Carlo, Walk-Forward).",
        "Cansou de planilhas de análise manuais e quer um dashboard profissional.",
    ])
    story.append(p("O que ele resolve", H2))
    story += bullet_list([
        "<b>Overfitting silencioso</b>: backtest perfeito que vira pó em conta real. O AuraBackTest detecta isso via PSR, DSR, PBO/CSCV.",
        "<b>Sorte versus edge real</b>: testes Simons (t-stat, Ljung-Box, Runs test, Outlier Dependency) separam estatística de aleatório.",
        "<b>Pior cenário ignorado</b>: Monte Carlo (5 modos) e bootstrap revelam que o drawdown real pode ser muito pior que o histórico.",
        "<b>Realismo na execução</b>: Monte Carlo com ticks reais simula slippage, jitter de timing e custos verdadeiros.",
        "<b>Sequência mágica de trades</b>: shuffle e skip tests garantem que o lucro não dependa de ordem específica.",
        "<b>Portfólio sem diversificação</b>: matriz de correlação + diversification ratio mostram se seus robôs são redundantes.",
        "<b>Estabilidade temporal</b>: Walk-Forward automático ponta-a-ponta valida estratégia em janelas IS/OOS.",
    ])
    story.append(p("Como usar este manual", H2))
    story.append(p(
        "Se você está começando agora, leia os capítulos 1 a 4 em ordem e depois pule para o capítulo 16 (Workflows recomendados). "
        "Quando precisar entender uma métrica específica, consulte o capítulo 14 (Glossário). "
        "Em caso de problemas, vá direto ao capítulo 17 (FAQ)."
    ))
    story.append(tip(
        "Este manual também serve como referência rápida. Todos os termos importantes "
        "estão indexados no glossário. Mantenha o PDF aberto em uma segunda tela enquanto "
        "explora o app pela primeira vez."
    ))
    story.append(PageBreak())

    # ===== CAPÍTULO 2 =====
    story.append(section_header("2", "Instalação e primeiros passos"))
    story.append(p("Requisitos de sistema", H2))
    story.append(kv_table([
        ("Sistema operacional", "Windows 10 ou 11, 64-bit"),
        ("Memória RAM", "Mínimo 4 GB. Recomendado 8 GB+ se for usar Monte Carlo com ticks (arquivos GB)."),
        ("Disco", "Mínimo 500 MB para o app + ~2 GB para dados de tick por símbolo testado."),
        ("MetaTrader 5", "Build 3815 ou superior. Pode ter múltiplas instâncias instaladas."),
        ("Conexão internet", "Necessária para checar atualizações automáticas e (se usar) baixar ticks via API."),
    ]))
    story.append(p(
        "<b>Não é necessário</b> instalar Python, Node.js, banco de dados ou qualquer "
        "dependência adicional — o instalador inclui tudo."
    ))
    story.append(p("Como baixar", H2))
    story.append(p(
        "Acesse a página oficial:"
    ))
    story.append(p("<font color='#58a6ff'>https://thiagobelopasa.github.io/AuraBackTest/</font>", CODE))
    story.append(p(
        "O download do instalador começa automaticamente após 1.2 segundos. "
        "O arquivo se chama <b>AuraBackTest-Setup.exe</b> e tem cerca de 220 MB."
    ))
    story.append(p("Instalando o app", H2))
    story += numbered_list([
        "Execute o arquivo <b>AuraBackTest-Setup.exe</b> com duplo clique.",
        "O Windows SmartScreen pode mostrar &quot;Aplicativo desconhecido&quot; — clique em <b>Mais informações</b> e depois <b>Executar assim mesmo</b>. (Não temos certificado de assinatura ainda; o app é totalmente seguro.)",
        "A instalação é <b>silenciosa e automática</b> — sem perguntas, sem opções a marcar.",
        "Quando finaliza, o app abre sozinho. Um atalho é criado na Área de Trabalho e no Menu Iniciar.",
    ])
    story.append(warn(
        "Se o SmartScreen bloquear sem mostrar a opção de executar, vá em "
        "Propriedades do arquivo (botão direito) → marque &quot;Desbloquear&quot; → OK."
    ))
    story.append(p("Primeira execução", H2))
    story.append(p(
        "Na primeira vez que abrir o AuraBackTest, você verá:"
    ))
    story += bullet_list([
        "<b>Banner verde no topo</b>: confirma que a licença está ativa.",
        "<b>Topo verde &quot;Backend OK&quot;</b>: confirma que o servidor interno do app subiu corretamente.",
        "<b>Tela &quot;Começar&quot;</b>: tour rápido dos 4 fluxos principais.",
    ])
    story.append(tip(
        "Se o &quot;Backend OK&quot; demorar mais de 30 segundos para aparecer, "
        "feche e abra o app novamente. O backend usa a porta 8765 — verifique se "
        "nenhum outro programa está ocupando essa porta."
    ))
    story.append(p("Atualizações", H2))
    story.append(p(
        "O AuraBackTest verifica atualizações automaticamente a cada 30 minutos e "
        "ao abrir o app. Quando há nova versão:"
    ))
    story += numbered_list([
        "Um banner azul aparece no topo: <i>&quot;Nova versão X.Y.Z disponível&quot;</i>.",
        "O download começa em background, sem interromper seu trabalho.",
        "Quando termina, o banner muda para: <i>&quot;Atualização pronta — reinicie&quot;</i>.",
        "Feche o app normalmente. Na próxima abertura, a versão nova já estará ativa.",
    ])
    story.append(PageBreak())

    # ===== CAPÍTULO 3 =====
    story.append(section_header("3", "Conceitos fundamentais"))
    story.append(p(
        "Esta seção explica em <b>linguagem simples</b> os conceitos que aparecem ao longo do app. "
        "Se você já está familiarizado com trading sistemático, pode pular para o capítulo 4."
    ))
    story.append(p("Backtest", H2))
    story.append(p(
        "Simular como uma estratégia teria se comportado no passado. "
        "<b>Vantagem</b>: medir Sharpe, drawdown, profit factor antes de arriscar capital. "
        "<b>Limitação</b>: passado não garante futuro; o resultado depende muito da qualidade dos dados (ticks reais &gt; OHLC)."
    ))
    story.append(p("Otimização", H2))
    story.append(p(
        "Testar centenas/milhares de combinações de parâmetros para achar a melhor configuração. "
        "<b>Risco principal</b>: <b>overfitting</b> — você achou a config que se encaixou perfeitamente "
        "no passado, mas é puro ajuste de curva e não tem edge real."
    ))
    story.append(p("Walk-Forward Analysis (WFA)", H2))
    story.append(p(
        "Dividir o histórico em pedaços (folds). Otimizar em um pedaço (in-sample, IS) e validar no pedaço seguinte (out-of-sample, OOS). "
        "Se a estratégia funciona em OOS, ela é <b>robusta</b>; se só funciona em IS, é overfit. "
        "O AuraBackTest faz isso automaticamente ponta-a-ponta."
    ))
    story.append(p("Monte Carlo", H2))
    story.append(p(
        "Embaralhar/simular os trades milhares de vezes para entender o intervalo de possíveis resultados. "
        "Responde a perguntas como: <i>&quot;Qual é o pior drawdown razoável que esperar?&quot;</i> "
        "e <i>&quot;Quão sensível meu sistema é à ordem dos trades?&quot;</i>."
    ))
    story.append(p("Robustez", H2))
    story.append(p(
        "Capacidade da estratégia de continuar funcionando em condições levemente diferentes do backtest: "
        "mais slippage, regime diferente, ordem diferente de trades. O scorecard do app mede 15+ dimensões de robustez."
    ))
    story.append(p("Overfitting", H2))
    story.append(p(
        "Memorizar o passado em vez de aprender uma regra geral. Sinais: backtest perfeito, "
        "muitos parâmetros otimizados, Sharpe altíssimo (&gt;4), retorno anual irreal (&gt;200%). "
        "Métricas de detecção: PSR (Probabilistic Sharpe), DSR (Deflated Sharpe), PBO via CSCV."
    ))
    story.append(p("Drawdown", H2))
    story.append(p(
        "Maior queda de capital, do pico ao fundo. <b>Max DD %</b> é a maior queda percentual já sofrida. "
        "<b>Regra prática</b>: o capital alocado deve aguentar 1.5–2× o DD histórico, "
        "porque o futuro costuma ser pior."
    ))
    story.append(p("Sharpe Ratio", H2))
    story.append(p(
        "Retorno por unidade de risco (volatilidade). Sharpe = 2 é excelente, &gt; 3 é elite, "
        "&lt; 1 é fraco. <b>Cuidado</b>: Sharpe altíssimo em backtest geralmente cai 30-50% em live."
    ))
    story.append(p("Profit Factor", H2))
    story.append(p(
        "Total ganho ÷ total perdido. PF = 2 significa que para cada R$ 1 perdido você ganhou R$ 2. "
        "<b>Bom</b>: 1.5–2.5. <b>Suspeito</b>: &gt; 3 (frequentemente cai em live)."
    ))
    story.append(p("Expectancy", H2))
    story.append(p(
        "Quanto você espera ganhar em CADA trade, na média. É o &quot;edge por trade&quot;. "
        "Precisa ser ≥ 2× custos (spread + comissão + slippage) para sobreviver em live."
    ))
    story.append(p("PSR (Probabilistic Sharpe)", H2))
    story.append(p(
        "Probabilidade de que o Sharpe real (futuro) seja maior que zero, "
        "considerando assimetria (skew) e fat tails (kurt) dos retornos. "
        "&gt; 95% é excelente."
    ))
    story.append(p("DSR (Deflated Sharpe)", H2))
    story.append(p(
        "Sharpe corrigido pelo número de candidatos testados na otimização. "
        "Quanto mais combinações você testa, mais alto o threshold para considerar significativo. "
        "É um anti-overfitting essencial."
    ))
    story.append(p("PBO via CSCV", H2))
    story.append(p(
        "<b>Probability of Backtest Overfitting</b> via Combinatorially Symmetric Cross-Validation. "
        "Divide os dados em 16 subsets, monta C(16,8) = 12.870 partições, e verifica em quantas o &quot;vencedor&quot; do in-sample vira perdedor no out-of-sample. "
        "PBO &lt; 25% é robusto. PBO &gt; 50% indica overfit severo."
    ))
    story.append(PageBreak())

    # ===== CAPÍTULO 4 =====
    story.append(section_header("4", "Tour pela interface"))
    story.append(p("Barra superior", H2))
    story.append(p(
        "A barra superior do app contém:"
    ))
    story += bullet_list([
        "<b>Banner verde de licença</b>: confirma que sua cópia é válida e mostra a versão atual.",
        "<b>Banner de atualização (quando há)</b>: avisa se há nova versão e o status do download.",
        "<b>Logo AuraBackTest</b>: clique para voltar à tela inicial.",
        "<b>Botão 📌 QuickStart</b>: painel lateral com atalhos para os fluxos mais comuns.",
        "<b>Botão Onboarding</b>: tour guiado pelas fases do app (útil na primeira semana).",
        "<b>Status do backend</b>: ponto verde = OK; vermelho = backend caiu, reinicie o app.",
    ])
    story.append(p("Abas principais", H2))
    story.append(kv_table([
        ("Começar", "Tela inicial com guia de fluxo e botão de diagnóstico do MT5."),
        ("Otimização ao vivo", "Coleta passes em tempo real enquanto o MT5 otimiza um EA."),
        ("Análise de Otimização", "Triagem: análise de robustez de vizinhança dos passes."),
        ("Backtest Aura", "Importa relatório HTM do MT5 para análise no app."),
        ("Backtest Individual", "Visão detalhada de um único backtest: KPIs, equity, robustez."),
        ("Portfólio", "Combinar múltiplos robôs e analisar correlação + PBO."),
        ("Walk-Forward", "Walk-Forward Analysis automático ponta-a-ponta."),
        ("Histórico", "Lista de todos os runs salvos no app."),
    ]))
    story.append(p("Navegação entre abas", H2))
    story.append(p(
        "Clique no nome da aba para alternar. Alguns botões dentro de uma aba "
        "levam você direto para outra (ex: &quot;Abrir análise&quot; no Histórico "
        "leva para Backtest Individual com o run já carregado)."
    ))
    story.append(p("Atalhos de teclado", H2))
    story.append(kv_table([
        ("Ctrl+Shift+I", "Abrir DevTools (modo desenvolvedor — útil para debugar)."),
        ("Ctrl+Shift+L", "Abrir pasta com logs do app."),
        ("Ctrl+R", "Recarregar a interface (mantém o backend rodando)."),
        ("Ctrl+P", "Imprimir a página atual (útil para salvar gráficos como PDF)."),
    ]))
    story.append(PageBreak())

    # ===== CAPÍTULO 5 =====
    story.append(section_header("5", "Aba Começar (Home)"))
    story.append(p(
        "A tela inicial é seu mapa de navegação. Ela mostra os <b>4 fluxos principais</b> "
        "do app em ordem natural de uso:"
    ))
    story += numbered_list([
        "<b>Otimização ao vivo</b> — você roda otimização no MT5, o app coleta os passes em tempo real e ranqueia por Sortino/Sharpe/AuraScore.",
        "<b>Análise de Otimização (Triagem)</b> — você seleciona os melhores passes e o app calcula robustez de vizinhança (parâmetros vizinhos também são lucrativos?).",
        "<b>Backtest Aura</b> — você importa o relatório HTM do MT5 do candidato escolhido.",
        "<b>Backtest Individual</b> — você analisa em profundidade um único backtest com toda a artilharia estatística do app.",
    ])
    story.append(p("Diagnóstico do MT5", H2))
    story.append(p(
        "Na Home há um botão <b>Diagnóstico do MT5</b> que verifica:"
    ))
    story += bullet_list([
        "Quantas instalações de MetaTrader 5 o app detectou no seu PC.",
        "Quais estão rodando agora (mostrado com ponto verde).",
        "Acesso à pasta comum (<code>%APPDATA%/MetaQuotes/Terminal/Common/Files</code>).",
        "Se o MetaEditor está disponível para auto-compilação de EAs.",
    ])
    story.append(tip(
        "Rode o diagnóstico ANTES de tentar usar Otimização ao vivo pela primeira vez. "
        "Ele identifica problemas comuns como: MT5 não detectado, pasta comum bloqueada por antivírus, MetaEditor não encontrado."
    ))
    story.append(PageBreak())

    # ===== CAPÍTULO 6 =====
    story.append(section_header("6", "Backtest Aura — importar relatório do MT5"))
    story.append(p("Quando usar esta aba", H2))
    story.append(p(
        "Sempre que você já tem um relatório de backtest do MT5 (arquivo <b>.htm</b>) e quer "
        "carregá-lo no AuraBackTest para análise."
    ))
    story.append(p("Passo a passo", H2))
    story.append(p("<b>No MetaTrader 5</b>:", H3))
    story += numbered_list([
        "Abra o MT5 e clique em <b>Visualizar</b> → <b>Testador de Estratégia</b> (ou pressione Ctrl+R).",
        "Selecione o EA, símbolo, timeframe, datas e modo (recomendamos <b>Cada tick baseado em ticks reais</b>).",
        "Clique em <b>Iniciar</b> e aguarde finalizar.",
        "Na aba <b>Relatório</b>, clique com botão direito → <b>Salvar como Relatório</b>.",
        "Salve como <b>.htm</b> em uma pasta de fácil acesso (ex: Documentos/Backtests/).",
    ])
    story.append(p("<b>No AuraBackTest</b>:", H3))
    story += numbered_list([
        "Vá para a aba <b>Backtest Aura</b>.",
        "Clique em <b>Selecionar arquivo</b> e escolha o arquivo .htm.",
        "Opcionalmente, preencha o <b>Nome / Label</b> (ex: &quot;BigSmall v2 EURUSD H1&quot;) para facilitar encontrar depois.",
        "Clique em <b>Importar e analisar</b>.",
        "Quando terminar, o app abre automaticamente o run na aba <b>Backtest Individual</b>.",
    ])
    story.append(tip(
        "Você pode renomear o label depois pela aba Histórico. "
        "Um nome descritivo no formato &quot;EA - Símbolo - Timeframe - Versão&quot; "
        "facilita muito a comparação entre runs."
    ))
    story.append(p("O que é extraído do .htm", H2))
    story += bullet_list([
        "<b>Parâmetros do EA</b>: todos os inputs com seus valores.",
        "<b>Métricas nativas do MT5</b>: net profit, profit factor, Sharpe (MT5), max drawdown, etc.",
        "<b>Lista completa de trades</b>: data/hora entrada e saída, lado, volume, preços, profit, swap, comissão.",
        "<b>Balance / equity por trade</b>: usado para construir as curvas do app.",
    ])
    story.append(warn(
        "O app calcula a maioria das métricas POR CONTA PRÓPRIA a partir dos trades brutos, "
        "porque o Sharpe nativo do MT5 é discrepante (usa cálculo simplificado). "
        "Os valores que você verá no Backtest Individual podem divergir ligeiramente do MT5 — "
        "os do app são os corretos para análise quantitativa."
    ))
    story.append(PageBreak())

    # ===== CAPÍTULO 7 =====
    story.append(section_header("7", "Backtest Individual — análise completa"))
    story.append(p(
        "Esta é a aba mais rica do app. Tudo o que pode ser dito sobre um backtest aparece aqui. "
        "Vamos passar por todas as seções na ordem em que aparecem na tela."
    ))

    story.append(p("Seletor de Run", H2))
    story.append(p(
        "No topo da página há um dropdown listando todos os runs salvos. "
        "Selecione para carregar o backtest. O run mais recentemente importado é "
        "selecionado por padrão."
    ))

    story.append(p("KPIs Principais (4 colunas)", H2))
    story.append(p(
        "16 cards mostrando as métricas-chave. Cada card tem um botão <b>?</b> ao "
        "lado do nome — passe o mouse para ver tradução em linguagem simples, "
        "faixas (ruim/bom/excelente) e como melhorar."
    ))
    story.append(p("As métricas mostradas:", BODY))
    story += bullet_list([
        "Lucro Líquido (R$ e %)",
        "Retorno Anual %",
        "Drawdown Máximo %",
        "Profit Factor",
        "Expectancy",
        "Payoff Ratio",
        "Win Rate (%)",
        "Sharpe Ratio",
        "Sortino Ratio",
        "SQN (Van Tharp)",
        "K-Ratio",
        "Recovery Factor",
        "Ulcer Index",
        "Calmar Ratio",
        "Total de Trades",
    ])

    story.append(p("Curva de Equity", H2))
    story.append(p(
        "Gráfico de linha mostrando a evolução do saldo ao longo do tempo. "
        "Linhas drawdown sombreadas em vermelho destacam visualmente os períodos negativos. "
        "Boas curvas têm <b>inclinação positiva consistente</b> e drawdowns curtos."
    ))

    story.append(p("Drawdown (%)", H2))
    story.append(p(
        "Gráfico complementar mostrando o % de queda do pico em cada momento. "
        "O Max DD aparece no topo do app. Use para identificar <b>quando</b> os "
        "DDs aconteceram (regime difícil? horário ruim?)."
    ))

    story.append(p("Análise Temporal", H2))
    story.append(p(
        "Quatro barras: lucro por hora do dia, por dia da semana, por mês e por ano. "
        "Identifica padrões: <i>&quot;sex-feira é o dia ruim&quot;</i>, <i>&quot;2 da tarde é horário de perdas&quot;</i>."
    ))
    story.append(tip(
        "Se ver padrão claro de perdas em horários/dias específicos, "
        "vá para a aba <b>What-If</b> (dentro de Backtest Individual) e simule "
        "a exclusão desses períodos para ver o impacto."
    ))

    story.append(p("MAE / MFE", H2))
    story.append(p(
        "<b>MAE</b> = Maximum Adverse Excursion = quanto o trade ficou no pior antes de fechar. "
        "<b>MFE</b> = Maximum Favorable Excursion = quanto chegou a ficar no melhor."
    ))
    story.append(p(
        "Scatter plot mostra profit × duração. Histograma mostra a distribuição de R-múltiplo "
        "(profit / risco). Se você converteu ticks reais, o app calcula MAE/MFE precisos por trade — "
        "permite saber se seu SL pode ser mais apertado (MAE pequeno = stop largo demais) "
        "ou se seu TP pode ser maior (MFE grande = está deixando lucro na mesa)."
    ))

    story.append(p("Long vs Short", H2))
    story.append(p(
        "Compara desempenho de operações compradas vs vendidas. "
        "Útil para detectar viés direcional: <i>&quot;só funciona em compra&quot;</i> "
        "ou <i>&quot;short tem profit factor 0.8&quot;</i>."
    ))

    story.append(p("Risk of Ruin", H2))
    story.append(p(
        "Tabela mostrando a probabilidade de quebrar a conta para diferentes níveis de risco por trade "
        "(0.5%, 1%, 2%, 5%). Calculado pela fórmula clássica usando win rate e payoff ratio."
    ))

    story.append(p("Stagnation", H2))
    story.append(p(
        "Gráfico de equity destacando períodos de <b>estagnação</b> (longos períodos sem novos picos). "
        "Mostra: máxima estagnação (em dias), média, % do tempo total em estagnação. "
        "Estagnação longa é tão dolorosa quanto DD profundo, mesmo sem perda nominal."
    ))

    story.append(p("Equity Control", H2))
    story.append(p(
        "Simulador de regras de gestão de risco aplicadas DURANTE o backtest:"
    ))
    story += bullet_list([
        "Parar após N losses consecutivos",
        "Parar após DD% atingir limite",
        "Reabrir o robô após X dias",
    ])
    story.append(p(
        "Mostra duas curvas sobrepostas: original vs controlada. "
        "Quando as regras ajudam, a curva controlada tem DD menor sem perder muito profit. "
        "Quando atrapalham, fica claro também — e você ajusta as regras."
    ))

    story.append(p("Validações Estatísticas (Simons-style)", H2))
    story.append(p(
        "6 testes inspirados nas práticas da Renaissance Technologies. Botão <b>Rodar validações</b> "
        "calcula e mostra o scorecard com PASS/FAIL para cada teste:"
    ))
    story += bullet_list([
        "<b>t-stat ≥ 2.5</b>: significância estatística do edge.",
        "<b>Ljung-Box</b>: sem autocorrelação nos retornos (independência).",
        "<b>Runs test</b>: wins e losses não clusterizados (aleatoriedade).",
        "<b>Outlier dependency</b>: lucrativo mesmo sem os top 5% trades.",
        "<b>Tail ratio</b>: P95 / |P5| ≥ 1 (assimetria favorável).",
        "<b>Jarque-Bera</b>: assimetria positiva (skew &gt; 0).",
    ])
    story.append(p(
        "Cada item tem botão <b>?</b> com explicação completa. Itens em FAIL mostram "
        "também uma sugestão de como melhorar (ex: <i>&quot;apertar stop loss para cortar cauda esquerda&quot;</i>)."
    ))

    story.append(p("Monte Carlo com Ticks Reais", H2))
    story.append(p(
        "Três simulações usando os ticks históricos reais (não retornos sintéticos):"
    ))
    story += bullet_list([
        "<b>Entry Jitter</b>: desloca timing de entrada em ±N segundos no histórico de tick. Mede sensibilidade a timing.",
        "<b>Spread Slippage</b>: usa o bid/ask real + pior caso para simular custo de execução.",
        "<b>Tick Return Bootstrap</b>: gera caminhos alternativos via block bootstrap dos retornos de tick.",
    ])
    story.append(p(
        "Pré-requisito: ter um arquivo Parquet de ticks. Use a aba <b>Backtest Aura</b> ou o botão "
        "<b>Converter ticks</b> dentro da MAE/MFE para gerar a partir de um CSV exportado do MT5."
    ))

    story.append(p("Suite de Robustez (Quant)", H2))
    story.append(p(
        "Scorecard completo com 15+ testes:"
    ))
    story += bullet_list([
        "PSR &gt; 95% (Probabilistic Sharpe)",
        "DSR &gt; 95% (Deflated Sharpe corrigindo multi-testing)",
        "MinTRL ≤ 500 trades",
        "Shuffle: prob lucro ≥ 90%",
        "Block bootstrap DD P95 &lt; 1.5× DD histórico",
        "Sobrevive a remoção de 20% dos trades (skip)",
        "Robusto a slippage ±25% (noise)",
        "Lucrativo em todos os anos testados (regime)",
        "Mais 6 testes estatísticos do scorecard Simons (acima)",
    ])
    story.append(tip(
        "Resultado final: scorecard verde (ROBUSTO), amarelo (ATENÇÃO) ou vermelho (FRÁGIL). "
        "Robôs FRÁGIL não devem ir para conta real — refaça a estratégia."
    ))

    story.append(p("Monte Carlo (Sintético)", H2))
    story.append(p(
        "Cinco modos rodando em paralelo:"
    ))
    story += bullet_list([
        "<b>Shuffle</b>: embaralha a ordem dos trades.",
        "<b>Bootstrap</b>: amostragem com reposição dos retornos.",
        "<b>Block Bootstrap</b>: preserva autocorrelação de streaks.",
        "<b>Skip</b>: remove aleatoriamente N% dos trades.",
        "<b>Noise</b>: aplica jitter de ±N% em cada profit (slippage simulada).",
    ])
    story.append(p(
        "Cada modo mostra: probabilidade de lucro, Net P5/P50/P95, DD P50/P95. "
        "P95 são os <b>casos pessimistas</b> que importam para dimensionamento de capital."
    ))

    story.append(p("What-If (em aba separada)", H2))
    story.append(p(
        "Simula a exclusão de horas/dias específicos para ver o impacto:"
    ))
    story += numbered_list([
        "Marca as horas que você quer excluir (0–23).",
        "Marca os dias da semana (segunda a domingo).",
        "Clica em <b>Simular</b>.",
        "Vê a comparação original vs filtrado — KPIs lado a lado, com deltas em %.",
    ])

    story.append(p("Money Management Simulator (aba separada)", H2))
    story.append(p(
        "Compara três estratégias de sizing aplicadas aos mesmos trades:"
    ))
    story += bullet_list([
        "<b>Lotes Fixos</b>: tamanho fixo por trade.",
        "<b>% do Capital</b>: tamanho proporcional ao capital atual (juros compostos).",
        "<b>Valor Fixo $</b>: risco em dinheiro constante por trade.",
    ])
    story.append(p(
        "Útil para responder: <i>&quot;vale mais a pena tamanho fixo ou compor?&quot;</i>. "
        "Depende do payoff ratio, sequência de wins/losses e tolerância a DD."
    ))
    story.append(PageBreak())

    # ===== CAPÍTULO 8 =====
    story.append(section_header("8", "Otimização ao vivo"))
    story.append(p("O que é", H2))
    story.append(p(
        "Em vez de rodar uma otimização no MT5, esperar horas, e SÓ ENTÃO importar o XML "
        "para análise, o AuraBackTest pode coletar os passes <b>em tempo real</b> conforme "
        "o MT5 vai testando combinações. Você acompanha o ranking sendo construído ao vivo."
    ))
    story.append(p(
        "Para isso, o app <b>instrumenta</b> seu EA com um pequeno código adicional "
        "(via include MQL5) que grava cada pass como JSON em uma pasta compartilhada. "
        "O watcher do app monitora essa pasta a cada 1 segundo."
    ))

    story.append(p("Passo a passo", H2))
    story.append(p("<b>Parte 1 — preparar o EA</b>", H3))
    story += numbered_list([
        "Vá para a aba <b>Otimização ao vivo</b>.",
        "Use o <b>InstallationPicker</b> para escolher MT5 e EA.",
        "Clique em <b>Instrumentar EA</b>.",
        "O app gera um novo arquivo <i>EuRoboNome_Aura.mq5</i> ao lado do original (não modifica o seu).",
        "Opcionalmente, marque <b>Compilar automaticamente</b> — o app chama o MetaEditor.",
        "Se preferir compilar manualmente: abra o arquivo gerado no MetaEditor → F7 (Compile).",
    ])
    story.append(p("<b>Parte 2 — iniciar coleta</b>", H3))
    story += numbered_list([
        "No mesmo painel, clique em <b>Iniciar coleta</b> — o app sobe o watcher.",
        "Você recebe um <b>session_id</b> e um label (pode renomear).",
        "Abra o MT5, vá em Testador de Estratégia.",
        "Selecione o EA <b>com sufixo _Aura</b> (versão instrumentada).",
        "Configure ranges de otimização normalmente e clique Iniciar.",
        "Volte ao AuraBackTest — a tabela começa a popular com passes em tempo real.",
    ])
    story.append(p("<b>Parte 3 — ranquear</b>", H3))
    story.append(p(
        "Conforme passes chegam, o app calcula <b>todas</b> as métricas avançadas "
        "(Sharpe, Sortino, Calmar, SQN, K-Ratio, etc) sem esperar o MT5 terminar."
    ))
    story.append(p(
        "O ranking padrão é por <b>AuraScore</b>:"
    ))
    story.append(p(
        "<b>AuraScore</b> = 40% Sortino + 30% Calmar + 20% (PF - 1) + 10% SQN",
        CODE,
    ))
    story.append(p(
        "Esse score é uma combinação ponderada que valoriza estratégias com Sortino consistente, "
        "Calmar saudável (retorno por DD), Profit Factor positivo e SQN alto. "
        "Pode ser alterado para ordenar por qualquer métrica."
    ))

    story.append(p("Quando parar e o que fazer", H2))
    story += bullet_list([
        "Aguarde o MT5 terminar (status no MT5 mostra %).",
        "Selecione os top N passes (~10) clicando nos checkboxes.",
        "Clique em <b>Abrir como runs</b> — cada pass vira um run individual analisável.",
        "Ou clique em <b>Enviar para Triagem</b> — leva os passes selecionados para a próxima aba (análise de vizinhança).",
    ])
    story.append(warn(
        "<b>Importante</b>: usar o EA <b>instrumentado</b> (com sufixo _Aura) é OBRIGATÓRIO. "
        "Se você esquecer e selecionar o original, a otimização roda mas o app não recebe nada. "
        "Olhe o status do watcher na lateral — ele indica 0 passes recebidos se a pasta está vazia."
    ))
    story.append(PageBreak())

    # ===== CAPÍTULO 9 =====
    story.append(section_header("9", "Análise de Otimização (Triagem)"))
    story.append(p("O que é", H2))
    story.append(p(
        "Depois que você tem um conjunto de passes (vindos de uma sessão ao vivo ou "
        "de um XML importado), a aba <b>Triagem</b> ajuda a separar os <b>verdadeiros vencedores</b> "
        "dos <b>vencedores por sorte</b>."
    ))
    story.append(p(
        "Princípio: estratégia robusta tem <b>vizinhança lucrativa</b>. "
        "Se o passe ótimo é P=42 e P=41 e P=43 também são bons, é robusto. "
        "Se só P=42 é bom e P=41 e P=43 são péssimos, é um pico isolado = overfit."
    ))
    story.append(p("Visualizações", H2))
    story.append(p("<b>Heatmap 2D</b>:", H3))
    story.append(p(
        "Mapa de calor de duas variáveis. Verde = lucro alto, vermelho = baixo. "
        "Regiões verdes <b>amplas e contíguas</b> são robustas; pontos verdes isolados são sorte."
    ))
    story.append(p("<b>Planet 3D</b>:", H3))
    story.append(p(
        "Scatter 3D de três variáveis. Permite girar e explorar interactivamente. "
        "Útil quando o robô tem 3 parâmetros sensíveis."
    ))
    story.append(p("<b>Parallel Coordinates</b>:", H3))
    story.append(p(
        "Cada pass é uma linha que cruza N eixos paralelos (um por parâmetro). "
        "Linhas brilhantes destacam configs lucrativas. Permite filtrar visualmente regiões do espaço."
    ))

    story.append(p("Robust Score normalizado", H2))
    story.append(p(
        "Cada pass recebe um score 0–100 baseado em métricas combinadas + vizinhança. "
        "Passes com Robust Score alto não só são bons sozinhos como também têm vizinhos bons."
    ))

    story.append(p("Filtros sugeridos", H2))
    story.append(p(
        "O sistema sugere automaticamente filtros para você aplicar:"
    ))
    story += bullet_list([
        "Net Profit &gt; X (mínimo de lucro)",
        "Max DD% &lt; Y (limite de DD)",
        "Sortino &gt; Z (qualidade do retorno por risco)",
        "Trades ≥ N (amostra mínima)",
    ])
    story.append(p(
        "Os valores são calculados a partir do percentil do dataset (sugere o P75 por padrão)."
    ))
    story.append(PageBreak())

    # ===== CAPÍTULO 10 =====
    story.append(section_header("10", "Portfólio — combinar robôs"))
    story.append(p("Quando usar", H2))
    story.append(p(
        "Você tem 2 ou mais robôs/configs e quer entender como eles se comportam <b>juntos</b>. "
        "Se eles fazem coisas diferentes, a combinação reduz risco. Se fazem a mesma coisa, "
        "você está só duplicando exposição."
    ))
    story.append(p("Como selecionar runs", H2))
    story += numbered_list([
        "Vá para a aba <b>Portfólio</b>.",
        "Na tabela superior, marque os checkboxes dos runs que quer combinar.",
        "Clique em <b>Analisar portfólio</b>.",
    ])
    story.append(p("O que o app calcula", H2))

    story.append(p("<b>Visão geral</b>:", H3))
    story.append(p(
        "KPIs do portfólio combinado: net profit, max DD%, Sharpe, profit factor, win rate, "
        "total de trades. Cada KPI tem botão ? com explicação."
    ))

    story.append(p("<b>Contribuição por run</b>:", H3))
    story.append(p(
        "Tabela mostrando trades e net profit de cada robô isoladamente. "
        "Identifica quem está puxando o resultado."
    ))

    story.append(p("<b>Matriz de correlação</b>:", H3))
    story.append(p(
        "Heatmap SVG simétrico onde verde = descorrelacionado, vermelho = correlacionado. "
        "Calculado sobre retornos diários sincronizados das equity curves."
    ))
    story.append(p("Três KPIs de diversificação acompanham:", BODY))
    story += bullet_list([
        "<b>Correlação média</b>: média das correlações fora da diagonal. &lt; 0.3 é bem diversificado.",
        "<b>Índice de diversificação</b>: 100% = totalmente descorrelacionado, 0% = redundância total.",
        "<b>Par mais correlacionado</b>: os 2 robôs com maior correlação — candidatos a redundância.",
    ])
    story.append(p(
        "Se o par mais correlacionado &gt; 0.6, um alerta automático sugere reduzir o peso de um dos dois."
    ))

    story.append(p("<b>PBO via CSCV</b>:", H3))
    story.append(p(
        "Botão <b>Calcular PBO (CSCV)</b> ao lado do botão de Analisar. "
        "Pega as equity curves dos runs selecionados, monta C(16,8) = 12.870 partições "
        "e calcula a probabilidade de overfitting. Mostra:"
    ))
    story += bullet_list([
        "<b>PBO %</b>: probabilidade do backtest ser overfit (verde &lt;25%, amarelo &lt;50%, vermelho &gt;50%).",
        "<b>Combinações CSCV</b>: número de partições testadas (sempre 12.870 com 16 subsets).",
        "<b>OOS rank médio</b>: percentil médio do vencedor IS no OOS. &gt;50% é bom.",
        "<b>Performance degradation</b>: slope IS→OOS. ≥0 é saudável.",
        "<b>Histograma de logits</b>: distribuição dos resultados das partições (verde = sem overfit, vermelho = overfit).",
    ])

    story.append(p("<b>Otimização de pesos</b>:", H3))
    story.append(p(
        "Se selecionou ≥ 2 runs, aparece um segundo card com slider de Max DD%. "
        "O app testa 4000 combinações de pesos via amostragem Dirichlet e retorna:"
    ))
    story += bullet_list([
        "<b>Baseline equal weights</b>: net profit + DD com pesos iguais.",
        "<b>Otimizado</b>: melhor combinação respeitando o teto de DD.",
        "<b>Ganho vs baseline (%)</b>: quanto a otimização melhorou.",
        "<b>Tabela de pesos ótimos</b>: % de capital alocado para cada robô.",
    ])
    story.append(p(
        "Se nenhuma combinação respeita o DD máximo configurado, o app retorna o de menor DD encontrado "
        "(com aviso vermelho)."
    ))

    story.append(p("<b>Scorecard de robustez (portfólio agregado)</b>:", H3))
    story.append(p(
        "Toda a suite de robustez aplicada ao portfólio combinado. Permite ver se a "
        "combinação dos robôs gera um sistema robusto, mesmo que cada um isolado seja "
        "marginal."
    ))
    story.append(PageBreak())

    # ===== CAPÍTULO 11 =====
    story.append(section_header("11", "Walk-Forward Analysis"))
    story.append(p("O que é", H2))
    story.append(p(
        "Walk-Forward é o padrão-ouro para validar estratégias otimizadas. O AuraBackTest "
        "roda o processo completo automaticamente:"
    ))
    story += numbered_list([
        "Divide o histórico em N folds.",
        "Para cada fold, otimiza no período IS (in-sample).",
        "Pega os top-N parâmetros e roda backtest no OOS (out-of-sample).",
        "Compara IS vs OOS e calcula scores de estabilidade.",
    ])
    story.append(p(
        "Cada OOS é salvo como um run individual, então você pode abrir cada um para análise detalhada."
    ))
    story.append(p("Configuração", H2))
    story += bullet_list([
        "<b>InstallationPicker</b>: MT5 + EA.",
        "<b>Símbolo</b> e <b>Timeframe</b>.",
        "<b>Data início</b> e <b>Data fim</b>.",
        "<b>Folds</b> (3–10): mais folds = mais validação mas mais lento.",
        "<b>OOS %</b> (10–40%): fração do fold reservada para validação.",
        "<b>Anchored</b>: se marcado, o IS começa sempre na origem e cresce (em vez de janelar).",
        "<b>Score key</b>: métrica que o app vai otimizar (profit factor, sharpe, sortino, etc).",
        "<b>Top-N</b>: quantos passes IS levam para OOS (1–5).",
    ])
    story.append(p("Resultado", H2))
    story.append(p(
        "Quando termina (pode levar horas), o app mostra três KPIs principais:"
    ))
    story += bullet_list([
        "<b>Stability Score</b>: razão OOS médio / IS médio. &gt;75% é robusto.",
        "<b>Consistency</b>: % dos folds OOS positivos. &gt;80% é consistente.",
        "<b>Degradation</b>: queda IS→OOS em %. &lt;30% é saudável.",
    ])
    story.append(p(
        "E uma tabela por fold com barras IS vs OOS coloridas (verde se OOS ≥ IS, vermelho se OOS &lt; IS), "
        "permitindo identificar quais folds foram mal."
    ))
    story.append(p(
        "Cada pass OOS tem botão para <b>abrir análise</b> — leva direto para Backtest Individual "
        "com todas as métricas e robustez do pass."
    ))
    story.append(warn(
        "WFA é caro computacionalmente. Para 4 folds com top-3 passes, são 4 otimizações + 12 backtests = "
        "pode levar 2-6 horas dependendo do EA e do tamanho do histórico. Recomendamos rodar à noite."
    ))
    story.append(PageBreak())

    # ===== CAPÍTULO 12 =====
    story.append(section_header("12", "Histórico"))
    story.append(p(
        "Lista persistente de todos os runs já importados ou gerados pelo app. "
        "Salvo em banco SQLite local — sobrevive a reinicializações e atualizações."
    ))
    story.append(p("Funcionalidades", H2))
    story += bullet_list([
        "<b>Tabela com colunas</b>: Nome/Label, Ativo, Timeframe, Fingerprint (hash dos params), Tipo (single/optimization/wfa_oos), Período, ID.",
        "<b>Filtro por tipo</b>: ver só single backtests, só WFA OOS, etc.",
        "<b>Renomear label</b>: clique no label → digite o novo → Enter.",
        "<b>Marcar favorito</b>: estrela ao lado do nome — favoritos sobem no topo.",
        "<b>Deletar</b>: ícone de lixeira no fim da linha. Pede confirmação.",
        "<b>Abrir análise</b>: clica em qualquer linha → vai para Backtest Individual com aquele run.",
    ])
    story.append(p("Fingerprint", H2))
    story.append(p(
        "Hash curto (8 chars) calculado a partir dos parâmetros do EA. "
        "Mesmo fingerprint = configurações idênticas. Útil para identificar duplicatas: "
        "se você importou o mesmo backtest duas vezes, eles aparecem com mesmo fingerprint."
    ))
    story.append(tip(
        "Use o filtro por tipo para encontrar rapidamente os runs WFA OOS — eles têm nome "
        "automático no formato <i>&quot;WFA fold#N OOS pass#M&quot;</i>."
    ))
    story.append(PageBreak())

    # ===== CAPÍTULO 13 =====
    story.append(section_header("13", "Tooltips (?) e ajuda contextual"))
    story.append(p(
        "Quase toda métrica e item de scorecard no app tem um botão circular <b>?</b> ao lado do nome. "
        "Passe o mouse sobre ele para abrir um tooltip com 4 seções:"
    ))
    story += numbered_list([
        "<b>Em linguagem simples</b>: o que aquela métrica/teste significa, sem jargão.",
        "<b>Faixas</b>: cores e valores para Ruim, Bom e Excelente.",
        "<b>💡 Como melhorar</b>: ações concretas para subir a métrica.",
        "<b>⚠️ Como não piorar</b>: armadilhas e regressões a evitar.",
    ])
    story.append(p(
        "Algumas métricas mostram também a <b>fórmula técnica</b> no rodapé do tooltip "
        "(Sharpe, SQN, t-stat, etc), para quem quiser ir mais fundo."
    ))
    story.append(tip(
        "Os tooltips são pensados para você usar como referência ao vivo enquanto analisa um robô. "
        "Não precisa decorar nada — está tudo disponível ao alcance do mouse."
    ))
    story.append(PageBreak())

    # ===== CAPÍTULO 14 =====
    story.append(section_header("14", "Glossário completo de métricas"))
    story.append(p("KPIs de performance", H2))
    story.append(metric_table([
        ("Net Profit", "Soma de todos os profits dos trades.", "&lt; 0 / +30% do capital", "&gt; 100%"),
        ("Annual Return %", "Retorno anualizado pelo período testado.", "&lt; 10% / 20–50%", "&gt; 50%"),
        ("Max Drawdown %", "Maior queda do pico ao fundo.", "&gt; 25% / 10–20%", "&lt; 10%"),
        ("Profit Factor", "Total ganho ÷ total perdido.", "&lt; 1.3 / 1.5–2.0", "&gt; 2.5"),
        ("Sharpe Ratio", "Retorno por unidade de volatilidade.", "&lt; 0.8 / 1.0–1.5", "&gt; 2.0"),
        ("Sortino Ratio", "Sharpe penalizando só volatilidade negativa.", "&lt; 1.0 / 1.5–2.5", "&gt; 3.0"),
        ("Calmar Ratio", "Retorno anualizado ÷ Max DD%.", "&lt; 0.5 / 1.0–2.0", "&gt; 3.0"),
        ("Win Rate", "% de trades vencedores (depende do tipo de estratégia).", "trend 30-45% / mr 55-70%", "depende"),
        ("Payoff Ratio", "Ganho médio ÷ perda média.", "&lt; 0.3 / 0.5–1.5", "&gt; 2.0"),
        ("Expectancy", "Lucro esperado por trade (média ponderada).", "&lt; 0 / 0–0.1× SL", "&gt; 0.3× SL"),
        ("Recovery Factor", "Net profit ÷ Max DD.", "&lt; 1.5 / 2.5–5", "&gt; 7"),
        ("SQN (Van Tharp)", "Qualidade geral do sistema (0–10).", "&lt; 1.6 / 2.5–3.5", "&gt; 5.0"),
        ("K-Ratio", "Consistência da inclinação da equity.", "&lt; 0.5 / 0.7–1.0", "&gt; 1.5"),
        ("Ulcer Index", "Dor dos DDs ao longo do tempo (menor = melhor).", "&gt; 10 / 2–5", "&lt; 2"),
    ]))

    story.append(p("Métricas de robustez", H2))
    story.append(metric_table([
        ("PSR", "Prob. do Sharpe real ser > 0 (considera skew/kurt).", "&lt; 90% / 90–95%", "&gt; 95%"),
        ("DSR", "PSR corrigido para multi-testing.", "&lt; 90% / 90–95%", "&gt; 95%"),
        ("MinTRL", "Trades necessários para 95% confiança de edge.", "&gt; 2000 / 500–1500", "≤ 500"),
        ("PBO via CSCV", "Probabilidade de backtest overfit.", "&gt; 50% / 25–50%", "&lt; 25%"),
        ("Stability Score", "OOS ÷ IS no Walk-Forward.", "&lt; 50% / 50–75%", "&gt; 75%"),
        ("Consistency", "% folds OOS positivos.", "&lt; 60% / 60–80%", "&gt; 80%"),
        ("Degradation", "Queda IS→OOS em %.", "&gt; 60% / 30–60%", "&lt; 30%"),
        ("Avg Correlation", "Correlação média entre robôs.", "&gt; 0.6 / 0.3–0.6", "&lt; 0.3"),
        ("Diversification %", "100% = descorrelacionado.", "&lt; 40% / 40–70%", "&gt; 70%"),
    ]))

    story.append(p("Distribuição dos retornos", H2))
    story.append(metric_table([
        ("Skewness", "Assimetria. Positiva é desejável.", "&lt; -0.5 / -0.5 a 0.5", "&gt; 1.0"),
        ("Excess Kurtosis", "Fat tails (eventos extremos).", "&gt; 20 / 3–10", "0–3"),
        ("t-stat", "Significância estatística do edge.", "&lt; 2.0 / 2.0–2.5", "&gt; 2.5"),
        ("Tail Ratio", "P95 ÷ |P5| (assimetria das caudas).", "&lt; 0.8 / 0.8–1.2", "&gt; 1.5"),
    ]))
    story.append(PageBreak())

    # ===== CAPÍTULO 15 =====
    story.append(section_header("15", "Interpretando o scorecard de robustez"))
    story.append(p(
        "O scorecard é o resumo mais importante de qualquer análise. Tem três status finais:"
    ))
    story.append(kv_table([
        ("🟢 ROBUSTO", "Todos os testes passaram. Estratégia pronta para validação final em conta demo."),
        ("🟡 ATENÇÃO", "1-2 testes falharam. Avaliar qual e decidir se é tolerável (ex: regime ruim em 1 ano específico)."),
        ("🔴 FRÁGIL", "Mais de 2 testes falharam. Não levar para conta real. Reformular a estratégia."),
    ]))
    story.append(p("Como ler cada teste em FAIL", H2))
    story.append(p(
        "Clique no item para expandir e ver: a nota técnica + a sugestão de como melhorar. "
        "Cada sugestão é específica para o que aquele teste mediu. Exemplos:"
    ))
    story += bullet_list([
        "<b>PSR baixo</b> → rodar em período maior, ajustar SL/TP para gerar skew positivo.",
        "<b>DSR baixo</b> → reduzir espaço de busca da otimização (menos parâmetros).",
        "<b>Shuffle baixo</b> → lucro depende de ordem específica; verificar outlier dependency.",
        "<b>Block bootstrap DD alto</b> → dimensionar capital para o P95, não para o histórico.",
        "<b>Skip test baixo</b> → endurecer filtros de entrada, MAE/MFE analysis.",
        "<b>Noise test baixo</b> → operar ativos mais líquidos, evitar baixa liquidez.",
        "<b>Regime test em ano negativo</b> → adicionar filtro de regime ou estratégia complementar.",
    ])
    story.append(p("Combinações típicas e o que indicam", H2))
    story.append(p("<b>PSR alto + DSR baixo</b>", H3))
    story.append(p(
        "Você otimizou DEMAIS. O Sharpe parece bom mas, considerando que você testou centenas de candidatos, "
        "ele perde significância. Solução: pegar top-5 e analisar média/desvio, em vez de single best."
    ))
    story.append(p("<b>Shuffle alto + Outlier dependency baixo</b>", H3))
    story.append(p(
        "Um ou poucos trades enormes carregam o sistema. Sem eles, o resto é mediano. "
        "Risco: esses outliers podem nunca se repetir (foram sorte ou condição específica). "
        "Solução: estudar o que esses trades têm em comum e replicar o setup. Se for irreplicável, sistema é frágil."
    ))
    story.append(p("<b>Block bootstrap DD muito alto + Sharpe alto</b>", H3))
    story.append(p(
        "Estratégia funciona, mas tem streaks de losses longos. O DD futuro pode ser muito pior. "
        "Solução: equity control (parar após N losses), reduzir position size, ou aceitar e dimensionar capital."
    ))
    story.append(p("<b>Skew negativo + Kurt alto</b>", H3))
    story.append(p(
        "Distribuição tóxica: perdas extremas raras mas catastróficas. Típico de venda de prêmio (martingale, anti-trend sem stop). "
        "Solução: apertar SL drasticamente, ou abandonar estratégia."
    ))
    story.append(PageBreak())

    # ===== CAPÍTULO 16 =====
    story.append(section_header("16", "Workflows recomendados"))

    story.append(p("Workflow 1 — Validando um robô que você já tem", H2))
    story += numbered_list([
        "Rode o backtest do robô no MT5 com ticks reais (modo &quot;Cada tick baseado em ticks reais&quot;).",
        "Salve o relatório como .htm.",
        "Importe no AuraBackTest pela aba <b>Backtest Aura</b>.",
        "Veja KPIs principais. Se Sharpe &lt; 1.0 ou DD &gt; 30%, é vermelho — não vale a pena prosseguir.",
        "Rode a <b>Suite de Robustez</b>. Se vier verde, prossiga. Se amarelo, avalie quais testes falharam. Se vermelho, refaça.",
        "Rode as <b>Validações Estatísticas (Simons)</b>. Mesmas regras: verde = ok, vermelho = problema.",
        "Se você tem ticks convertidos, rode <b>Monte Carlo com Ticks Reais</b>. Veja se sobrevive a slippage real.",
        "Use <b>What-If</b> para testar exclusão de horários ruins identificados na Análise Temporal.",
        "Aprovado? Vá para conta demo e compare resultados live com backtest (a aba <b>Forward Compare</b> faz isso).",
    ])

    story.append(p("Workflow 2 — Encontrando um novo robô via otimização", H2))
    story += numbered_list([
        "Vá para <b>Otimização ao vivo</b>. Instrumente seu EA template.",
        "Inicie a coleta. Rode otimização no MT5 com ranges amplos.",
        "Conforme passes chegam, ordene por <b>AuraScore</b>.",
        "Selecione os top 10 → <b>Enviar para Triagem</b>.",
        "Na Triagem, use Heatmap 2D para validar vizinhança. Descarte picos isolados.",
        "Pegue os top 3 da Triagem → <b>Abrir como runs</b>.",
        "Para cada um, vá para Backtest Individual e rode <b>Suite de Robustez</b>.",
        "Os que passarem o scorecard, leve para <b>Walk-Forward Analysis</b> como validação final.",
        "O que sobreviver ao WFA com Stability Score &gt; 75% e Consistency &gt; 80% é o candidato real.",
    ])

    story.append(p("Workflow 3 — Construindo um portfólio de robôs", H2))
    story += numbered_list([
        "Tenha pelo menos 3 robôs aprovados nos workflows acima.",
        "Vá para a aba <b>Portfólio</b>.",
        "Selecione todos eles → <b>Analisar portfólio</b>.",
        "Olhe a <b>Matriz de Correlação</b>. Se houver pares &gt; 0.6, considere remover um.",
        "Veja o <b>Índice de Diversificação</b> — almeje &gt; 60%.",
        "Rode <b>Calcular PBO (CSCV)</b>. PBO &lt; 25% confirma que o conjunto não é overfit.",
        "Use <b>Otimização de pesos</b> com max DD% saudável (ex: 15%).",
        "O resultado &quot;Otimizado&quot; é seu mix recomendado. Compare com baseline (pesos iguais)."
    ])

    story.append(p("Workflow 4 — Diagnóstico de robô em queda", H2))
    story += numbered_list([
        "Importe o backtest do período recente.",
        "Compare com backtest do período de glória (use dois runs separados).",
        "Veja Análise Temporal: o pad raão de hora/dia mudou?",
        "Veja MAE/MFE: o SL ainda está adequado?",
        "Rode a Suite: novos itens em FAIL? Quais regrediram?",
        "Use <b>Forward Compare</b> com trades reais — está dentro do esperado pelo Monte Carlo P5?",
        "Se sim, é flutuação normal — aguarde mais trades. Se não, mercado mudou de regime."
    ])
    story.append(PageBreak())

    # ===== CAPÍTULO 17 =====
    story.append(section_header("17", "Solução de problemas (FAQ)"))

    story.append(p("O app não abre / fica em &quot;Iniciando serviços&quot;", H2))
    story.append(p(
        "Provavelmente a porta 8765 está sendo usada por outro programa. Soluções:"
    ))
    story += bullet_list([
        "Reinicie o computador (resolve em 90% dos casos).",
        "Veja em Gerenciador de Tarefas se há um processo <i>AuraBackTestServer.exe</i> rodando órfão; encerre-o.",
        "Em último caso, use Ctrl+Shift+L para abrir os logs e veja qual erro aparece.",
    ])

    story.append(p("Detecção de MT5 não encontra minhas instalações", H2))
    story += bullet_list([
        "Verifique se a instalação está em Program Files / Program Files (x86).",
        "Se você instalou em local custom, abra o MT5 pelo menos uma vez para criar o data folder em %APPDATA%.",
        "Antivírus pode bloquear acesso a %APPDATA%/MetaQuotes — adicione exceção.",
    ])

    story.append(p("Otimização ao vivo não recebe nenhum pass", H2))
    story += bullet_list([
        "Está rodando o EA <b>instrumentado</b> (sufixo _Aura)? É obrigatório.",
        "Pasta comum existe? <code>%APPDATA%/MetaQuotes/Terminal/Common/Files/AuraBackTest/</code>",
        "Antivírus pode estar deletando os JSONs assim que são criados — desabilite temporariamente para testar.",
        "Watcher está rodando? Verifique o status no painel lateral da aba Live.",
    ])

    story.append(p("Monte Carlo com Ticks Reais falha", H2))
    story += bullet_list([
        "Você precisa de um arquivo Parquet de ticks. Converta primeiro pelo botão na seção MAE/MFE.",
        "Para conversão, exporte CSV do MT5 (Símbolos → botão direito → Exportar ticks).",
        "Arquivo Parquet pode ficar em qualquer pasta — informe o path no app.",
    ])

    story.append(p("Importação de HTM falha com erro de parser", H2))
    story += bullet_list([
        "Geralmente é HTM antigo de MT5 build &lt; 3000 com formato diferente. Re-rode o backtest no MT5 atual.",
        "HTMs editados manualmente quebram o parser — sempre use o arquivo original do MT5.",
        "Se persistir, abra logs (Ctrl+Shift+L) e envie o erro para suporte com o arquivo HTM anexo.",
    ])

    story.append(p("Walk-Forward muito lento", H2))
    story += bullet_list([
        "Cada fold = 1 otimização + N backtests. Para 5 folds × 3 top-N = 5 otimizações + 15 backtests.",
        "Reduza folds para 3 e top-N para 2 se quiser teste mais rápido.",
        "Use timeframe maior (H1 em vez de M5) — reduz tempo de processamento do MT5.",
    ])

    story.append(p("Diferença entre Sharpe do MT5 e do app", H2))
    story.append(p(
        "Esperada. O MT5 usa cálculo simplificado de Sharpe (sem anualização correta, sem ajuste de skew). "
        "O app usa cálculo padrão da literatura quantitativa. Confie no Sharpe do app."
    ))

    story.append(p("App ficou desatualizado", H2))
    story.append(p(
        "Veja o banner azul de update no topo. Se não aparecer, clique em <i>Checar atualização</i> no banner verde de licença. "
        "Se mesmo assim não atualizar, baixe a versão mais recente manualmente do site oficial."
    ))
    story.append(PageBreak())

    # ===== CAPÍTULO 18 =====
    story.append(section_header("18", "Atualizações automáticas"))
    story.append(p(
        "O AuraBackTest tem sistema de auto-update integrado. Fluxo:"
    ))
    story += numbered_list([
        "<b>Verificação</b>: ao abrir e a cada 30 minutos, o app consulta o servidor para checar nova versão.",
        "<b>Download em background</b>: se há nova versão, o download começa automaticamente sem interromper você.",
        "<b>Notificação</b>: quando o download termina, um banner azul aparece dizendo <i>&quot;Atualização X.Y.Z pronta — reinicie&quot;</i>.",
        "<b>Instalação</b>: feche o app normalmente. A versão nova é instalada silenciosamente. Na próxima abertura, você já está usando a versão atualizada.",
    ])
    story.append(p("Histórico de versões", H2))
    story.append(p(
        "Para ver o que mudou entre versões, visite:"
    ))
    story.append(p("<font color='#58a6ff'>https://github.com/thiagobelopasa/AuraBackTest/releases</font>", CODE))
    story.append(p(
        "Cada release tem notas detalhadas com features, fixes e melhorias."
    ))
    story.append(p("Desabilitar auto-update", H2))
    story.append(p(
        "Não é recomendado, mas se quiser: vá em <code>%APPDATA%/AuraBackTest/config.json</code> "
        "e adicione <code>&quot;autoUpdate&quot;: false</code>. Reabra o app."
    ))
    story.append(PageBreak())

    # ===== CAPÍTULO 19 =====
    story.append(section_header("19", "Suporte e contato"))
    story.append(p("Como obter ajuda", H2))
    story.append(p(
        "Antes de pedir suporte, tente:"
    ))
    story += numbered_list([
        "Procurar a resposta neste manual (especialmente capítulo 17 - FAQ).",
        "Passar o mouse sobre o botão <b>?</b> da métrica em questão.",
        "Reiniciar o app e tentar novamente.",
        "Abrir os logs (Ctrl+Shift+L) e ler as últimas linhas — frequentemente o erro está autoexplicativo.",
    ])
    story.append(p("Reportando problema", H2))
    story.append(p(
        "Se nada resolveu, envie email para:"
    ))
    story.append(p("<b>thiago.belo.pasa@gmail.com</b>", BODY))
    story.append(p(
        "<b>Inclua na mensagem</b>:"
    ))
    story += bullet_list([
        "Versão do AuraBackTest (visível no banner verde superior).",
        "Versão do MT5 (Visualizar → Sobre).",
        "Descrição do problema e passos para reproduzir.",
        "Screenshot da tela com o erro.",
        "Anexo do log (pasta aberta via Ctrl+Shift+L).",
    ])
    story.append(p("Sugestões de melhoria", H2))
    story.append(p(
        "O AuraBackTest evolui rápido. Sugestões são <b>bem-vindas</b>. "
        "Mande email com o assunto &quot;Sugestão: [resumo]&quot;. "
        "Ideias acionáveis costumam entrar em uma versão menor (2-4 semanas)."
    ))
    story.append(p("Garantia da licença", H2))
    story.append(p(
        "A licença é <b>vitalícia</b>. Isso significa:"
    ))
    story += bullet_list([
        "Você não paga mensalidade.",
        "Você recebe todas as atualizações de v0.X.Y para sempre.",
        "Você pode usar em quantos computadores quiser (single-user).",
        "Se mudar de PC, basta baixar e instalar de novo.",
    ])
    story.append(p("Limitações", H2))
    story += bullet_list([
        "O suporte é por email, em horário comercial brasileiro (resposta em até 48h úteis).",
        "Não há suporte por WhatsApp ou telefone — todas as interações documentadas por email.",
        "Customizações específicas para o seu caso (ex: novo cálculo de métrica) são avaliadas caso a caso e podem ter custo adicional.",
        "Versões anteriores a v0.5.0 não têm garantia de compatibilidade com features novas.",
    ])
    story.append(Spacer(1, 2 * cm))
    story.append(p(
        "<i>Boas análises, e que seus robôs sobrevivam no real!</i>",
        ParagraphStyle("italic", parent=BODY, alignment=1, fontSize=12, textColor=GREEN),
    ))
    story.append(p(
        "— Equipe AuraBackTest",
        ParagraphStyle("italic2", parent=BODY, alignment=1, fontSize=11, textColor=MUTED, spaceBefore=8),
    ))

    return story


# ─────────────────────────────────────────────────────────────────────────────
# Build
# ─────────────────────────────────────────────────────────────────────────────
def build_pdf():
    doc = SimpleDocTemplate(
        str(OUTPUT_PATH),
        pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title="AuraBackTest — Manual do Usuário",
        author="Thiago Belopasa",
    )
    story = build_content()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"PDF gerado: {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    build_pdf()
