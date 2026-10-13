@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo   AIP ENTERPRISE V4.5.1 - VISTA PREVIA CON DATOS REALES
echo   Rama: feature/ux-v4-5-1-performance-responsiveness
echo   No se modifica el release certificado.
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
    echo Instalando las dependencias del codigo de desarrollo...
    ".venv\Scripts\python.exe" -m pip install -e .
    if errorlevel 1 (
        echo ERROR: instalacion de dependencias fallida.
        pause
        exit /b 1
    )
    echo installed> ".venv\.preview-installed"
)

REM The REAL configured runtime is always the default entry point.
REM Demo is opt-in for developer-only tests; never silently replace live data.
if /I "%~1"=="demo" goto demo
if /I not "%~1"=="configured" if not "%~1"=="" (
    echo Uso: run_aip_ux_preview.cmd [configured ^| demo]
    exit /b 2
)

echo Iniciando AIP CONFIGURED con las fuentes existentes.
if not exist "config\runtime.local.cmd" (
    echo AVISO: no existe config\runtime.local.cmd en esta copia.
    echo Se usaran rutas institucionales detectadas y variables de entorno.
    echo Si su instalacion certificada usa overrides locales, copiarlos
    echo UNICAMENTE a esta copia local. No subir credenciales a GitHub.
)
call run_aip_configured.cmd
set "AIP_PREVIEW_EXIT=%errorlevel%"
if not "%AIP_PREVIEW_EXIT%"=="0" (
    echo.
    echo ERROR: inicio con datos reales o preflight institucional fallido.
    echo Revise config\runtime.local.cmd y accesibilidad de fuentes.
    pause
)
exit /b %AIP_PREVIEW_EXIT%

:demo
echo MODO DEMO ACTIVADO EXPLICITAMENTE: no carga datos institucionales.
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
exit /b %errorlevel%
