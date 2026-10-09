@echo off
cd /d "%~dp0"

:: Check if Python is installed
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python is not installed. Please install it first.
    pause
    exit /b
)

:: Create the virtual environment on first run
if not exist .venv\Scripts\python.exe (
    echo Creating virtual environment...
    python -m venv .venv
    .venv\Scripts\python.exe -m pip install --upgrade pip
)

:: Install or update the packages, so changes to requirements.txt are picked up
.venv\Scripts\python.exe -m pip install --quiet -r requirements.txt

:: Start the API with auto reload, the docs are at http://localhost:8000/docs
.venv\Scripts\python.exe -m uvicorn app.main:app --reload

:: Keep the command prompt open
pause
