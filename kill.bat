@echo off
:: Authority — stop any running instance (Windows)

set "PORT=8700"

echo [Authority] Looking for processes on port %PORT%...

for /f "tokens=5" %%P in ('netstat -aon 2^>NUL ^| findstr "LISTENING" ^| findstr ":%PORT% "') do (
    echo [Authority] Killing PID %%P
    taskkill /F /PID %%P >NUL 2>&1
)

:: Verify
timeout /t 1 /nobreak >NUL
netstat -aon 2>NUL | findstr "LISTENING" | findstr ":%PORT% " >NUL 2>&1
if %errorlevel%==0 (
    echo [Authority] WARNING: Port %PORT% still in use. You may need to close it manually.
) else (
    echo [Authority] Stopped.
)
