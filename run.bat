@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title MarianaOS Agent
echo.
echo  ========================================
echo   MarianaOS — Desktop AI Agent
echo  ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python not found on PATH.
  echo Install Python 3.10+ and enable "Add to PATH".
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creating virtual environment (.venv)...
  python -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Failed to create .venv
    pause
    exit /b 1
  )
  set "NEED_INSTALL=1"
) else (
  echo [1/3] Virtual environment found.
  set "NEED_INSTALL=0"
)

echo [2/3] Activating .venv...
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
  echo [ERROR] Failed to activate .venv
  pause
  exit /b 1
)

REM Always use venv interpreters explicitly
set "VENV_PY=.venv\Scripts\python.exe"
set "VENV_PIP=.venv\Scripts\python.exe -m pip"

REM Install deps on first create, or if a core package is missing
"%VENV_PY%" -c "import google.genai, anthropic, telegram, openai, pydantic_settings" >nul 2>&1
if errorlevel 1 set "NEED_INSTALL=1"

if "%NEED_INSTALL%"=="1" (
  echo [2/3] Installing / updating dependencies...
  "%VENV_PY%" -m pip install --upgrade pip
  "%VENV_PY%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [ERROR] pip install failed
    pause
    exit /b 1
  )
) else (
  echo [2/3] Dependencies OK.
)

echo [3/3] Starting MarianaOS...
echo.
"%VENV_PY%" main.py
set "EXITCODE=%ERRORLEVEL%"

echo.
if not "%EXITCODE%"=="0" (
  echo [ERROR] MarianaOS exited with code %EXITCODE%
)
pause
endlocal & exit /b %EXITCODE%
