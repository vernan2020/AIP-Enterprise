# AIP Enterprise Demo 0.9

This product slice provides a deterministic, executable demo experience for AIP Enterprise.

## Run

Activate the virtual environment and run:

```bash
python -m aip.ui.application.main
```

## Modes

- DEMO: deterministic demo data and read-only execution.
- CONFIGURED: uses configured external source flags when supplied.

## Notes

- No credentials are embedded.
- No financial logic is implemented in the UI.
- The demo uses existing application and UI modules through dependency injection.
