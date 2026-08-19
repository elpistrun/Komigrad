@echo off
chcp 65001 >nul 2>&1
title Komigrad - Установка
echo ============================================
echo   Komigrad Website - Установка
echo ============================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Python найден:
    python --version
    echo.
) else (
    echo [!] Python не найден. Скачиваю...
    echo.
    
    :: Download Python installer
    echo Скачивание Python 3.12...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe' -OutFile '%TEMP%\python_installer.exe'" 2>nul
    
    if exist "%TEMP%\python_installer.exe" (
        echo.
        echo Запуск установщика Python...
        echo ВАЖНО: Поставь галочку "Add Python to PATH" при установке!
        echo.
        start /wait "%TEMP%\python_installer.exe" /install
            
        :: Re-check
        python --version >nul 2>&1
        if %errorlevel% neq 0 (
            echo.
            echo [ERROR] Python не установлен или не добавлен в PATH.
            echo Перезапусти компьютер и попробуй снова.
            pause
            exit /b 1
        )
        echo.
        echo [OK] Python установлен:
        python --version
    ) else (
        echo [ERROR] Не удалось скачать Python.
        echo Скачай вручную: https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

echo.
echo ============================================
echo   Установка завершена!
echo   Запусти start.bat для запуска сайта
echo ============================================
pause
