@echo off
setlocal
cd /d "%~dp0"
REM Read-only: validate real SICVECA Brechas/Calce from configured institutional root.
REM No file copying, no database mutation and no changes to certified RTILB formulas.
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
    ".venv\Scripts\python.exe" -m aip.product.configured.irrbb.regulatory_xml_readiness_cli %*
) else (
    python -m aip.product.configured.irrbb.regulatory_xml_readiness_cli %*
)
set "AIP_RTILB_XML_DIAG_RC=%ERRORLEVEL%"
if not "%AIP_RTILB_XML_DIAG_RC%"=="0" echo RTILB XML: BLOQUEADO o fuente no configurada. Verifique JSON anterior.
exit /b %AIP_RTILB_XML_DIAG_RC%
