@echo off
setlocal EnableExtensions
cd /d "%~dp0"
REM Diagnostico de solo lectura del Maestro institucional, no GAP certificado.
set "AIP_EXECUTION_MODE=CONFIGURED"
set "AIP_DEMO_MODE_ENABLED=false"
if exist "config\runtime.local.cmd" (
    call "config\runtime.local.cmd" >nul
    if errorlevel 1 exit /b 2
)
set "PYTHONPATH=%CD%\src"
if not exist ".venv\Scripts\python.exe" exit /b 2
".venv\Scripts\python.exe" -m aip.product.configured.irrbb.investment_master_cutoff_cli %*
set "RESULT=%ERRORLEVEL%"
endlocal & exit /b %RESULT%
