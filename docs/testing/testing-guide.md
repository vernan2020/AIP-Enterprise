# Testing Guide

## Test Layers

- Unit tests validate isolated behavior.
- Integration tests validate cross-module workflows.

## Running the Suite

```bash
pytest tests/unit -q -W error
pytest tests/integration -q -W error
pytest --cov=src --cov-report=term-missing -q -W error
```
