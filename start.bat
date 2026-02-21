@echo off
:: Vantage — Launch Script
:: Starts the backend (requires elevation for Scapy) and frontend dev server.

:: ── Self-elevate to Administrator ─────────────────────────────────────────────
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting Administrator privileges...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"%~f0\"' -Verb RunAs"
    exit /b
)

:: ── Paths ─────────────────────────────────────────────────────────────────────
set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "PYTHON=%BACKEND%\venv\Scripts\python.exe"

:: ── Sanity checks ─────────────────────────────────────────────────────────────
if not exist "%PYTHON%" (
    echo [ERROR] Python venv not found at: %PYTHON%
    echo Run: cd backend ^&^& python -m venv venv ^&^& venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] npm not found. Install Node.js from https://nodejs.org
    pause
    exit /b 1
)

:: ── Start backend in a new window ─────────────────────────────────────────────
echo Starting Vantage backend...
start "Vantage Backend" cmd /k "cd /d "%BACKEND%" && "%PYTHON%" main.py"

:: ── Start frontend in a new window ────────────────────────────────────────────
echo Starting Vantage frontend...
start "Vantage Frontend" cmd /k "cd /d "%FRONTEND%" && npm run dev"

:: ── Open browser after a short delay ──────────────────────────────────────────
echo Waiting for servers to start...
timeout /t 4 /nobreak >nul
start http://localhost:5173

echo.
echo Vantage is running.
echo   Backend:  http://localhost:8001
echo   Frontend: http://localhost:5173
echo.
echo Close the "Vantage Backend" and "Vantage Frontend" windows to stop.
