@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title AuraBackTest Web

echo.
echo ============================================================
echo   AuraBackTest Web
echo ============================================================
echo.

REM =========================================================
REM  1. Verificar se Python 3.11+ esta disponivel no PATH
REM =========================================================
set PYTHON_OK=0
set PYTHON_CMD=

REM Tenta "python" primeiro
python --version >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=2" %%V in ('python --version 2^>^&1') do set PY_VER=%%V
    REM Extrai major.minor
    for /f "tokens=1,2 delims=." %%A in ("!PY_VER!") do (
        set PY_MAJOR=%%A
        set PY_MINOR=%%B
    )
    if !PY_MAJOR! GEQ 3 (
        if !PY_MINOR! GEQ 11 (
            set PYTHON_OK=1
            set PYTHON_CMD=python
        )
    )
)

REM Se nao encontrou, tenta "py" (launcher oficial do Windows)
if !PYTHON_OK! EQU 0 (
    py -3.11 --version >nul 2>&1
    if not errorlevel 1 (
        set PYTHON_OK=1
        set PYTHON_CMD=py -3.11
    )
)

REM =========================================================
REM  2. Python nao encontrado ou versao antiga -> oferecer instalacao
REM =========================================================
if !PYTHON_OK! EQU 0 (
    echo [AVISO] Python 3.11+ nao foi encontrado ou nao esta no PATH.
    echo.

    REM Verifica se winget esta disponivel (Windows 10 21H1+ / Windows 11)
    winget --version >nul 2>&1
    if not errorlevel 1 (
        echo O Python sera instalado automaticamente via winget.
        echo Isso pode levar alguns minutos...
        echo.
        winget install --id Python.Python.3.11 --source winget --silent --accept-package-agreements --accept-source-agreements
        if errorlevel 1 (
            echo [ERRO] Falha na instalacao automatica via winget.
            goto :MANUAL_INSTALL
        )

        REM Atualiza PATH da sessao atual para incluir Python recem-instalado
        for /f "usebackq tokens=*" %%P in (`powershell -NoProfile -Command "[System.Environment]::GetEnvironmentVariable('PATH','Machine') + ';' + [System.Environment]::GetEnvironmentVariable('PATH','User')"`) do (
            set PATH=%%P
        )

        REM Confirma instalacao
        python --version >nul 2>&1
        if not errorlevel 1 (
            set PYTHON_OK=1
            set PYTHON_CMD=python
            echo [ok] Python instalado com sucesso!
        ) else (
            REM winget instala mas o PATH so vale no proximo terminal
            REM Tenta localizar o executavel diretamente
            for /f "tokens=*" %%F in ('where /r "%LOCALAPPDATA%\Programs\Python" python.exe 2^>nul') do (
                set PYTHON_CMD=%%F
                set PYTHON_OK=1
            )
            if !PYTHON_OK! EQU 0 (
                for /f "tokens=*" %%F in ('where /r "%ProgramFiles%\Python311" python.exe 2^>nul') do (
                    set PYTHON_CMD=%%F
                    set PYTHON_OK=1
                )
            )
            if !PYTHON_OK! EQU 1 (
                echo [ok] Python encontrado em: !PYTHON_CMD!
            ) else (
                echo [AVISO] Instalacao concluida mas Python nao esta no PATH ainda.
                echo Por favor, feche este janela e abra novamente o .bat.
                pause
                exit /b 1
            )
        )
    ) else (
        :MANUAL_INSTALL
        echo Para instalar Python manualmente:
        echo   1. Acesse https://www.python.org/downloads/
        echo   2. Baixe Python 3.11 ou mais recente
        echo   3. Execute o instalador marcando "Add python.exe to PATH"
        echo   4. Reabra este arquivo
        echo.
        start https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

echo [ok] Python encontrado: !PYTHON_CMD!

REM =========================================================
REM  3. Verificar se python esta em PATH corretamente (teste
REM     de import de modulos basicos)
REM =========================================================
!PYTHON_CMD! -c "import sys; assert sys.version_info >= (3,11), 'versao antiga'" >nul 2>&1
if errorlevel 1 (
    echo [AVISO] A versao do Python no PATH e mais antiga que 3.11.
    echo Por favor, instale Python 3.11+ e garanta que e o primeiro no PATH.
    echo.
    echo Dica: abra o Painel de Controle > Variaveis de Ambiente e coloque
    echo o Python 3.11 antes das outras versoes em "Path".
    pause
    exit /b 1
)

REM =========================================================
REM  4. Criar venv se nao existe
REM =========================================================
if not exist "backend\.venv\Scripts\python.exe" (
    echo.
    echo [backend] Criando ambiente virtual...
    pushd backend
    !PYTHON_CMD! -m venv .venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar venv. Verifique permissoes ou reinstale o Python.
        pause
        exit /b 1
    )
    echo [backend] Instalando dependencias (pode levar alguns minutos na primeira vez)...
    call .venv\Scripts\python.exe -m pip install --upgrade pip --quiet
    call .venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERRO] Falha ao instalar dependencias.
        pause
        exit /b 1
    )
    popd
    echo [ok] Dependencias instaladas.
) else (
    echo [ok] Ambiente virtual ja existe.
)

REM =========================================================
REM  5. Verificar frontend compilado
REM =========================================================
if not exist "frontend\dist\index.html" (
    echo [ERRO] frontend\dist nao encontrado.
    echo Este pacote deveria vir com o frontend ja compilado.
    echo Reobtenha o zip original.
    pause
    exit /b 1
)
echo [ok] Frontend encontrado.

REM =========================================================
REM  6. Verificar se ha atualizacao disponivel (opcional,
REM     silencioso - nao bloqueia a inicializacao)
REM =========================================================
echo.
echo [info] Verificando atualizacoes...
for /f "tokens=*" %%V in ('type "electron\package.json" 2^>nul ^| findstr /C:"\"version\""') do (
    set PKG_LINE=%%V
)
REM Extrai versao do package.json (ex: "version": "0.5.0")
for /f "tokens=2 delims=:" %%A in ("!PKG_LINE!") do (
    set LOCAL_VER=%%A
    set LOCAL_VER=!LOCAL_VER: =!
    set LOCAL_VER=!LOCAL_VER:"=!
    set LOCAL_VER=!LOCAL_VER:,=!
)
if defined LOCAL_VER (
    echo [info] Versao local: !LOCAL_VER!
)

REM =========================================================
REM  7. Subir servidor
REM =========================================================
echo.
echo [ok] Tudo pronto. Subindo servidor...
echo.

start "" cmd /c "timeout /t 4 /nobreak >nul && start http://localhost:8000/app"

cd backend
call .venv\Scripts\activate.bat
echo Backend rodando em http://localhost:8000
echo Frontend em       http://localhost:8000/app
echo.
echo Pressione Ctrl+C para encerrar.
echo ============================================================
python -m uvicorn main:app --host 127.0.0.1 --port 8000
