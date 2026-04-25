@echo off
REM =========================================================
REM  AuraBackTest - Launcher Web (so precisa de Python)
REM
REM  Este launcher e simplificado: roda backend Python que ja
REM  serve o frontend (nao precisa instalar Node.js).
REM
REM  Requisitos:
REM  - Python 3.11 ou mais recente
REM  - MetaTrader 5 instalado (pra detectar instalacoes/ticks)
REM =========================================================
setlocal
cd /d "%~dp0"

title AuraBackTest Web

echo.
echo ============================================================
echo   AuraBackTest Web - iniciando...
echo ============================================================
echo.

REM -------------------- Verificar Python --------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado no PATH.
    echo Instale Python 3.11+ em https://www.python.org/downloads/
    echo Marque a opcao "Add python.exe to PATH" durante a instalacao.
    pause
    exit /b 1
)

REM -------------------- Criar venv se nao existe --------------------
if not exist "backend\.venv\Scripts\python.exe" (
    echo [backend] criando ambiente virtual...
    pushd backend
    python -m venv .venv
    if errorlevel 1 (
        echo [ERRO] falha ao criar venv.
        pause
        exit /b 1
    )
    call .venv\Scripts\activate.bat
    echo [backend] instalando dependencias ^(pode levar alguns minutos na primeira vez^)...
    python -m pip install --upgrade pip --quiet
    python -m pip install -r requirements.txt
    popd
)

REM -------------------- Verificar frontend built --------------------
if not exist "frontend\dist\index.html" (
    echo [ERRO] frontend\dist nao encontrado.
    echo Este pacote deveria vir com o frontend ja compilado.
    echo Reobtenha o zip original ou rode:
    echo   cd frontend ^& npm install ^& npm run build
    pause
    exit /b 1
)

echo.
echo [ok] Tudo pronto. Subindo servidor...
echo.

REM -------------------- Abrir browser em 4s --------------------
start "" cmd /c "timeout /t 4 /nobreak >nul && start http://localhost:8000/app"

REM -------------------- Subir backend (serve API + frontend) --------------------
cd backend
call .venv\Scripts\activate.bat
echo Backend rodando em http://localhost:8000
echo Frontend em       http://localhost:8000/app
echo.
echo Pressione Ctrl+C pra encerrar.
echo ============================================================
python -m uvicorn main:app --host 127.0.0.1 --port 8000
