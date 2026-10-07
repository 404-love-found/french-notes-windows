@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    echo Python launcher not found. Install Python 3.11 or newer from python.org first.
    pause
    exit /b 1
)
py -3 -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
    echo Python 3.11 or newer with Tcl/Tk is required. Repair your Python installation.
    pause
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
    if errorlevel 1 goto :failed
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed
echo Setup complete. Double-click start_windows.bat to run French Notes.
pause
exit /b 0
:failed
echo Setup failed. Please check the error above and try again.
pause
exit /b 1
