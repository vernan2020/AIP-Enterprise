@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"
set "AIP_EXECUTION_MODE=CONFIGURED"
set "AIP_DEMO_MODE_ENABLED=false"
set "PYTHONPATH=src"
set "AIP_FOLDERWATCH_ENABLED=true"
set "AIP_VECTOR_ENABLED=true"
set "AIP_BCCR_ENABLED=true"
python -m aip
endlocal
