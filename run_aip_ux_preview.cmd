@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo   AIP ENTERPRISE V4.5.1 - RUNTIME REAL CONFIGURED
echo   Misma aplicacion AIP, mismas fuentes y conectores institucionales.
echo   El release certificado permanece sin modificaciones.
echo ============================================================
echo.

if not "%~1"=="" (
    echo ERROR: este lanzador solo admite la herramienta CONFIGURED real.
    echo Para QA aislado se usan exclusivamente los tests automaticos.
    exit /b 2
)

if not exist ".venv\Scripts\python.exe" (
    echo Creando entorno Python 3.13 solo para el codigo en desarrollo...
    py -3.13 -m venv ".venv"
    if errorlevel 1 (
        echo ERROR: no se encontro Python 3.13.
        exit /b 1
    )
)

if not exist ".venv\.preview-installed" (
    echo Instalando dependencias para ejecutar el AIP real V4.5.1...
    ".venv\Scripts\python.exe" -m pip install -e .
    if errorlevel 1 (
        echo ERROR: no se instalaron las dependencias.
        exit /b 1
    )
    echo installed> ".venv\.preview-installed"
)

if defined AIP_RUNTIME_LOCAL_CMD (
    echo Usando configuracion institucional existente por AIP_RUNTIME_LOCAL_CMD.
) else (
    echo Buscando config\runtime.local.cmd o rutas institucionales detectadas.
)

REM This is the ACTUAL AIP application, not synthetic demonstration data.
call run_aip_configured.cmd
set "AIP_V451_EXIT=%errorlevel%"
if not "%AIP_V451_EXIT%"=="0" (
    echo.
    echo ERROR: preflight o apertura de AIP con fuentes reales fallido.
    echo Validar configuracion institucional y conectividad, sin usar DEMO.
)
endlocal & exit /b %AIP_V451_EXIT%
