@echo off
cd /d "%~dp0"
echo.
echo  ================================================
echo   Prime Micro Markets -- Public Mode
echo   https://app.primemicromarkets.com
echo  ================================================
echo.

echo Starting Cloudflare Tunnel...
start "Cloudflare Tunnel" cloudflared tunnel run prime-markets

echo Waiting for tunnel to connect...
timeout /t 3 /nobreak > nul

echo Starting app server...
echo.
.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000
pause
