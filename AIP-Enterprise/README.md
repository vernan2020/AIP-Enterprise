# AIP Enterprise

Plataforma de escritorio para la gestión integral del portafolio de inversiones de Coopealianza R.L.

## Release

**R0.1.0 – Foundation**

Incluye configuración YAML validada, logging con Loguru, inyección de dependencias, DuckDB, auditoría básica, interfaz PySide6 y pruebas unitarias.

## Requisitos

- Windows 10/11
- Python 3.13

## Instalación en CMD

```cmd
py -3.13 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e .[dev]
```

## Ejecución

```cmd
python main.py
```

## Pruebas

```cmd
pytest
```

## Validación

```cmd
ruff check src tests
mypy src
```

## Licencia

Propiedad exclusiva de Coopealianza R.L. Uso interno.
