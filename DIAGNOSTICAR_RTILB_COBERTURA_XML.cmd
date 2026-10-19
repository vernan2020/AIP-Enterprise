@echo off
setlocal
cd /d "%~dp0"
REM Diagnostico de cobertura contractual XML CONFIA; solo lectura.
REM No calcula flujos ni bandas y no modifica formulas RTILB certificadas.
set "AIP_EXECUTION_MODE=CONFIGURED"
set "AIP_DEMO_MODE_ENABLED=false"
set "PYTHONPATH=%CD%\src"
if exist "config\runtime.local.cmd" (
    call "config\runtime.local.cmd" >nul 2>&1
    if errorlevel 1 (
        echo ERROR: No se pudo cargar configuracion institucional local.
        exit /b 2
    )
)
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m aip.product.configured.irrbb.xml_contractual_coverage_cli %*
) else (
    python -m aip.product.configured.irrbb.xml_contractual_coverage_cli %*
)
set "AIP_RTILB_COVERAGE_RC=%ERRORLEVEL%"
if not "%AIP_RTILB_COVERAGE_RC%"=="0" echo RTILB: Diagnostico contractual bloqueado. Revise JSON anterior.
exit /b %AIP_RTILB_COVERAGE_RC%
