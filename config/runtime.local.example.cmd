@echo off
REM Copy this file to config\runtime.local.cmd only when local overrides are needed.
REM Never commit runtime.local.cmd because it may contain credentials.

REM BCCR live API credentials. If omitted, Macro Intelligence uses persisted official history.
REM set "AIP_BCCR_NAME=YOUR_REGISTERED_NAME"
REM set "AIP_BCCR_EMAIL=YOUR_REGISTERED_EMAIL"
REM set "AIP_BCCR_TOKEN=YOUR_TOKEN"

REM Optional explicit source paths. AIP auto-discovers the institutional paths when available.
REM set "AIP_PORTFOLIO_ROOT=C:\Users\%%USERNAME%%\COOPEALIANZA R.L\Seidy Fonseca Hernandez - inversiones"
REM set "AIP_ICL_ROOT=C:\Users\%%USERNAME%%\COOPEALIANZA R.L\Liquidez e Inversiones - Documentos\General\Análisis Financiero"
REM set "AIP_DATA_CUTOFF_DATE=2026-08-27"

REM Official SUGEF financial/accounting exports (.csv, .xls or .xlsx).
REM Keep the automatic download endpoint unset until its public contract is validated.
REM set "AIP_SUGEF_FINANCIAL_ENABLED=true"
REM set "AIP_SUGEF_FINANCIAL_ROOT=C:\Datos\SUGEF\Informacion Financiera"
REM set "AIP_SUGEF_FINANCIAL_FILE_PATTERN=*"
