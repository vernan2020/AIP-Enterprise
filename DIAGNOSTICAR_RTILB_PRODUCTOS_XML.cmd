@echo off
setlocal
cd /d "%~dp0"
REM RTILB: diagnóstico agregado por producto, solo lectura.
set "AIP_EXECUTION_MODE=CONFIGURED"
set "AIP_DEMO_MODE_ENABLED=false"
set "PYTHONPATH=%CD%\src"
if exist "config\runtime.local.cmd" (
    call "config\runtime.local.cmd" >nul 2>&1
    if errorlevel 1 exit /b 2
)
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m aip.product.configured.irrbb.xml_contractual_gap_drilldown_cli %*
) else (
    python -m aip.product.configured.irrbb.xml_contractual_gap_drilldown_cli %*
)
exit /b %ERRORLEVEL%
