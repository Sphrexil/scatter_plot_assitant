@echo off
cd /d "%~dp0"
python scatter_tool.py
if errorlevel 1 (
    echo.
    echo Please install Python 3.10+ with: pip install matplotlib pandas numpy pywin32
    pause
)
