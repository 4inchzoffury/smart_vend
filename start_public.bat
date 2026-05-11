@echo off
cd /d "%~dp0"
echo.
echo  ================================================
echo   Prime Micro Markets -- Public Mode
echo   https://app.primemicromarkets.com
echo  ================================================
echo.

:: --- Pre-flight: cloudflared must be installed ---
where cloudflared >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] cloudflared is not installed or not on PATH.
    echo.
    echo  Run this command to install it, then re-run this script:
    echo.
    echo      winget install Cloudflare.cloudflared
    echo.
    echo  After installing, open a NEW terminal so PATH is refreshed.
    echo.
    pause
    exit /b 1
)

echo  [OK] cloudflared found.
echo.

echo Starting Cloudflare Tunnel...
start "Cloudflare Tunnel" cloudflared tunnel run prime-markets

echo Waiting for tunnel to connect...
timeout /t 5 /nobreak > nul

echo Starting app server...
echo.
.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000
pause
