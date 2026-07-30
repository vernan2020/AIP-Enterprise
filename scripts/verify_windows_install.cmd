@echo off
setlocal
if exist dist\AIPEnterprise\AIPEnterprise.exe (
  echo Windows packaging artifact available
) else (
  echo Windows packaging artifact not found
  exit /b 1
)
