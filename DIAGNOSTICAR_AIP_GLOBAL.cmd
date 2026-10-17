@echo off
setlocal EnableExtensions
cd /d "%~dp0"
REM Revision transversal de fuentes AIP; nunca consulta API, SQL ni modifica datos.
set "AIP_EXECUTION_MODE=CONFIGURED"
set "AIP_DEMO_MODE_ENABLED=false"
call "scripts\launch\load_existing_institutional_runtime.cmd"
if errorlevel 1 exit /b 2
set "PYTHONPATH=%CD%\src"
if not exist ".venv\Scripts\python.exe" (
    echo AIP: entorno Python local no encontrado.
    exit /b 2
)
".venv\Scripts\python.exe" -m aip.product.configured.global_source_preflight_cli %*
set "RESULT=%ERRORLEVEL%"
endlocal & exit /b %RESULT%
