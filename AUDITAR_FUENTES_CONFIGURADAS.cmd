@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call "scripts\launch\load_existing_institutional_runtime.cmd"
if errorlevel 1 exit /b 2
if not exist ".venv\Scripts\python.exe" (
  echo No se encuentra el entorno Python de AIP-V451-PREVIEW.
  exit /b 2
)
".venv\Scripts\python.exe" "scripts\qa\audit_configured_sources.py"
set "RESULTADO=%errorlevel%"
endlocal & exit /b %RESULTADO%
