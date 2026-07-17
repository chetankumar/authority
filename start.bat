@echo off
setlocal

:: Authority — Windows launcher
:: Starts the backend server. Run setup.bat first if dependencies changed.
:: Stays in the calling terminal (same pattern as start.sh).

set "ROOT=%~dp0"
cd /d "%ROOT%"

set "PORT=8700"
set "ENV_NAME=authority"
set "BACKEND=%ROOT%src\backend"

:: -------------------------------------------------------------------
:: 1. Already running?
:: -------------------------------------------------------------------
curl -s -o NUL -w "%%{http_code}" "http://localhost:%PORT%/api/health" 2>NUL | findstr "200" >NUL 2>&1
if %errorlevel%==0 (
    echo Authority is already running on port %PORT%.
    start "" "http://localhost:%PORT%"
    exit /b 0
)

:: -------------------------------------------------------------------
:: 2. Resolve environment
:: -------------------------------------------------------------------
where conda >NUL 2>&1
if %errorlevel%==0 (
    set "USE_CONDA=1"
) else (
    set "USE_CONDA=0"
)

:: -------------------------------------------------------------------
:: 3. Open browser once ready (background), then run uvicorn in foreground
:: Uvicorn owns this terminal — Ctrl+C stops the server.
:: -------------------------------------------------------------------
echo [Authority] Starting on port %PORT%...
echo [Authority] Stop with Ctrl+C, or run kill.bat.

start "Authority-ready" /b powershell -NoProfile -Command "1..30 | ForEach-Object { Start-Sleep 2; $code = & curl.exe -s -o NUL -w '%%{http_code}' http://localhost:%PORT%/api/health 2>$null; if ($code -eq '200') { Write-Host '[Authority] Ready at http://localhost:%PORT%'; Start-Process 'http://localhost:%PORT%'; exit 0 } }; Write-Host '[Authority] ERROR: Backend did not start within 60 seconds.'; Write-Host '             Check logs\api.log for details.'"

if "%USE_CONDA%"=="1" (
    conda run -n %ENV_NAME% --no-capture-output python -m uvicorn app.main:app --host 127.0.0.1 --port %PORT% --workers 1 --reload --app-dir "%BACKEND%"
) else (
    "%ROOT%.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT% --workers 1 --reload --app-dir "%BACKEND%"
)
