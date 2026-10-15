@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo No se encuentra Python del entorno de desarrollo.
    exit /b 2
)
set "PYTHONPATH=%CD%\src"
echo INSPECCION SIN CAMBIOS: HISTORICOS CERTIFICADO VS PREVIEW
".venv\Scripts\python.exe" "scripts\qa\recover_macro_history.py"
endlocal
