@echo off
cd /d "%~dp0"
echo.
echo  ================================================
echo   Prime Micro Markets -- Local Mode
echo   http://localhost:8000
echo  ================================================
echo.
.venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
pause
