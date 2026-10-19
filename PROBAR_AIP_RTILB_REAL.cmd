@echo off
setlocal EnableExtensions
cd /d "%~dp0"
REM Pruebas solo lectura: no altera fuentes, DB ni formulas certificadas.
set "AIP_EXECUTION_MODE=CONFIGURED"
set "AIP_DEMO_MODE_ENABLED=false"
if not exist ".venv\Scripts\python.exe" (
    echo BLOQUEADO: Python institucional de PREVIEW no encontrado.
    exit /b 2
)
call "scripts\launch\load_existing_institutional_runtime.cmd" >nul
if errorlevel 1 (
    echo BLOQUEADO: configuracion institucional no disponible.
    exit /b 2
)
set "PYTHONPATH=%CD%\src"
".venv\Scripts\python.exe" "scripts\qa\run_readonly_rtilb_validation.py" %*
set "RESULT=%ERRORLEVEL%"
endlocal & exit /b %RESULT%
