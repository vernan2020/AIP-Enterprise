@echo off
setlocal EnableExtensions
cd /d "%~dp0"
REM Solo lectura: inspecciona rutas/nombres, nunca carga otro corte ni datos DEMO.
set "AIP_EXECUTION_MODE=CONFIGURED"
set "AIP_DEMO_MODE_ENABLED=false"
if exist "config\runtime.local.cmd" (
    call "config\runtime.local.cmd" >nul
    if errorlevel 1 exit /b 2
)
if not exist ".venv\Scripts\python.exe" (
    echo BLOCKED: falta entorno Python institucional.
    exit /b 2
)
set "PYTHONPATH=%CD%\src"
".venv\Scripts\python.exe" -m aip.product.configured.irrbb.investment_master_path_diagnostic %*
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
