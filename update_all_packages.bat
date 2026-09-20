@echo off
title J.A.R.V.I.S. - Auto Pip Package Updater
cd /d "%~dp0"
chcp 65001 >nul 2>&1
color 0A

echo ======================================================================
echo              * J.A.R.V.I.S. AUTO PIP DEPENDENCY UPDATER *
echo          Checking PyPI and Auto-Upgrading All Python Libraries
echo ======================================================================
echo.

set "PYTHON_EXE="
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "venv\Scripts\python.exe" set "PYTHON_EXE=venv\Scripts\python.exe"
if not defined PYTHON_EXE set "PYTHON_EXE=python"

"%PYTHON_EXE%" scripts\auto_pip_updater.py --force

echo.
echo ======================================================================
echo [OK] Package check and update process complete!
echo ======================================================================
echo.
pause
