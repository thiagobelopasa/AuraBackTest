@echo off
REM =========================================================
REM  AuraBackTest - starter
REM  Sobe backend (FastAPI) + frontend (Vite) e abre o navegador.
REM  Na primeira execução, cria venv + npm install (pode demorar).
REM =========================================================
setlocal
cd /d "%~dp0"

title AuraBackTest - Launcher

echo.
echo ============================================================
echo   AuraBackTest - iniciando...
echo ============================================================
echo.

REM -------------------- Backend (venv + deps) --------------------
if not exist "backend\.venv\Scripts\python.exe" (
    echo [backend] criando ambiente virtual...
    pushd backend
    python -m venv .venv
    if errorlevel 1 (
        echo [erro] falha ao criar venv. Python 3.11+ instalado?
        pause
        exit /b 1
    )
    call .venv\Scripts\activate.bat
    echo [backend] instalando dependencias...
    python -m pip install --upgrade pip --quiet
    python -m pip install -r requirements.txt
    popd
)

REM -------------------- Frontend (node_modules) --------------------
if not exist "frontend\node_modules" (
    echo [frontend] instalando dependencias...
    pushd frontend
    call npm install
    popd
)

echo.
echo [ok] dependencias prontas. Subindo servicos...
echo.

REM -------------------- Start backend em janela nova --------------------
start "AuraBackTest Backend" cmd /k "cd /d %~dp0backend && call .venv\Scripts\activate.bat && python -m uvicorn main:app --reload --port 8000"

REM -------------------- Start frontend em janela nova --------------------
start "AuraBackTest Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

REM -------------------- Espera o Vite subir e abre o browser --------------------
timeout /t 5 /nobreak >nul
start "" "http://localhost:5173"

echo.
echo ============================================================
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5173
echo ============================================================
echo   Para parar: feche as duas janelas abertas (Backend/Frontend)
echo ============================================================
echo.
timeout /t 3 /nobreak >nul
exit /b 0
