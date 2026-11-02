@echo off
setlocal EnableExtensions
cd /d "%~dp0"
REM Abre la misma aplicacion AIP V4.5.1 PREVIEW, nunca un demo separado.
REM Navegar a Liquidez / Flujo proyectado SUGEF 2-10.
if not exist "run_aip_ux_preview.cmd" (
    echo BLOCKED: instalacion AIP V4.5.1 PREVIEW incompleta.
    exit /b 2
)
echo AIP V4.5.1 CONFIGURED - modulo Liquidez / Flujo proyectado SUGEF 2-10
echo El calculo de caja requiere XML, Maestro y autorizaciones institucionales.
call "run_aip_ux_preview.cmd"
set "AIP_LIQ_EXIT=%errorlevel%"
endlocal & exit /b %AIP_LIQ_EXIT%
