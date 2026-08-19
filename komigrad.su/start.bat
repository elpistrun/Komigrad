@echo off
chcp 65001 >nul 2>&1
title Komigrad Server
echo ============================================
echo   Komigrad Website + Backend
echo   Запуск сервера...
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python не найден! Запусти install.bat
    pause
    exit /b 1
)

:: Start server in background
start /b python "%~dp0server_fullstack.py"

:: Wait for server to start
timeout /t 3 /nobreak >nul

:: Open browser
start http://127.0.0.1:8080

echo.
echo [OK] Сервер запущен: http://127.0.0.1:8080
echo [OK] Браузер открыт
echo.
echo Нажми любую клавишу для остановки сервера...
pause >nul

:: Kill server
taskkill /f /im python.exe >nul 2>&1
echo [OK] Сервер остановлен.
