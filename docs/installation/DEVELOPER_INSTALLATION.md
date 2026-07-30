# Developer installation

## Prerequisites
- Python 3.13
- pip
- Qt runtime support for PySide6

## Editable install
```bash
python -m pip install -e ".[dev]"
```

## Start commands
```bash
python -m aip
aip-enterprise
```

## Offscreen validation
```bash
QT_QPA_PLATFORM=offscreen timeout 10s aip-enterprise
```

Exit code 124 indicates the Qt event loop remained active until the timeout.
