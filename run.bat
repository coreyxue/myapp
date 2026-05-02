@echo off
REM ComicForge launcher for Windows 11
REM Usage: double-click run.bat, or run from PowerShell / cmd.

setlocal
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

where py >nul 2>&1
if %ERRORLEVEL%==0 (
    set PY=py -3
) else (
    where python >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo [error] Python 3.10+ not found. Install from https://www.python.org/downloads/
        pause
        exit /b 1
    )
    set PY=python
)

if not exist .venv (
    echo [setup] creating venv...
    %PY% -m venv .venv
    if %ERRORLEVEL% NEQ 0 ( pause & exit /b 1 )
)

call .venv\Scripts\activate.bat
if %ERRORLEVEL% NEQ 0 ( pause & exit /b 1 )

python -c "import comicforge" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [setup] installing dependencies...
    python -m pip install --upgrade pip
    python -m pip install -e .
    if %ERRORLEVEL% NEQ 0 ( pause & exit /b 1 )
)

set COMICFORGE_LLM=%COMICFORGE_LLM%
if "%COMICFORGE_LLM%"=="" set COMICFORGE_LLM=ollama

set PORT=%PORT%
if "%PORT%"=="" set PORT=8765

echo [run] http://127.0.0.1:%PORT%
start "" "http://127.0.0.1:%PORT%"
python -m uvicorn comicforge.server:app --host 127.0.0.1 --port %PORT%

endlocal
