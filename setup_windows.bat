@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    echo Lanceur Python introuvable. Installez Python 3.11 ou une version plus récente depuis python.org.
    pause
    exit /b 1
)
py -3 -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
    echo Python 3.11 ou une version plus récente avec Tcl/Tk est requis. Réparez votre installation de Python.
    pause
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
    if errorlevel 1 goto :failed
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed
echo Installation terminée. Double-cliquez sur start_windows.bat pour ouvrir FrenchNotes.
pause
exit /b 0
:failed
echo Échec de l'installation. Consultez l'erreur ci-dessus, puis réessayez.
pause
exit /b 1
