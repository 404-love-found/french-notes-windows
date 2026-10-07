@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Exécutez d'abord setup_windows.bat.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name FrenchNotes --collect-all docx run.py
if errorlevel 1 goto :failed
echo Fichier créé : dist\FrenchNotes.exe. Copiez-le pour utiliser l'application sans installer Python.
pause
exit /b 0
:failed
echo Échec de la compilation. Consultez l'erreur ci-dessus.
pause
exit /b 1
