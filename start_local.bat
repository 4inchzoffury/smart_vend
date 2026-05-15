@echo off
cd /d "%~dp0"
echo.
echo  ================================================
echo   Prime Micro Markets -- Local Mode
echo   http://localhost:8000
echo  ================================================
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

.venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
pause
