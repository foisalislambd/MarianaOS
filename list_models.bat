@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title MarianaOS — list models

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python not found on PATH.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating .venv and installing dependencies...
  python -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Failed to create .venv
    pause
    exit /b 1
  )
  call ".venv\Scripts\activate.bat"
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
) else (
  call ".venv\Scripts\activate.bat"
)

".venv\Scripts\python.exe" list_models.py %*
set "EXITCODE=%ERRORLEVEL%"
echo.
pause
endlocal & exit /b %EXITCODE%
