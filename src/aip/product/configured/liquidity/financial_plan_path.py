"""Resolve a previously configured institutional plan without copying its contents.

The plan file stays on the Windows/institutional filesystem.  This module
never scans arbitrary directories or guesses a source file from a cutoff.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path


_PLAN_PATH_SETTINGS = (
    "AIP_FINANCIAL_PLAN_2026_PATH",
    "AIP_FINANCIAL_PLAN_PATH",
    "AIP_PLAN_FINANCIERO_2026_PATH",
)


def configured_financial_plan_path(
    environment: Mapping[str, str] | None = None,
) -> Path | None:
    """Return an explicit institutional plan path, if one is configured.

    The caller validates existence and workbook contents.  Returning ``None``
    means no approved path was provided; it never triggers fallback DEMO data.
    """
    values = os.environ if environment is None else environment
    for key in _PLAN_PATH_SETTINGS:
        raw_value = values.get(key, "").strip().strip('"')
        if raw_value:
            return Path(os.path.expandvars(os.path.expanduser(raw_value)))
    return None
