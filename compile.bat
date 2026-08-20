@echo off
setlocal

:: Authority — compile frontend (production build)
:: Runs npm run build in src\frontend. Output goes to src\frontend\dist\
:: If start.bat is running with UI live-reload, the browser refreshes on its own.

set "ROOT=%~dp0"
cd /d "%ROOT%"

set "FRONTEND=%ROOT%src\frontend"

echo [Authority] Building frontend...
pushd "%FRONTEND%"
call npm run build
if errorlevel 1 (
    echo [Authority] ERROR: frontend build failed.
    popd
    exit /b 1
)
popd

echo [Authority] Build complete — dist at src\frontend\dist\
