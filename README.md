# AuraBackTest

App web para backtesting de estratégias de trading.

## Como rodar

### Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn main:app --reload
```
API disponível em: http://localhost:8000

### Frontend
```bash
cd frontend
npm install
npm run dev
```
App disponível em: http://localhost:5173

## Stack
- Backend: Python + FastAPI + vectorbt + yfinance
- Frontend: React + Vite + Recharts + Tailwind CSS
