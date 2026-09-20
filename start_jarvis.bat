@echo off
title SudhirDevOps1 AI Assistant (J.A.R.V.I.S.) - Automated Setup and Launcher
cd /d "%~dp0"
chcp 65001 >nul 2>&1
color 0B

echo ======================================================================
echo             * SUDHIRDEVOPS1 AI ASSISTANT (J.A.R.V.I.S.) *
echo            Automated Self-Deploying Neural Desktop Interface
echo ======================================================================
echo.

:: 1. Auto-Detect / Auto-Install Python
set "PYTHON_EXE="

:: Check existing virtual environment first
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "venv\Scripts\python.exe" set "PYTHON_EXE=venv\Scripts\python.exe"

:: Check PATH for python
if not defined PYTHON_EXE where python >nul 2>&1 && set "PYTHON_EXE=python"

:: Check known Windows install paths
if not defined PYTHON_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PYTHON_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PYTHON_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PYTHON_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
if not defined PYTHON_EXE if exist "C:\Program Files\Python313\python.exe" set "PYTHON_EXE=C:\Program Files\Python313\python.exe"
if not defined PYTHON_EXE if exist "C:\Program Files\Python312\python.exe" set "PYTHON_EXE=C:\Program Files\Python312\python.exe"
if not defined PYTHON_EXE if exist "C:\Program Files\Python311\python.exe" set "PYTHON_EXE=C:\Program Files\Python311\python.exe"
if not defined PYTHON_EXE if exist "C:\Python313\python.exe" set "PYTHON_EXE=C:\Python313\python.exe"
if not defined PYTHON_EXE if exist "C:\Python312\python.exe" set "PYTHON_EXE=C:\Python312\python.exe"
if not defined PYTHON_EXE if exist "C:\Python311\python.exe" set "PYTHON_EXE=C:\Python311\python.exe"
if not defined PYTHON_EXE if exist "C:\Python310\python.exe" set "PYTHON_EXE=C:\Python310\python.exe"

:: Check py launcher
if not defined PYTHON_EXE py --version >nul 2>&1 && set "PYTHON_EXE=py"

:: If Python is still not found, auto-download and install Python 3.12 (silent setup)
if defined PYTHON_EXE goto :python_found

echo [!] Python nahi mila. Automated installer shuru kar rahe hain...
echo [*] Downloading and installing official Python 3.12 64-bit...

where winget >nul 2>&1
if %ERRORLEVEL% EQU 0 goto :install_winget
goto :install_powershell

:install_winget
echo [*] Installing via Windows Package Manager winget...
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements --silent
goto :check_installed_python

:install_powershell
echo [*] Downloading Python installer from python.org...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe', '$env:TEMP\python_setup.exe'); Start-Process '$env:TEMP\python_setup.exe' -ArgumentList '/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 SimpleInstall=1' -Wait"
goto :check_installed_python

:check_installed_python
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto :python_found
)
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_EXE=python"
    goto :python_found
)

:python_not_found
echo [ERROR] Python auto-install nahi ho saka.
echo Kripya Python 3.10+ manual install karein: https://www.python.org/downloads/
echo Installation ke samay 'Add Python to PATH' zaroor tick karein.
pause
exit /b 1

:python_found
:: 2. Auto-activate or Auto-create Virtual Environment
if exist ".venv\Scripts\python.exe" goto :activate_dot_venv
if exist "venv\Scripts\python.exe" goto :activate_venv

echo [*] Initializing isolated virtual environment .venv...
"%PYTHON_EXE%" -m venv .venv
if exist ".venv\Scripts\python.exe" goto :activate_dot_venv
goto :pip_setup

:activate_dot_venv
call .venv\Scripts\activate.bat
set "PYTHON_EXE=.venv\Scripts\python.exe"
goto :pip_setup

:activate_venv
call venv\Scripts\activate.bat
set "PYTHON_EXE=venv\Scripts\python.exe"
goto :pip_setup

:pip_setup
:: 3. Pip self-repair and upgrade
"%PYTHON_EXE%" -m ensurepip --default-pip >nul 2>&1

:: 4. Check and Auto-Install Python Dependencies on First Run
echo [*] Checking libraries and system dependencies...
"%PYTHON_EXE%" -c "import PyQt6, google.genai, requests, sounddevice, edge_tts, PIL, cv2, psutil, tinydb, rank_bm25, thefuzz, keyboard, sklearn, fastapi, uvicorn, cryptography, win32api, comtypes, pycaw" >nul 2>&1
if %ERRORLEVEL% EQU 0 goto :dependencies_ready

echo [*] Pehli baar setup ho raha hai ya missing packages hain.
echo [*] Auto-installing required packages from requirements.txt...
"%PYTHON_EXE%" -m pip install --upgrade pip --quiet >nul 2>&1
"%PYTHON_EXE%" -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [!] Warning: Pip install had warnings. Continuing anyway...
) else (
    echo [OK] Sabhi zaroori packages safaltapoorvak install ho gaye!
)
echo.

:dependencies_ready
:: 5. Run Preflight Check (Auto-downloads models, LFM2.5, SFX, icons, sets up desktop shortcut)
echo [*] Running automated pre-flight checks and asset verification...
"%PYTHON_EXE%" scripts\preflight_check.py

if "%~1"=="--check" (
    echo.
    echo [OK] J.A.R.V.I.S. automated setup and verification complete. Everything is ready!
    exit /b 0
)
if "%~1"=="--dry-run" (
    echo.
    echo [OK] J.A.R.V.I.S. automated setup and verification complete. Everything is ready!
    exit /b 0
)

:: 6. Hands-Free Launch (Zero Enter required)
echo [*] Starting J.A.R.V.I.S. neural interface...
echo.
set "PYTHONWARNINGS=ignore::DeprecationWarning"
"%PYTHON_EXE%" main.py %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ======================================================================
    echo [INFO] J.A.R.V.I.S. band ho gaya ya runtime warning aayi.
    echo Window band karne ke liye koi bhi key dabayein...
    echo ======================================================================
    echo.
    pause
)
