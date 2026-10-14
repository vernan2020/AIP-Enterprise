@echo off
REM Resolve existing institutional runtime configuration without copying credentials.
REM Caller uses SETLOCAL; this script intentionally does not, so values reach Python.
REM Precedence: explicit override > PREVIEW private config > inherited environment
REM > certified installation private config (read-only).
REM No secret names, values or private paths are echoed.

if defined AIP_RUNTIME_LOCAL_CMD (
    if not exist "%AIP_RUNTIME_LOCAL_CMD%" (
        echo ERROR: AIP_RUNTIME_LOCAL_CMD no se encuentra. No se usa DEMO.
        exit /b 2
    )
    call "%AIP_RUNTIME_LOCAL_CMD%"
    if errorlevel 1 (
        echo ERROR: la configuracion institucional explicita fallo.
        exit /b 2
    )
    echo AIP: configuracion institucional explicita cargada.
    exit /b 0
)

if exist "config\runtime.local.cmd" (
    call "config\runtime.local.cmd"
    if errorlevel 1 (
        echo ERROR: la configuracion privada de PREVIEW fallo.
        exit /b 2
    )
    echo AIP: configuracion privada de PREVIEW cargada.
    exit /b 0
)

if defined AIP_BCCR_TOKEN (
    echo AIP: credencial BCCR heredada del entorno de Windows.
    exit /b 0
)

REM Trusted institutional source: execute the existing private CMD in place.
REM Never copy it into PREVIEW, GitHub, a ZIP, or a diagnostic report.
if exist "C:\Proyectos\AIP-TIR5-RC1\AIP-Enterprise-release-core-v1.0\config\runtime.local.cmd" (
    call "C:\Proyectos\AIP-TIR5-RC1\AIP-Enterprise-release-core-v1.0\config\runtime.local.cmd"
    if errorlevel 1 (
        echo ERROR: la configuracion privada certificada fallo.
        exit /b 2
    )
    echo AIP: configuracion institucional certificada cargada sin copiarla.
    exit /b 0
)

echo AIP: sin archivo privado local detectado; se conserva el entorno existente.
exit /b 0
