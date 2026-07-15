@echo off
setlocal enabledelayedexpansion

:: Authority — Windows development mode (doc 02)
:: Starts Uvicorn with --reload and Vite dev server in parallel.
:: Vite proxies /api to the backend (see vite.config.ts).
:: For working on Authority itself, never for writing.

set "ROOT=%~dp0"
cd /d "%ROOT%"

set "PORT=8700"
set "ENV_NAME=authority"
set "BACKEND=%ROOT%src\backend"
set "FRONTEND=%ROOT%src\frontend"

:: Check if already running
curl -s -o NUL -w "%%{http_code}" "http://localhost:%PORT%/api/health" 2>NUL | findstr "200" >NUL 2>&1
if %errorlevel%==0 (
    echo [Authority DEV] Backend already running on port %PORT%. Stop it first.
    exit /b 1
)

:: Resolve environment
where conda >NUL 2>&1
if %errorlevel%==0 (
    set "USE_CONDA=1"
) else (
    set "USE_CONDA=0"
)

:: -------------------------------------------------------------------
:: Start backend with --reload
:: -------------------------------------------------------------------
echo [Authority DEV] Starting backend (reload mode) on port %PORT%...

if %USE_CONDA%==1 (
    start "Authority API" cmd /k "conda run -n %ENV_NAME% --no-capture-output python -m uvicorn app.main:app --host 127.0.0.1 --port %PORT% --reload --app-dir "%BACKEND%""
) else (
    start "Authority API" cmd /k "call "%ROOT%.venv\Scripts\activate.bat" && python -m uvicorn app.main:app --host 127.0.0.1 --port %PORT% --reload --app-dir "%BACKEND%""
)

:: -------------------------------------------------------------------
:: Start Vite dev server
:: -------------------------------------------------------------------
echo [Authority DEV] Starting Vite dev server...
start "Authority Frontend" cmd /k "cd /d "%FRONTEND%" && npm run dev"

:: -------------------------------------------------------------------
:: Wait for backend readiness, then print info
:: -------------------------------------------------------------------
set "TRIES=0"
:poll
if %TRIES% geq 20 (
    echo [Authority DEV] WARNING: Backend hasn't responded after 40s. Check the API terminal.
    goto :info
)
timeout /t 2 /nobreak >NUL
curl -s -o NUL -w "%%{http_code}" "http://localhost:%PORT%/api/health" 2>NUL | findstr "200" >NUL 2>&1
if %errorlevel% neq 0 (
    set /a TRIES+=1
    goto :poll
)

:info
echo.
echo =====================================================
echo   Authority DEV
echo   API:      http://localhost:%PORT%/api
echo   Frontend: http://localhost:5173
echo   Docs:     http://localhost:%PORT%/docs
echo =====================================================
echo   Close the two terminal windows to stop.
echo.
start "" "http://localhost:5173"
