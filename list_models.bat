@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

title MarianaOS - list models

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python not found on PATH.
  pause
  exit /b 1
)

set "VENV_PY=%~dp0.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
  echo Creating .venv and installing dependencies...
  python -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Failed to create .venv
    pause
    exit /b 1
  )
  "%VENV_PY%" -m pip install --upgrade pip
  "%VENV_PY%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [ERROR] pip install failed
    pause
    exit /b 1
  )
)

"%VENV_PY%" list_models.py %*
set "EXITCODE=!ERRORLEVEL!"
echo.
pause
exit /b !EXITCODE!
