@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"

set "AIP_EXECUTION_MODE=CONFIGURED"
set "AIP_DEMO_MODE_ENABLED=false"
set "PYTHONPATH=src"

REM Local secrets/overrides are intentionally not versioned.
if exist "config\runtime.local.cmd" call "config\runtime.local.cmd"

if not defined AIP_FOLDERWATCH_ENABLED set "AIP_FOLDERWATCH_ENABLED=true"
if not defined AIP_VECTOR_ENABLED set "AIP_VECTOR_ENABLED=true"
if not defined AIP_BCCR_ENABLED set "AIP_BCCR_ENABLED=true"
if not defined AIP_BCCR_BASE_URL set "AIP_BCCR_BASE_URL=https://apim.bccr.fi.cr"
if not defined AIP_ALLOW_PRIOR_SOURCE_DATE set "AIP_ALLOW_PRIOR_SOURCE_DATE=true"

REM Self-heal only when manifest-declared critical runtime modules are absent.
python scripts\recovery\runtime_checkpoint_status.py --critical-only >nul 2>&1
if errorlevel 1 (
    echo AIP critical runtime is incomplete. Restoring the certified local checkpoint...
    python scripts\recovery\restore_runtime_checkpoint.py
    if errorlevel 1 (
        echo.
        echo AIP certified runtime restore failed. Review the diagnostics above.
        exit /b 1
    )
)

python -m aip.tools.preflight_runtime
if errorlevel 1 (
    echo.
    echo AIP preflight failed. Review the diagnostics above.
    exit /b 1
)

python -m aip
endlocal
