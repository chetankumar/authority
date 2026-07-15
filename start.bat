@echo off
setlocal enabledelayedexpansion

:: Authority — Windows launcher
:: Starts the backend server. Run setup.bat first if dependencies changed.

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
:: 3. Start the backend
:: -------------------------------------------------------------------
echo [Authority] Starting on port %PORT%...

if %USE_CONDA%==1 (
    start /b "" conda run -n %ENV_NAME% --no-capture-output python -m uvicorn app.main:app --host 127.0.0.1 --port %PORT% --workers 1 --reload --app-dir "%BACKEND%"
) else (
    call "%ROOT%.venv\Scripts\activate.bat"
    start /b "" python -m uvicorn app.main:app --host 127.0.0.1 --port %PORT% --workers 1 --reload --app-dir "%BACKEND%"
)

:: -------------------------------------------------------------------
:: 4. Poll for readiness (up to 60s)
:: -------------------------------------------------------------------
set "TRIES=0"
:poll
if %TRIES% geq 30 (
    echo [Authority] ERROR: Backend did not start within 60 seconds.
    echo              Check logs\api.log for details.
    pause
    exit /b 1
)
timeout /t 2 /nobreak >NUL
curl -s -o NUL -w "%%{http_code}" "http://localhost:%PORT%/api/health" 2>NUL | findstr "200" >NUL 2>&1
if %errorlevel% neq 0 (
    set /a TRIES+=1
    goto :poll
)

:: -------------------------------------------------------------------
:: 5. Open browser
:: -------------------------------------------------------------------
echo [Authority] Ready at http://localhost:%PORT%
start "" "http://localhost:%PORT%"

echo Press Ctrl+C to stop Authority.
:wait
timeout /t 86400 /nobreak >NUL
goto :wait
