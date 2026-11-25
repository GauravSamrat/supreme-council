@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    where py >nul 2>nul
    if errorlevel 1 (
        echo Install Python 3.10 or newer from python.org with Tcl/Tk and the Windows launcher.
        goto failed
    )
    py -3 -c "import sys, tkinter; sys.exit(not sys.version_info[0:2] >= (3, 10))"
    if errorlevel 1 goto failed
    py -3 -m venv .venv
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -c "import sys, tkinter; sys.exit(not sys.version_info[0:2] >= (3, 10))"
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip --disable-pip-version-check install -r requirements.txt
if errorlevel 1 goto failed
if not exist ".env" (
    copy /-Y ".env.example" ".env" <nul >nul
    if errorlevel 1 goto failed
)
echo Setup complete. Configure .env and config.local.json as described in README.md.
exit /b 0
:failed
echo Setup failed. See README.md for requirements and manual setup.
exit /b 1
