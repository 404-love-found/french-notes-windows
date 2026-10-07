@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Exécutez d'abord setup_windows.bat.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" run.py
if errorlevel 1 pause
