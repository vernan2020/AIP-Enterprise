"""Resolve the exact-cutoff portfolio master without XML fallback or guessed dates."""

from __future__ import annotations

from datetime import date
from glob import glob
from pathlib import Path

from aip.product.configured.configuration.institutional_paths import (
    expand_environment_path,
)


def find_exact_cutoff_master(
    root: str | None, pattern: str, cutoff: date
) -> tuple[str, int]:
    """Return safe status and candidate count; never return private paths."""
    if not root:
        return "UNCONFIGURED", 0
    resolved = expand_environment_path(root)
    if not resolved or not Path(resolved).is_dir():
        return "ROOT_NOT_AVAILABLE", 0
    if not pattern:
        return "PATTERN_UNCONFIGURED", 0
    try:
        relative = pattern.format(
            year=cutoff.year, month=f"{cutoff.month:02d}", day=f"{cutoff.day:02d}"
        ).replace("\\", "/")
    except (KeyError, ValueError):
        return "INVALID_PATTERN", 0
    pattern_path = Path(relative)
    if pattern_path.is_absolute() or ".." in pattern_path.parts:
        return "INVALID_PATTERN", 0
    exact_stamp = f"{cutoff.day:02d}-{cutoff.month:02d}-{cutoff.year}"
    try:
        candidates = [
            path
            for name in glob(str(Path(resolved) / pattern_path))
            if (path := Path(name)).is_file()
            and exact_stamp in path.stem
            and path.suffix.lower() in {".xls", ".xlsx"}
        ]
    except (OSError, ValueError):
        return "FILE_DISCOVERY_FAILED", 0
    if not candidates:
        return "EXACT_CUTOFF_MASTER_NOT_FOUND", 0
    if len(candidates) > 1:
        return "AMBIGUOUS_MASTER_FILES", len(candidates)
    return "EXACT_CUTOFF_MASTER_FOUND_NOT_CERTIFIED", 1
