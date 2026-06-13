@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found. Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

:: Install missing dependencies silently
pip install -r requirements.txt -q --disable-pip-version-check 2>nul

:: Launch
python scatter_tool.py
exit /b 0
