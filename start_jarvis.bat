@echo off
title SudhirDevOps1 AI Assistant
chcp 65001 >nul
cd /d "%~dp0"

echo ===================================================
echo             Starting SudhirDevOps1 AI Assistant
echo ===================================================
echo.

where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python nahi mila! Kripya Python ko PATH me add karein.
    echo.
    pause
    exit /b 1
)

:: Run fast preflight check (downloads missing models on first run, skips if cached)
python scripts/preflight_check.py

python main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [INFO] JARVIS band ho gaya ya koi error aayi.
    echo.
    pause
)
