@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

title MarianaOS Agent
echo.
echo  ========================================
echo   MarianaOS - Desktop AI Agent
echo  ========================================
echo.

where python >nul 2>&1
if errorlevel 1 goto :no_python

set "VENV_PY=%~dp0.venv\Scripts\python.exe"
set "NEED_INSTALL=0"

if not exist "%VENV_PY%" (
  echo [1/3] Creating virtual environment .venv ...
  python -m venv .venv
  if errorlevel 1 goto :venv_fail
  set "NEED_INSTALL=1"
) else (
  echo [1/3] Virtual environment found.
)

echo [2/3] Using venv Python...
if not exist "%VENV_PY%" goto :venv_fail

"%VENV_PY%" -c "import google.genai" >nul 2>&1
if errorlevel 1 set "NEED_INSTALL=1"
"%VENV_PY%" -c "import anthropic" >nul 2>&1
if errorlevel 1 set "NEED_INSTALL=1"
"%VENV_PY%" -c "import telegram" >nul 2>&1
if errorlevel 1 set "NEED_INSTALL=1"
"%VENV_PY%" -c "import openai" >nul 2>&1
if errorlevel 1 set "NEED_INSTALL=1"

if "!NEED_INSTALL!"=="1" (
  echo [2/3] Installing dependencies from requirements.txt ...
  "%VENV_PY%" -m pip install --upgrade pip
  if errorlevel 1 goto :pip_fail
  "%VENV_PY%" -m pip install -r requirements.txt
  if errorlevel 1 goto :pip_fail
) else (
  echo [2/3] Dependencies OK.
)

echo [3/3] Starting MarianaOS...
echo.
"%VENV_PY%" main.py
set "EXITCODE=!ERRORLEVEL!"

echo.
if not "!EXITCODE!"=="0" echo [ERROR] MarianaOS exited with code !EXITCODE!
pause
exit /b !EXITCODE!

:no_python
echo [ERROR] Python not found on PATH.
echo Install Python 3.10+ and enable Add to PATH.
pause
exit /b 1

:venv_fail
echo [ERROR] Failed to create or find .venv
pause
exit /b 1

:pip_fail
echo [ERROR] pip install failed
pause
exit /b 1
