@echo off
title J.A.R.V.I.S. Test Runner
cd /d "%~dp0"
chcp 65001 >nul 2>&1
color 0A

echo ======================================================================
echo        J.A.R.V.I.S. TEST SUITE RUNNER
echo        Automated Full Test Suite Execution
echo ======================================================================
echo.

:: 1. Auto-Detect / Auto-Activate Python
set "PYTHON_EXE="

if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "venv\Scripts\python.exe" set "PYTHON_EXE=venv\Scripts\python.exe"
if not defined PYTHON_EXE where python >nul 2>&1 && set "PYTHON_EXE=python"
if not defined PYTHON_EXE py --version >nul 2>&1 && set "PYTHON_EXE=py"

if not defined PYTHON_EXE (
    echo [ERROR] Python environment nahi mila.
    echo Pehle start_jarvis.bat chalayen taaki .venv setup ho.
    pause
    exit /b 1
)

echo [INFO] Using Python: %PYTHON_EXE%
"%PYTHON_EXE%" --version
echo.

:: 2. Verify dependencies
echo [*] Checking test dependencies...
"%PYTHON_EXE%" -c "import pytest, fastapi, httpx" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [*] Installing test dependencies...
    "%PYTHON_EXE%" -m pip install pytest fastapi "uvicorn[standard]" httpx --quiet
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Test dependencies install failed.
        pause
        exit /b 1
    )
)
echo [OK] Test dependencies ready.
echo.

:: 3. Run test suite
echo [*] Starting test suite...
echo.

set PYTHONWARNINGS=ignore::DeprecationWarning,ignore::RuntimeWarning
set PYTHONIOENCODING=utf-8

:: Parse command line args for pytest
set "PYTEST_ARGS=-q --tb=short"
if "%~1"=="" goto :run_tests
if "%~1"=="-h" goto :help
if "%~1"=="--help" goto :help
if "%~1"=="--fast" (
    set "PYTEST_ARGS=-x -q --tb=line"
    goto :run_tests
)
if "%~1"=="--security" (
    set "PYTEST_ARGS=-q --tb=short tests/test_phase0_security.py"
    goto :run_tests
)
if "%~1"=="--learning" (
    set "PYTEST_ARGS=-q --tb=short tests/test_learning_loop.py"
    goto :run_tests
)
if "%~1"=="--mcp" (
    set "PYTEST_ARGS=-q --tb=short tests/test_mcp_manager.py"
    goto :run_tests
)
if "%~1"=="--privacy" (
    set "PYTEST_ARGS=-q --tb=short tests/test_privacy_guard.py"
    goto :run_tests
)
set "PYTEST_ARGS=%*"

:help
echo Usage: run_tests.bat [options]
echo.
echo Options:
echo   (none)        Run full test suite
echo   --fast        Stop on first failure (fast feedback)
echo   --security    Run only Phase 0 security regression tests
echo   --learning    Run only learning loop tests
echo   --mcp         Run only MCP manager tests
echo   --privacy     Run only privacy guard tests
echo   -k "pattern"  Run tests matching pattern (pytest -k)
echo   ^<any pytest args passed through^>
echo.
exit /b 0

:run_tests
echo Running: %PYTHON_EXE% -m pytest %PYTEST_ARGS%
echo ---------------------------------------------------------
"%PYTHON_EXE%" -m pytest %PYTEST_ARGS%

:: Capture exit code
set PYTEST_EXIT=%ERRORLEVEL%
echo ---------------------------------------------------------
echo.

if %PYTEST_EXIT% EQU 0 (
    echo ======================================================================
    echo [SUCCESS] All tests passed!
    echo ======================================================================
) else (
    echo ======================================================================
    echo [FAILURE] Some tests failed (exit code: %PYTEST_EXIT%)
    echo ======================================================================
)

:: Keep window open on failure or if explicitly asked
if "%~1"=="" (
    if %PYTEST_EXIT% NEQ 0 pause
) else (
    pause
)

exit /b %PYTEST_EXIT%