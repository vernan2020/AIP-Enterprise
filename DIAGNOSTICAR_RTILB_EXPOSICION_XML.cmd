@echo off
setlocal
cd /d "%~dp0"
REM Auditoria de saldos contractuales: solo lectura; no calcula bandas RTILB.
set "AIP_EXECUTION_MODE=CONFIGURED"
set "AIP_DEMO_MODE_ENABLED=false"
if exist "config\runtime.local.cmd" (
    call "config\runtime.local.cmd" >nul 2>&1
    if errorlevel 1 exit /b 2
)
set "PYTHONPATH=%CD%\src"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m aip.product.configured.irrbb.xml_contractual_exposure_audit_cli %*
) else (
    python -m aip.product.configured.irrbb.xml_contractual_exposure_audit_cli %*
)
exit /b %ERRORLEVEL%
