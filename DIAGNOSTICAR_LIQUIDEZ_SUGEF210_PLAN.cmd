@echo off
setlocal EnableExtensions
cd /d "%~dp0"
REM Solo lectura de matriz institucional y sin datos DEMO ni carga en efectivo.
set "AIP_EXECUTION_MODE=CONFIGURED"
set "AIP_DEMO_MODE_ENABLED=false"
if exist "config\runtime.local.cmd" (
    call "config\runtime.local.cmd" >nul
    if errorlevel 1 exit /b 2
)
if not exist ".venv\Scripts\python.exe" (
    echo BLOCKED: falta el Python virtual institucional.
    exit /b 2
)
set "PYTHONPATH=%CD%\src"
".venv\Scripts\python.exe" -m aip.product.configured.liquidity.sugef210_financial_plan_cli %*
set "RESULT=%ERRORLEVEL%"
endlocal & exit /b %RESULT%
