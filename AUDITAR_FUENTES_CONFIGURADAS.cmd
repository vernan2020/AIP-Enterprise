@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if defined AIP_RUNTIME_LOCAL_CMD (
  if not exist "%AIP_RUNTIME_LOCAL_CMD%" (
    echo No se encuentra el archivo privado indicado en AIP_RUNTIME_LOCAL_CMD.
    exit /b 2
  )
  call "%AIP_RUNTIME_LOCAL_CMD%"
  if errorlevel 1 exit /b 2
) else (
  if exist "config\runtime.local.cmd" (
    call "config\runtime.local.cmd"
    if errorlevel 1 exit /b 2
  )
)
if not exist ".venv\Scripts\python.exe" (
  echo No se encuentra el entorno Python de AIP-V451-PREVIEW.
  exit /b 2
)
".venv\Scripts\python.exe" "scripts\qa\audit_configured_sources.py"
set "RESULTADO=%errorlevel%"
endlocal & exit /b %RESULTADO%
