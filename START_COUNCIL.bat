@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
 echo Run setup in README first.
 pause
 exit /b 1
)
.venv\Scripts\python.exe gui.py
if errorlevel 1 pause
