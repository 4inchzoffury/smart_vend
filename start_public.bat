@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
echo.
echo  ================================================
echo   Prime Micro Markets -- Public Mode
echo   https://primemicromarkets.com
echo  ================================================
echo.

:: --- Pre-flight: cloudflared must be installed ---
:: Store paths with (x86) in variables so the batch parser never sees raw parens
set "CF_X86=C:\Program Files (x86)\cloudflared\cloudflared.exe"
set "CF_X64=C:\Program Files\cloudflared\cloudflared.exe"
set "CLOUDFLARED_EXE=cloudflared"

where cloudflared >nul 2>&1
if not errorlevel 1 goto :cf_found

if exist "!CF_X86!" set "CLOUDFLARED_EXE=!CF_X86!" & goto :cf_found
if exist "!CF_X64!" set "CLOUDFLARED_EXE=!CF_X64!" & goto :cf_found

echo  [ERROR] cloudflared is not installed or not on PATH.
echo.
echo  Run this command to install it, then re-run this script:
echo.
echo      winget install Cloudflare.cloudflared
echo.
pause
exit /b 1

:cf_found
echo  [OK] cloudflared found.
echo.

:: --- Optional: start Ollama if installed and not already running ---
where ollama >nul 2>&1
if not errorlevel 1 (
    curl -s -o nul -w "%%{http_code}" http://localhost:11434 2>nul | findstr /x "200" >nul 2>&1
    if errorlevel 1 (
        echo  [INFO] Ollama installed but not running -- starting it...
        start "" ollama serve
        timeout /t 3 /nobreak > nul
        echo  [OK] Ollama started at http://localhost:11434
    ) else (
        echo  [OK] Ollama already running at http://localhost:11434
    )
    echo.
) else (
    echo  [INFO] Ollama not installed. Local AI provider unavailable.
    echo         Install from https://ollama.com/download/windows to enable it.
    echo.
)

:: --- NordVPN bypass: route Cloudflare IPs through real gateway ---
net session >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=*" %%g in ('powershell -NoProfile -Command "Get-NetRoute -DestinationPrefix 0.0.0.0/0 -InterfaceAlias Alien_Wi-Fi -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty NextHop"') do set "REAL_GW=%%g"
    if defined REAL_GW (
        route add 198.41.128.0 MASK 255.255.128.0   !REAL_GW! >nul 2>&1
        route add 104.16.0.0  MASK 255.248.0.0     !REAL_GW! >nul 2>&1
        route add 1.1.1.1     MASK 255.255.255.255  !REAL_GW! >nul 2>&1
        route add 1.0.0.1     MASK 255.255.255.255  !REAL_GW! >nul 2>&1
        echo  [OK] Cloudflare routes added via !REAL_GW! (bypassing NordVPN)
    ) else (
        echo  [WARN] Could not detect real gateway -- tunnel may still route through NordVPN.
    )
) else (
    echo  [WARN] Not running as Administrator -- cannot add NordVPN bypass routes.
    echo         Right-click start_public.bat and choose "Run as administrator" for the
    echo         tunnel to work while NordVPN is active.
)
echo.

echo Starting Cloudflare Tunnel...
start "Cloudflare Tunnel" cmd /k ""!CLOUDFLARED_EXE!" tunnel --protocol http2 --edge-ip-version 4 run prime-markets"

echo Waiting for tunnel to connect...
timeout /t 5 /nobreak > nul

echo Starting app server...
echo.
.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000
pause
