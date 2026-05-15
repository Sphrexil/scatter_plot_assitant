@echo off
cd /d "%~dp0"
python scatter_tool.py
if errorlevel 1 (
    echo.
    echo Please install Python 3.10+ and dependencies with:
    echo pip install -r requirements.txt
    pause
)
