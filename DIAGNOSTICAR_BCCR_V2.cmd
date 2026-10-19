@echo off
setlocal EnableExtensions
cd /d "%~dp0"
REM Read-only direct diagnostic of official BCCR SDDE v2.
REM Loads ONLY existing private configuration; does not print user, email or token.
set "AIP_EXECUTION_MODE=CONFIGURED"
set "AIP_DEMO_MODE_ENABLED=false"
set "PYTHONPATH=%CD%\src"
if exist "config\runtime.local.cmd" (
    call "config\runtime.local.cmd" >nul 2>&1
    if errorlevel 1 (
        echo BCCR SDDE v2: ERROR al cargar la configuracion privada.
        exit /b 2
    )
)
if not exist ".venv\Scripts\python.exe" (
    echo BCCR SDDE v2: no se encontro Python de AIP PREVIEW.
    exit /b 2
)
".venv\Scripts\python.exe" -m aip.integration.bccr.connector.sdde_v2_diagnostic %*
set "AIP_BCCR_V2_RESULT=%ERRORLEVEL%"
if not "%AIP_BCCR_V2_RESULT%"=="0" echo BCCR SDDE v2: revisar diagnostico, no se muestran datos inventados.
exit /b %AIP_BCCR_V2_RESULT%
