@echo off
setlocal
py -3.13 -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e .[dev]
echo.
echo Instalacion completada.
endlocal
