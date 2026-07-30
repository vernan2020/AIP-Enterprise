# AIP Enterprise

Plataforma de escritorio para la gestión integral del portafolio de inversiones de Coopealianza R.L.

## Release

**1.0 RC1 – Packaging and installation readiness**

Incluye instalación editable, instalación estándar, punto de entrada canónico vía `python -m aip`, comando `aip-enterprise`, validación offscreen para Codespaces y base de empaquetado para Windows.

## Requisitos

- Python 3.13
- pip
- PySide6 runtime support

## Instalación editable

```bash
python -m pip install -e ".[dev]"
```

## Instalación estándar

```bash
python -m build
python -m pip install dist/aip_enterprise-1.0.0rc1-py3-none-any.whl
```

## Ejecución

```bash
python -m aip
aip-enterprise
```

## Validación offscreen

```bash
QT_QPA_PLATFORM=offscreen timeout 10s aip-enterprise
```

La salida de código 124 indica que la aplicación permaneció activa hasta el timeout, lo cual es el resultado esperado en ambientes sin pantalla nativa.

## Pruebas

```bash
pytest
```

## Validación

```bash
python -m compileall src tests
python -m mypy src
```

## Licencia

Propiedad exclusiva de Coopealianza R.L. Uso interno.
