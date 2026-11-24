@echo off
setlocal enabledelayedexpansion
title SEPA/VCP Trading Terminal — Localhost Launcher

echo ========================================================================
echo   SEPA/VCP TRADING TERMINAL (Mark Minervini) — 100%% Gratuito / Local
echo ========================================================================
echo.

cd /d "%~dp0"

if not exist ".env" (
    echo [INFO] Ficheiro .env nao encontrado. A copiar .env.example para .env...
    copy ".env.example" ".env" >nul
)

REM --- 1. Verificar/Criar ambiente virtual Python ---
if not exist "backend\.venv\Scripts\python.exe" (
    echo [1/4] A criar ambiente virtual Python em backend\.venv...
    python -m venv backend\.venv
    if errorlevel 1 (
        echo [ERRO] Python nao encontrado no PATH. Instala Python 3.11+ e tenta novamente.
        pause
        exit /b 1
    )
    echo [2/4] A instalar dependencias Python...
    backend\.venv\Scripts\pip.exe install -r backend\requirements.txt
    if errorlevel 1 (
        echo [ERRO] Falha ao instalar dependencias Python.
        pause
        exit /b 1
    )
) else (
    echo [1/4] Ambiente Python encontrado (backend\.venv).
)

REM --- 2. Verificar/Instalar dependencias Node.js ---
if not exist "frontend\node_modules" (
    echo [2/4] A instalar dependencias do frontend (npm install)...
    pushd frontend
    call npm install
    if errorlevel 1 (
        popd
        echo [ERRO] Falha ao instalar dependencias Node.js. Verifica se Node 18+ esta instalado.
        pause
        exit /b 1
    )
    popd
) else (
    echo [2/4] Dependencias do frontend encontradas.
)

echo [3/4] A iniciar Backend FastAPI em http://127.0.0.1:8000 ...
start "SEPA-VCP Backend (FastAPI)" cmd /k "cd /d "%~dp0backend" && .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

timeout /t 3 /nobreak >nul

echo [4/4] A iniciar Frontend React (Vite) em http://127.0.0.1:5173 ...
start "SEPA-VCP Frontend (Vite)" cmd /k "cd /d "%~dp0frontend" && npm run dev"

timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:5173"

echo.
echo ========================================================================
echo   APLICACAO INICIADA COM SUCESSO!
echo   Dashboard: http://127.0.0.1:5173
echo   API Docs : http://127.0.0.1:8000/docs
echo ========================================================================
echo.
pause
