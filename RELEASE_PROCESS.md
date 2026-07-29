# Release Process

## Semantic Versioning

This project follows Semantic Versioning (SemVer):

- MAJOR: incompatible API changes
- MINOR: backwards-compatible feature additions
- PATCH: backwards-compatible bug fixes

## Release Checklist

1. Confirm the branch is up to date.
2. Run the full test suite.
3. Run linting, formatting, typing, and packaging checks.
4. Update changelog and release notes.
5. Tag the release and push the tag.
6. Publish the build artifacts.

## Release Steps

```bash
python -m pytest
python -m pytest --cov=src --cov-report=term-missing -q -W error
ruff check src tests
black --check src tests
isort --check-only src tests
mypy src tests
python -m compileall src tests
python -m build
```
