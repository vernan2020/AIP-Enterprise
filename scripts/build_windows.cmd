@echo off
setlocal
python -m pip install -U pyinstaller
pyinstaller packaging/aip-enterprise.spec
