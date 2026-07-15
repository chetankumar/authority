@echo off
setlocal enabledelayedexpansion

:: Authority — Windows production launcher (doc 02)
:: Usage: double-click or run from a terminal. Ctrl+C to stop.

set "ROOT=%~dp0"
cd /d "%ROOT%"

:: Read config (defaults)
set "PORT=8700"
set "APP_DATA_ROOT=./data"
set "ENV_NAME=authority"
set "BACKEND=%ROOT%src\backend"
set "FRONTEND=%ROOT%src\frontend"
set "MARKER=%ROOT%.setup-complete"

:: -------------------------------------------------------------------
:: 1. Already running? If health endpoint answers, just open browser.
:: -------------------------------------------------------------------
curl -s -o NUL -w "%%{http_code}" "http://localhost:%PORT%/api/health" 2>NUL | findstr "200" >NUL 2>&1
if %errorlevel%==0 (
    echo Authority is already running on port %PORT%.
    start "" "http://localhost:%PORT%"
    exit /b 0
)

:: -------------------------------------------------------------------
:: 2. Environment resolution (conda preferred, else venv)
:: -------------------------------------------------------------------
where conda >NUL 2>&1
if %errorlevel%==0 (
    set "USE_CONDA=1"
    echo [Authority] Using conda environment "%ENV_NAME%"

    conda info --envs 2>NUL | findstr /C:"%ENV_NAME%" >NUL 2>&1
    if !errorlevel! neq 0 (
        echo [Authority] Creating conda environment "%ENV_NAME%" with Python 3.11...
        conda create -n %ENV_NAME% python=3.11 -y
        if !errorlevel! neq 0 (
            echo [Authority] ERROR: Failed to create conda environment.
            pause
            exit /b 1
        )
    )
) else (
    set "USE_CONDA=0"
    echo [Authority] conda not found; using venv at .venv
    if not exist "%ROOT%.venv\Scripts\activate.bat" (
        python -m venv "%ROOT%.venv"
        if !errorlevel! neq 0 (
            echo [Authority] ERROR: Failed to create venv.
            pause
            exit /b 1
        )
    )
)

:: -------------------------------------------------------------------
:: 3. First-run setup (install deps + build frontend)
:: -------------------------------------------------------------------
:: Compute a hash of requirements.txt + package.json to detect changes.
set "HASH="
for /f %%A in ('certutil -hashfile "%BACKEND%\requirements.txt" MD5 2^>NUL ^| findstr /v "hash"') do (
    if not defined HASH set "HASH=%%A"
)
for /f %%B in ('certutil -hashfile "%FRONTEND%\package.json" MD5 2^>NUL ^| findstr /v "hash"') do (
    set "HASH=!HASH!-%%B"
)

set "NEED_SETUP=0"
if not exist "%MARKER%" set "NEED_SETUP=1"
if exist "%MARKER%" (
    set /p STORED_HASH=<"%MARKER%"
    if not "!STORED_HASH!"=="!HASH!" set "NEED_SETUP=1"
)

if %NEED_SETUP%==1 (
    echo [Authority] Installing / updating dependencies...

    if %USE_CONDA%==1 (
        conda run -n %ENV_NAME% --no-banner --no-capture-output pip install -r "%BACKEND%\requirements.txt"
    ) else (
        call "%ROOT%.venv\Scripts\activate.bat"
        pip install -r "%BACKEND%\requirements.txt"
    )
    if !errorlevel! neq 0 (
        echo [Authority] ERROR: pip install failed.
        pause
        exit /b 1
    )

    :: Check git
    where git >NUL 2>&1
    if !errorlevel! neq 0 (
        echo [Authority] WARNING: git is not installed. Version control features will not work.
    )

    :: Build frontend
    echo [Authority] Building frontend...
    pushd "%FRONTEND%"
    call npm install
    if !errorlevel! neq 0 (
        echo [Authority] ERROR: npm install failed.
        popd & pause & exit /b 1
    )
    call npm run build
    if !errorlevel! neq 0 (
        echo [Authority] ERROR: frontend build failed.
        popd & pause & exit /b 1
    )
    popd

    :: Write marker
    echo !HASH!> "%MARKER%"
    echo [Authority] Setup complete.
)

:: -------------------------------------------------------------------
:: 4. Start the backend
:: -------------------------------------------------------------------
echo [Authority] Starting on port %PORT%...

if %USE_CONDA%==1 (
    start /b "" conda run -n %ENV_NAME% --no-banner --no-capture-output python -m uvicorn app.main:app --host 127.0.0.1 --port %PORT% --workers 1 --app-dir "%BACKEND%"
) else (
    call "%ROOT%.venv\Scripts\activate.bat"
    start /b "" python -m uvicorn app.main:app --host 127.0.0.1 --port %PORT% --workers 1 --app-dir "%BACKEND%"
)

:: -------------------------------------------------------------------
:: 5. Poll for readiness (up to 60s)
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
:: 6. Open browser
:: -------------------------------------------------------------------
echo [Authority] Ready at http://localhost:%PORT%
start "" "http://localhost:%PORT%"

:: Keep the window open so the backend stays alive.
echo Press Ctrl+C to stop Authority.
:wait
timeout /t 86400 /nobreak >NUL
goto :wait
