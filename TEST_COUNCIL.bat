@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
 echo Set up the virtual environment using README.md.
 exit /b 1
)
.venv\Scripts\python.exe -m unittest discover -v
exit /b %errorlevel%
