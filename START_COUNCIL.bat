@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run SETUP_COUNCIL.bat first. See README.md for account configuration.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" gui.py
set "council_exit=%errorlevel%"
if not "%council_exit%"=="0" pause
exit /b %council_exit%
