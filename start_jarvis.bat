@echo off
title SudhirDevOps1 AI Assistant (J.A.R.V.I.S.)
chcp 65001 >nul
cd /d "%~dp0"
color 0B

echo ===================================================
echo     ✦ SUDHIRDEVOPS1 AI ASSISTANT (J.A.R.V.I.S.) ✦
echo ===================================================
echo.

:: 1. Check Python Availability
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
        set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
    ) else (
        echo [ERROR] Python nahi mila! Kripya Python 3.11 ya 3.12 install karein aur PATH me add karein.
        echo Download from: https://www.python.org/downloads/
        echo.
        pause
        exit /b 1
    )
)

:: 2. Auto-activate Virtual Environment if present
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

:: 3. Check and Auto-Install Python Dependencies on First Run
python -c "import PyQt6, google.genai, requests, sounddevice, edge_tts, PIL, psutil" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [*] Pehli baar setup ho raha hai. Missing dependencies auto-install ho rahi hain...
    echo [*] Please wait a moment while packages are being installed...
    echo.
    python -m pip install -r requirements.txt edge-tts
    if %ERRORLEVEL% NEQ 0 (
        echo [!] Warning: Kuch packages install nahi ho paye. Continuing anyway...
    ) else (
        echo [OK] Sabhi zaroori packages safaltapoorvak install ho gaye!
    )
    echo.
)

:: 4. Run Preflight Check (downloads Piper Hindi TTS, SFX assets, icons, openwakeword)
python scripts\preflight_check.py

:: 5. Auto-Create Desktop Shortcut if missing
python -c "
import os, sys
from pathlib import Path
desktop = Path(os.path.expanduser('~/Desktop'))
lnk = desktop / 'J.A.R.V.I.S.lnk'
if not lnk.exists():
    try:
        from ui import MainWindow
        # Invoking desktop shortcut builder via UI helper
        ico_path = Path('config/jarvis.ico').resolve()
        pythonw = Path(sys.executable).parent / 'pythonw.exe'
        target = str(pythonw if pythonw.exists() else sys.executable)
        launcher = str(Path('run_jarvis.pyw').resolve())
        MainWindow._create_lnk_windows(str(lnk), target, launcher, str(Path('.').resolve()), str(ico_path))
        print('  [OK] Desktop Shortcut auto-created on Desktop.')
    except Exception:
        pass
" >nul 2>&1

:: 6. Launch Assistant
echo [*] Launching J.A.R.V.I.S. interface...
python main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ===================================================
    echo [INFO] JARVIS band ho gaya ya koi error aayi.
    echo ===================================================
    echo.
    pause
)
