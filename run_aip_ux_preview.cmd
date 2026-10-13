@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo   AIP ENTERPRISE V4.5.1 - VISTA PREVIA DE DESARROLLO
echo   Rama: feature/ux-v4-5-1-performance-responsiveness
echo   Esta ejecucion NO altera el release certificado.
echo ============================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Creando entorno Python 3.13 aislado...
    py -3.13 -m venv ".venv"
    if errorlevel 1 (
        echo ERROR: se requiere Python 3.13 con el lanzador py disponible.
        pause
        exit /b 1
    )
)

if not exist ".venv\.preview-installed" (
    echo Instalando dependencias de la vista previa...
    ".venv\Scripts\python.exe" -m pip install -e .
    if errorlevel 1 (
        echo ERROR: instalacion de dependencias fallida.
        pause
        exit /b 1
    )
    echo installed> ".venv\.preview-installed"
)

if /I "%~1"=="configured" goto configured

echo Abriendo modo DEMO: solo para revisar interfaz y navegacion.
set "AIP_EXECUTION_MODE=DEMO"
set "AIP_DEMO_MODE_ENABLED=true"
set "AIP_CONFIGURED_DIAGNOSTIC_MODE=false"
set "AIP_PORTFOLIO_ROOT="
set "AIP_VECTOR_PATH="
set "AIP_VECTOR_ROOT="
set "AIP_VECTOR_ENABLED=false"
set "AIP_FOLDERWATCH_ENABLED=false"
set "AIP_FOLDER_WATCH_ENABLED=false"
set "AIP_SQLSERVER_ENABLED=false"
set "AIP_SQL_CONNECTOR_ENABLED=false"
set "AIP_CURVES_ENABLED=false"
set "AIP_BCCR_ENABLED=false"
set "PYTHONPATH=%CD%\src"
".venv\Scripts\python.exe" -m aip
if errorlevel 1 (
    echo.
    echo ERROR: no se pudo abrir la vista previa.
    pause
    exit /b 1
)
exit /b 0

:configured
if not exist "config\runtime.local.cmd" (
    echo ERROR: falta config\runtime.local.cmd para ejecutar con fuentes reales.
    echo Copie el archivo privado desde su instalacion institucional validada.
    echo NO suba ese archivo a GitHub.
    pause
    exit /b 1
)
echo Abriendo modo CONFIGURED con sus fuentes locales...
call run_aip_configured.cmd
if errorlevel 1 (
    echo.
    echo ERROR: preflight institucional o arranque fallido.
    pause
    exit /b 1
)
exit /b 0
