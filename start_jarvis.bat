@echo off
title SudhirDevOps1 AI Assistant (J.A.R.V.I.S.)
cd /d "%~dp0"
color 0B

echo ======================================================================
echo             * SUDHIRDEVOPS1 AI ASSISTANT (J.A.R.V.I.S.) *
echo ======================================================================
echo.

:: 1. Auto-Detect Python
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
        set "PATH=%LOCALAPPDATA%\Programs\Python\Python313;%LOCALAPPDATA%\Programs\Python\Python313\Scripts;%PATH%"
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
        set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
        set "PATH=%LOCALAPPDATA%\Programs\Python\Python310;%LOCALAPPDATA%\Programs\Python\Python310\Scripts;%PATH%"
    ) else if exist "C:\Program Files\Python313\python.exe" (
        set "PATH=C:\Program Files\Python313;C:\Program Files\Python313\Scripts;%PATH%"
    ) else if exist "C:\Program Files\Python312\python.exe" (
        set "PATH=C:\Program Files\Python312;C:\Program Files\Python312\Scripts;%PATH%"
    ) else if exist "C:\Program Files\Python311\python.exe" (
        set "PATH=C:\Program Files\Python311;C:\Program Files\Python311\Scripts;%PATH%"
    ) else if exist "C:\Python313\python.exe" (
        set "PATH=C:\Python313;C:\Python313\Scripts;%PATH%"
    ) else if exist "C:\Python312\python.exe" (
        set "PATH=C:\Python312;C:\Python312\Scripts;%PATH%"
    ) else if exist "C:\Python311\python.exe" (
        set "PATH=C:\Python311;C:\Python311\Scripts;%PATH%"
    ) else if exist "C:\Python310\python.exe" (
        set "PATH=C:\Python310;C:\Python310\Scripts;%PATH%"
    ) else (
        echo [!] Python PATH me nahi mila. Testing 'py' launcher...
        py --version >nul 2>&1
        if %ERRORLEVEL% EQU 0 (
            set "PYTHON_EXE=py"
        ) else (
            echo [ERROR] Python 3.10+ install nahi mila!
            echo Kripya Python install karein: https://www.python.org/downloads/
            pause
            exit /b 1
        )
    )
)

if not defined PYTHON_EXE set "PYTHON_EXE=python"

:: 2. Auto-activate Virtual Environment if present
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

:: 3. Check and Auto-Install Python Dependencies on First Run
echo [*] Checking libraries and system dependencies...
%PYTHON_EXE% -c "import PyQt6, google.genai, requests, sounddevice, edge_tts, PIL, psutil, tinydb, rank_bm25, thefuzz, keyboard, sklearn" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [*] Pehli baar setup ho raha hai ya missing packages hain.
    echo [*] Auto-installing required packages from requirements.txt...
    %PYTHON_EXE% -m pip install -r requirements.txt
    if %ERRORLEVEL% NEQ 0 (
        echo [!] Warning: Pip install had warnings. Continuing anyway...
    ) else (
        echo [OK] Sabhi zaroori packages safaltapoorvak install ho gaye!
    )
    echo.
)

:: 4. Run Preflight Check (Auto-downloads Piper Hindi voice, models, SFX, icons)
echo [*] Running automated pre-flight checks and model verification...
%PYTHON_EXE% scripts\preflight_check.py

:: 5. Hands-Free Launch (Zero Enter required)
echo [*] Starting J.A.R.V.I.S. neural interface...
echo.
%PYTHON_EXE% main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ======================================================================
    echo [INFO] J.A.R.V.I.S. band ho gaya ya runtime warning aayi.
    echo ======================================================================
    echo.
    pause
)

