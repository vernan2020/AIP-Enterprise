# Troubleshooting

## Qt display errors in Codespaces
Codespaces does not provide a native desktop display for Qt applications. Use the offscreen backend for validation:

```bash
QT_QPA_PLATFORM=offscreen timeout 10s aip-enterprise
```

## No PYTHONPATH required
After installation, the package should resolve with the standard Python import path. If imports fail, verify the environment was created from a fresh virtual environment and the package was installed with `pip install -e .` or `pip install dist/*.whl`.
