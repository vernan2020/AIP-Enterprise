@echo off
setlocal EnableExtensions
cd /d "%~dp0"
REM Solo lectura de matriz institucional y sin datos DEMO ni carga en efectivo.
set "AIP_EXECUTION_MODE=CONFIGURED"
set "AIP_DEMO_MODE_ENABLED=false"
REM Mismo resolver que run_aip_configured: respeta override, PREVIEW y release read-only.
call "scripts\launch\load_existing_institutional_runtime.cmd"
if errorlevel 1 (
    echo BLOCKED: configuracion institucional no disponible.
    exit /b 2
)
REM La configuracion privada nunca puede habilitar el modo DEMO.
set "AIP_EXECUTION_MODE=CONFIGURED"
set "AIP_DEMO_MODE_ENABLED=false"
if not exist ".venv\Scripts\python.exe" (
    echo BLOCKED: falta el Python virtual institucional.
    exit /b 2
)
set "PYTHONPATH=%CD%\src"
".venv\Scripts\python.exe" -m aip.product.configured.liquidity.sugef210_financial_plan_cli %*
set "RESULT=%ERRORLEVEL%"
endlocal & exit /b %RESULT%
