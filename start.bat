@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo   Personal AI Accountability Coach via Telegram
echo ===================================================
echo.

:: 1. Check Python installation
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.11 or higher from https://www.python.org/
    pause
    exit /b 1
)

:: 2. Check .env file
if not exist ".env" (
    if exist ".env.example" (
        echo [INFO] .env not found. Creating .env from .env.example...
        copy ".env.example" ".env" >nul
        echo [WARNING] Please open the .env file and fill in your:
        echo   - TELEGRAM_BOT_TOKEN
        echo   - GEMINI_API_KEY
        echo   - ALLOWED_CHAT_ID
        echo.
        pause
    ) else (
        echo [ERROR] Neither .env nor .env.example found!
        pause
        exit /b 1
    )
)

:: 3. Setup Virtual Environment
if not exist ".venv" (
    echo [INFO] Creating Python virtual environment in .venv...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
)

:: 4. Activate virtual environment
call .venv\Scripts\activate.bat

:: 5. Install or update dependencies
echo [INFO] Checking dependencies in requirements.txt...
pip install -q --upgrade pip
pip install -q -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies!
    pause
    exit /b 1
)

:: 6. Ensure data directory exists
if not exist "data" mkdir data

:: 7. Launch Bot
echo [INFO] Starting Personal AI Accountability Coach...
echo Press Ctrl+C to stop the bot.
echo.
python src\main.py

pause
