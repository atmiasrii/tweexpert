@echo off
REM ===================================================================
REM  Quill - one double-click to start the day.
REM
REM  Starts the API, which in turn starts the worker and the browser
REM  process (autostart_live), then opens the dashboard. Close this
REM  window or press Ctrl+C to stop the API; use Stop in the dashboard
REM  to stop the worker and browser.
REM ===================================================================
setlocal
cd /d "%~dp0"
title Quill

set "PY=%~dp0.venv\Scripts\python.exe"
set "PORT=8770"
set "URL=http://127.0.0.1:%PORT%"

echo.
echo   Quill
echo   -----
echo.

REM --- prerequisites -------------------------------------------------
if not exist "%PY%" (
  echo   [x] No virtual environment at .venv
  echo       Run: make install
  goto :fail
)
if not exist "%~dp0.env" (
  echo   [x] No .env file in %~dp0
  echo       Copy .env.example to .env and fill it in.
  goto :fail
)

echo   [.] Checking the local model...
curl -s -o nul -m 5 http://localhost:11434/v1/models
if errorlevel 1 (
  echo   [x] Ollama is not answering on port 11434.
  echo       Start Ollama, then run this again.
  goto :fail
)
echo   [ok] Ollama is up

REM --- frontend: only rebuild when the source is newer ----------------
set "NEEDBUILD="
if not exist "%~dp0frontend\dist\index.html" set "NEEDBUILD=1"
if defined NEEDBUILD (
  echo   [.] Building the dashboard, one moment...
  pushd "%~dp0frontend"
  call npm run build
  popd
)
echo   [ok] Dashboard built

REM --- is it already running? ----------------------------------------
curl -s -o nul -m 3 %URL%/api/ping
if not errorlevel 1 (
  echo   [ok] Quill is already running
  goto :open
)

REM --- start the API -------------------------------------------------
echo   [.] Starting Quill...
start "Quill API" /min "%PY%" -m uvicorn quill.api.app:app ^
  --host 127.0.0.1 --port %PORT% --app-dir backend

REM --- wait for it to answer -----------------------------------------
set /a TRIES=0
:waitloop
set /a TRIES+=1
if %TRIES% gtr 60 (
  echo   [x] Quill did not come up. See backend\data\quill.jsonl
  goto :fail
)
timeout /t 1 /nobreak >nul
curl -s -o nul -m 3 %URL%/api/ping
if errorlevel 1 goto :waitloop

echo   [ok] Quill is up on %URL%

:open
start "" %URL%
echo.
echo   Dashboard : %URL%
echo   Logs      : backend\data\quill.jsonl
echo               backend\data\worker.out
echo               backend\data\browser.out
echo.
echo   It watches your accounts and works the For You feed on its own.
echo   Open the dashboard whenever you want to approve or stop it.
echo.
timeout /t 6 /nobreak >nul
exit /b 0

:fail
echo.
pause
exit /b 1
