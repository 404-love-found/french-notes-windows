@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup_windows.bat first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name FrenchNotes --collect-all docx run.py
if errorlevel 1 goto :failed
echo Built dist\FrenchNotes.exe. Copy that file to run without installing Python.
pause
exit /b 0
:failed
echo Build failed. Please check the error above.
pause
exit /b 1
