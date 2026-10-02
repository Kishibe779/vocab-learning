@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Please create the project virtual environment first. See README.md.
    pause
    exit /b 1
)
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
pause
