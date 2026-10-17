"""Resolve the exact-cutoff portfolio master without XML fallback or guessed dates."""

from __future__ import annotations

from datetime import date
from glob import glob
from pathlib import Path

from aip.product.configured.configuration.institutional_paths import (
    expand_environment_path,
)


def resolve_exact_cutoff_master(
    root: str | None, pattern: str, cutoff: date
) -> tuple[str, Path | None, int]:
    """Only exact-cutoff files are eligible; no nearest-date substitution."""
    if not root:
        return "UNCONFIGURED", None, 0
    resolved = expand_environment_path(root)
    if not resolved or not Path(resolved).is_dir():
        return "ROOT_NOT_AVAILABLE", None, 0
    if not pattern:
        return "PATTERN_UNCONFIGURED", None, 0
    try:
        relative = pattern.format(
            year=cutoff.year, month=f"{cutoff.month:02d}", day=f"{cutoff.day:02d}"
        ).replace("\\", "/")
    except (KeyError, ValueError):
        return "INVALID_PATTERN", None, 0
    pattern_path = Path(relative)
    if pattern_path.is_absolute() or ".." in pattern_path.parts:
        return "INVALID_PATTERN", None, 0
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
        return "FILE_DISCOVERY_FAILED", None, 0
    if not candidates:
        return "EXACT_CUTOFF_MASTER_NOT_FOUND", None, 0
    if len(candidates) > 1:
        return "AMBIGUOUS_MASTER_FILES", None, len(candidates)
    return "EXACT_CUTOFF_MASTER_FOUND_NOT_CERTIFIED", candidates[0], 1



def find_exact_cutoff_master(root: str | None, pattern: str, cutoff: date) -> tuple[str, int]:
    """Preserve the existing safe, path-free discovery contract."""
    status, _path, count = resolve_exact_cutoff_master(root, pattern, cutoff)
    return status, count
