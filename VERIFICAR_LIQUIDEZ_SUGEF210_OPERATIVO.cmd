@echo off
setlocal EnableExtensions
cd /d "%~dp0"
REM Misma configuracion privada de la AIP real: sin copia de tokens ni datos DEMO.
call "scripts\launch\load_existing_institutional_runtime.cmd"
if errorlevel 1 (
    echo BLOCKED: configuracion institucional sin acceso.
    exit /b 2
)
set "AIP_EXECUTION_MODE=CONFIGURED"
set "AIP_DEMO_MODE_ENABLED=false"
if not exist ".venv\Scripts\python.exe" (
    echo BLOCKED: falta .venv\Scripts\python.exe. Ejecutar run_aip_ux_preview.cmd para instalar dependencias.
    exit /b 2
)
if "%~1"=="" (
    echo USO: VERIFICAR_LIQUIDEZ_SUGEF210_OPERATIVO.cmd --self-test
    echo       VERIFICAR_LIQUIDEZ_SUGEF210_OPERATIVO.cmd --cutoff YYYY-MM-DD
    echo PARA FLUJO: agregar --scenario BASE --approval "archivo.json" --bank "conciliacion.json"
    exit /b 2
)
set "PYTHONPATH=%CD%\src"
".venv\Scripts\python.exe" -m aip.product.configured.liquidity.sugef210_operational_readiness %*
set "AIP_LIQ_EXIT=%errorlevel%"
endlocal & exit /b %AIP_LIQ_EXIT%
