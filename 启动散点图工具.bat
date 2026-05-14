@echo off
chcp 65001 >nul
title 散点图工具 · Scatter → CDR
python "%~dp0scatter_tool.py"
if errorlevel 1 (
    echo.
    echo 启动失败，请确认已安装 Python 3.10+
    pause
)
