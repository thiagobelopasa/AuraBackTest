from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AuraBackTest API",
    description="Motor de backtesting de estratégias de trading",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend Vite
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "AuraBackTest API rodando", "version": "0.1.0"}

@app.get("/health")
def health():
    return {"status": "ok"}
