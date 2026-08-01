from __future__ import annotations

import ntpath
import os
from pathlib import Path, PureWindowsPath
from typing import Any


def _is_windows_path(value: str) -> bool:
    return value.startswith("\\\\") or len(value) >= 2 and value[1] == ":"


def _normalize_path(value: str) -> str:
    if value.startswith("\\\\") or len(value) >= 2 and value[1] == ":":
        return ntpath.normpath(value.replace("/", "\\"))
    return str(Path(value))


def expand_environment_path(value: str | None, *, base_root: str | None = None) -> str | None:
    if not value:
        return None
    expanded = os.path.expandvars(os.path.expanduser(value))
    if not expanded:
        return None
    if base_root and not _is_windows_path(expanded) and not Path(expanded).is_absolute():
        expanded = os.path.join(base_root, expanded)
    return _normalize_path(expanded)


def resolve_institutional_path(value: str | None, *, base_root: str | None = None) -> str | None:
    if not value:
        return None
    expanded = os.path.expandvars(os.path.expanduser(value))
    if not expanded:
        return None
    if base_root:
        base_value = os.path.expandvars(os.path.expanduser(base_root))
        if _is_windows_path(expanded):
            candidate = expanded
        elif _is_windows_path(base_value):
            candidate = os.path.join(base_value, expanded)
        elif not Path(expanded).is_absolute():
            candidate = os.path.join(base_value, expanded)
        else:
            candidate = expanded
    else:
        candidate = expanded
    return _normalize_path(candidate)


def build_institutional_path(*parts: Any, base_root: str | None = None) -> str | None:
    if not parts:
        return None
    root = base_root
    if root is None:
        return _normalize_path(os.path.join(*[str(part) for part in parts]))
    if _is_windows_path(root):
        return str(PureWindowsPath(root).joinpath(*[str(part) for part in parts]))
    return str(Path(root).joinpath(*[str(part) for part in parts]))
