@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "AIP_EXECUTION_MODE=CONFIGURED"
set "AIP_DEMO_MODE_ENABLED=false"
if defined AIP_RUNTIME_LOCAL_CMD (
    if not exist "%AIP_RUNTIME_LOCAL_CMD%" (
        echo No se encontro el archivo de configuracion externa.
        exit /b 2
    )
    call "%AIP_RUNTIME_LOCAL_CMD%"
    if errorlevel 1 exit /b 2
) else (
    if exist "config\runtime.local.cmd" (
        call "config\runtime.local.cmd"
        if errorlevel 1 exit /b 2
    )
)
if not exist ".venv\Scripts\python.exe" (
    echo No se encontro Python del entorno de desarrollo.
    exit /b 2
)
set "PYTHONPATH=%CD%\src"
".venv\Scripts\python.exe" "scripts\qa\diagnose_official_feeds.py" --live --period 2026-09
set "RESULTADO=%errorlevel%"
endlocal & exit /b %RESULTADO%
