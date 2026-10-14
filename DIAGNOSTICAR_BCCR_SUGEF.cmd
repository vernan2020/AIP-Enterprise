@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "AIP_EXECUTION_MODE=CONFIGURED"
set "AIP_DEMO_MODE_ENABLED=false"
call "scripts\launch\load_existing_institutional_runtime.cmd"
if errorlevel 1 exit /b 2
if not exist ".venv\Scripts\python.exe" (
    echo No se encontro Python del entorno de desarrollo.
    exit /b 2
)
set "PYTHONPATH=%CD%\src"
".venv\Scripts\python.exe" "scripts\qa\diagnose_official_feeds.py" --live --period 2026-09
set "RESULTADO=%errorlevel%"
endlocal & exit /b %RESULTADO%
