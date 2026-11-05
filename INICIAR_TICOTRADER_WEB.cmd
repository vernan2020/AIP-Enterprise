@echo off
setlocal
cd /d "%~dp0"
if not exist .venv-ticotrader\Scripts\python.exe (
  py -3.13 -m venv .venv-ticotrader
  if errorlevel 1 exit /b 1
  .venv-ticotrader\Scripts\python.exe -m pip install -r ticotrader_web\requirements.txt
  if errorlevel 1 exit /b 1
)
if not exist ticotrader_web\.env (
  .venv-ticotrader\Scripts\python.exe ticotrader_web\configure.py
  if errorlevel 1 exit /b 1
)
echo TicoTrader Web: http://127.0.0.1:8080
.venv-ticotrader\Scripts\python.exe ticotrader_web\start.py
