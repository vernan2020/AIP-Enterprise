# Development Guide

## Environment Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e .[dev]
pre-commit install
```

## Validation Commands

```bash
pytest
ruff check src tests
black --check src tests
isort --check-only src tests
mypy src tests
python -m compileall src tests
```
