@echo off
title Data Dictionary Agent v4

echo ============================================
echo   Data Dictionary Agent v4 - Launcher
echo ============================================
echo.

:: Check for .env
if not exist ".env" (
    echo [WARNING] .env file not found. Copying from .env.example ...
    copy .env.example .env >nul 2>&1
    echo            Please edit .env with your API keys before using AI features.
    echo.
)

:: Start backend
echo [1/2] Starting FastAPI backend on http://localhost:8000 ...
start "DD-Backend" cmd /k "cd /d %~dp0 && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

:: Wait a moment for backend to boot
timeout /t 3 /nobreak >nul

:: Start frontend
echo [2/2] Starting React frontend on http://localhost:3000 ...
cd frontend
start "DD-Frontend" cmd /k "npm install && npm run dev"
cd ..

echo.
echo ============================================
echo   Both servers starting up!
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo   API docs: http://localhost:8000/docs
echo ============================================
echo.
echo Press any key to exit this launcher (servers keep running) ...
pause >nul
