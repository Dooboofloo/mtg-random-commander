@echo off
setlocal
cd /d "%~dp0"

rem Create a local environment once. Python 3.11+ must be installed.
if not exist ".venv\Scripts\python.exe" (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -m venv .venv
    ) else (
        python -m venv .venv
    )
    if errorlevel 1 (
        echo Could not create a Python environment. Install Python 3.11 or newer.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
    echo Python 3.11 or newer is required. Remove .venv and rerun with a newer Python.
    pause
    exit /b 1
)

rem Verify that mtg-carddb 1.x exists before installing. No network on later runs.
".venv\Scripts\python.exe" -c "from importlib.metadata import version; v=version('mtg-carddb'); assert int(v.split('.')[0]) == 1" >nul 2>nul
if errorlevel 1 (
    echo Installing Python dependencies...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Failed to install dependencies.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" main.py %*
set "RESULT=%errorlevel%"
echo.
pause
exit /b %RESULT%
