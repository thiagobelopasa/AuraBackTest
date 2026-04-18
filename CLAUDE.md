# AuraBackTest

## Visão Geral
App web para backtesting de estratégias de trading. Permite ao usuário configurar parâmetros de uma estratégia, rodá-la sobre dados históricos e visualizar os resultados (retorno, drawdown, gráficos de equity curve).

## Stack Tecnológica

### Backend (Python)
- **FastAPI** — API REST
- **pandas** — manipulação de dados financeiros
- **numpy** — cálculos numéricos
- **yfinance** — download de dados históricos gratuitos
- **vectorbt** — motor de backtesting vetorizado (rápido)
- **uvicorn** — servidor ASGI

### Frontend (JavaScript)
- **React + Vite** — interface do usuário
- **Recharts** — gráficos (equity curve, drawdown)
- **Tailwind CSS** — estilização
- **Axios** — chamadas HTTP para o backend

### Ambiente
- Python 3.11+
- Node.js 18+
- Estrutura: monorepo com pastas `/backend` e `/frontend`

## Estrutura de Pastas
```
AuraBackTest/
├── backend/
│   ├── main.py              # Ponto de entrada FastAPI
│   ├── routers/             # Rotas da API (backtest, dados, estratégias)
│   ├── services/            # Lógica de negócio (backtesting engine)
│   ├── models/              # Schemas Pydantic
│   ├── requirements.txt
│   └── .env                 # Variáveis de ambiente (NÃO commitar)
├── frontend/
│   ├── src/
│   │   ├── components/      # Componentes React reutilizáveis
│   │   ├── pages/           # Páginas (Home, Resultado, Histórico)
│   │   ├── services/        # Chamadas à API
│   │   └── App.jsx
│   ├── package.json
│   └── vite.config.js
├── CLAUDE.md
├── .claudeignore
├── .gitignore
└── README.md
```

## Comandos Essenciais

### Backend
```bash
cd backend
pip install -r requirements.txt   # Instalar dependências
uvicorn main:app --reload          # Rodar em desenvolvimento
```

### Frontend
```bash
cd frontend
npm install                        # Instalar dependências
npm run dev                        # Rodar em desenvolvimento (porta 5173)
```

## Convenções de Código

### Python
- Usar type hints em todas as funções
- Schemas Pydantic para validação de entrada/saída
- Funções puras para a lógica de backtesting (sem side effects)
- Nomear arquivos em snake_case

### JavaScript/React
- Componentes funcionais com hooks (sem class components)
- Named exports (não default exports para componentes)
- Nomear componentes em PascalCase, arquivos em camelCase
- Usar async/await, nunca .then() encadeados

## Regras Importantes
- NUNCA modificar arquivos em `/backend/.env` — contém chaves privadas
- NUNCA commitar o arquivo `.env`
- Sempre rodar `pip freeze > requirements.txt` após instalar nova lib Python
- Sempre rodar `npm run build` antes de considerar uma feature pronta no frontend
- Dados de mercado vêm via yfinance (gratuito, sem API key)

## Funcionalidades Planejadas
1. Seleção de ativo (ex: PETR4.SA, AAPL, BTC-USD)
2. Configuração de estratégia (médias móveis, RSI, MACD, etc.)
3. Definição de período (data início / fim)
4. Execução do backtest
5. Visualização de resultados: retorno total, Sharpe ratio, max drawdown
6. Gráfico de equity curve interativo
7. Tabela de trades executados
