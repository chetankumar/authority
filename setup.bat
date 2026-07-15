@echo off
setlocal enabledelayedexpansion

:: Authority — Windows setup script
:: Installs Python deps, Node deps, builds frontend.
:: Run once after cloning, or again after changing requirements.txt / package.json.

set "ROOT=%~dp0"
cd /d "%ROOT%"

set "ENV_NAME=authority"
set "BACKEND=%ROOT%src\backend"
set "FRONTEND=%ROOT%src\frontend"

:: -------------------------------------------------------------------
:: 1. Resolve Python environment (conda preferred, else venv)
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
:: 2. Install Python dependencies
:: -------------------------------------------------------------------
echo [Authority] Installing Python dependencies...

if %USE_CONDA%==1 (
    conda run -n %ENV_NAME% --no-capture-output pip install -r "%BACKEND%\requirements.txt"
) else (
    call "%ROOT%.venv\Scripts\activate.bat"
    pip install -r "%BACKEND%\requirements.txt"
)

:: Verify with a quick import (conda run exit codes are unreliable)
if %USE_CONDA%==1 (
    conda run -n %ENV_NAME% --no-capture-output python -c "import fastapi" >NUL 2>&1
) else (
    python -c "import fastapi" >NUL 2>&1
)
if !errorlevel! neq 0 (
    echo [Authority] ERROR: pip install failed.
    pause
    exit /b 1
)
echo [Authority] Python dependencies OK.

:: -------------------------------------------------------------------
:: 3. Check git
:: -------------------------------------------------------------------
where git >NUL 2>&1
if !errorlevel! neq 0 (
    echo [Authority] WARNING: git is not installed. Version control features will not work.
)

:: -------------------------------------------------------------------
:: 4. Install Node dependencies + build frontend
:: -------------------------------------------------------------------
echo [Authority] Installing Node dependencies...
pushd "%FRONTEND%"
call npm install
if !errorlevel! neq 0 (
    echo [Authority] ERROR: npm install failed.
    popd & pause & exit /b 1
)

echo [Authority] Building frontend...
call npm run build
if !errorlevel! neq 0 (
    echo [Authority] ERROR: frontend build failed.
    popd & pause & exit /b 1
)
popd

echo.
echo [Authority] Setup complete. Run start.bat to launch.
