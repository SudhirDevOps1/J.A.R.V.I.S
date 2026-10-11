@echo off
rem ==============================================================================
rem scripts/update_deps.bat — Windows Auto-Updater Wrapper for J.A.R.V.I.S.
rem ==============================================================================
rem Ye batch file auto_update.py ko launch karti hai.
rem Virtual environment (.venv) ko auto-detect karti hai aur safe update run karti hai.
rem
rem Usage:
rem     scripts\update_deps.bat              (Default Safe Update)
rem     scripts\update_deps.bat --check      (Check outdated packages)
rem     scripts\update_deps.bat --dry-run    (Simulation mode)
rem ==============================================================================

chcp 65001 >nul
setlocal enabledelayedexpansion

echo ======================================================================
echo           * J.A.R.V.I.S. DEPENDENCY AUTO-UPDATER (WINDOWS) *
echo ======================================================================

set "SCRIPT_DIR=%~dp0"
set "ROOT_DIR=%SCRIPT_DIR%.."
cd /d "%ROOT_DIR%"

rem Python interpreter khojo (.venv prioritized)
set "PY_EXE="
if exist "%ROOT_DIR%\.venv\Scripts\python.exe" (
    set "PY_EXE=%ROOT_DIR%\.venv\Scripts\python.exe"
) else if exist "%ROOT_DIR%\venv\Scripts\python.exe" (
    set "PY_EXE=%ROOT_DIR%\venv\Scripts\python.exe"
) else (
    where python >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        set "PY_EXE=python"
    )
)

if "%PY_EXE%"=="" (
    echo [ERROR] Python interpreter nahi mila! Kripya Python ya .venv install karein.
    exit /b 1
)

echo [*] Using Python: %PY_EXE%
echo [*] Starting defensive dependency update...
echo.

"%PY_EXE%" "%SCRIPT_DIR%auto_update.py" %*
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if %EXIT_CODE% equ 0 (
    echo [OK] Update cycle complete ho gaya bina kisi error ke.
) else (
    echo [WARNING] Update process exit code: %EXIT_CODE%
)

exit /b %EXIT_CODE%
