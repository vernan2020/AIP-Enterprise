@echo off
setlocal EnableExtensions
REM Package may be extracted anywhere; ONLY the known development PREVIEW is updated.
set "AIP_PATCH_ROOT=%~dp0"
REM A trailing backslash before a closing quote escapes the quote in Python argv.
REM Append dot to keep a valid absolute directory path without trailing backslash.
if not defined AIP_PREVIEW_ROOT set "AIP_PREVIEW_ROOT=C:\Proyectos\AIP-V451-PREVIEW"
if /I not "%AIP_PREVIEW_ROOT:~-16%"=="AIP-V451-PREVIEW" (
    echo ERROR: destino no es la instalacion PREVIEW.
    exit /b 2
)
if not exist "%AIP_PREVIEW_ROOT%\src\aip\" (
    echo ERROR: no se encontro AIP-V451-PREVIEW real.
    exit /b 2
)
if not exist "%AIP_PREVIEW_ROOT%\run_aip_ux_preview.cmd" (
    echo ERROR: falta el lanzador institucional PREVIEW.
    exit /b 2
)
if exist "%AIP_PREVIEW_ROOT%\.venv\Scripts\python.exe" (
    "%AIP_PREVIEW_ROOT%\.venv\Scripts\python.exe" "%AIP_PATCH_ROOT%tools\apply_preview_patch.py" --package-root "%AIP_PATCH_ROOT%." --preview-root "%AIP_PREVIEW_ROOT%" %*
) else (
    py -3.13 "%AIP_PATCH_ROOT%tools\apply_preview_patch.py" --package-root "%AIP_PATCH_ROOT%." --preview-root "%AIP_PREVIEW_ROOT%" %*
)
set "AIP_PATCH_EXIT=%errorlevel%"
if not "%AIP_PATCH_EXIT%"=="0" (
    echo ERROR: actualizacion rechazada; verifique permisos y que AIP este cerrado.
)
endlocal & exit /b %AIP_PATCH_EXIT%
