"""Read-only explanation of why exact-cutoff investment Master discovery failed.

Diagnoses the existing configured root/pattern. Never substitutes a different
cutoff, changes configuration, reads workbook contents or writes to sources.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from glob import glob
from pathlib import Path

from aip.product.configured.configuration.institutional_paths import (
    expand_environment_path,
)
from aip.product.configured.irrbb.investment_master_discovery import (
    resolve_exact_cutoff_master,
)
from aip.product.demo.configuration.environment_loader import EnvironmentLoader

_EXTENSION_SET = frozenset((".xls", ".xlsx"))
_MAX_SCANNED_FILES = 12000
_MAX_MATCHES_REPORTED = 12


def _date_variants(cutoff: date) -> tuple[str, ...]:
    return (
        cutoff.strftime("%d-%m-%Y"),
        cutoff.strftime("%Y-%m-%d"),
        cutoff.strftime("%d_%m_%Y"),
        cutoff.strftime("%Y_%m_%d"),
        cutoff.strftime("%d.%m.%Y"),
        cutoff.strftime("%Y.%m.%d"),
        cutoff.strftime("%d%m%Y"),
        cutoff.strftime("%Y%m%d"),
    )


def _contains_exact_cutoff(stem: str, cutoff: date) -> bool:
    return any(
        re.search(r"(?<!\d)" + re.escape(stamp) + r"(?!\d)", stem) is not None
        for stamp in _date_variants(cutoff)
    )


def inspect_master_paths(*, root: str | None, pattern: str, cutoff: date) -> dict[str, object]:
    """Describe discovery coverage without trusting any alternative Master."""
    status, _selected, count = resolve_exact_cutoff_master(root, pattern, cutoff)
    report: dict[str, object] = {
        "status": "INVESTMENT_MASTER_DISCOVERY_INSPECTED",
        "cutoff": cutoff.isoformat(),
        "strict_discovery_status": status,
        "strict_matching_count": count,
        "root_configured": bool(root),
        "root_exists": False,
        "configured_pattern": pattern,
        "matching_glob_file_count": 0,
        "alternate_cutoff_candidates": [],
        "scanned_spreadsheet_count": 0,
        "scan_truncated": False,
        "recommendation": "REVIEW_CONFIGURED_ROOT_AND_PATTERN",
        "financially_certified": False,
    }
    if not root:
        report["recommendation"] = "CONFIGURE_PORTFOLIO_ROOT"
        return report
    resolved = expand_environment_path(root)
    base = Path(resolved) if resolved else None
    if base is None or not base.is_dir():
        report["recommendation"] = "MOUNT_OR_CORRECT_PORTFOLIO_ROOT"
        return report
    report["root_exists"] = True
    try:
        relative = pattern.format(
            year=cutoff.year, month=f"{cutoff.month:02d}", day=f"{cutoff.day:02d}"
        ).replace("\\", "/")
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            report["recommendation"] = "CORRECT_INVALID_MASTER_PATTERN"
            return report
        report["matching_glob_file_count"] = sum(
            Path(path).is_file() and Path(path).suffix.lower() in _EXTENSION_SET
            for path in glob(str(base / relative_path))
        )
    except (OSError, ValueError, KeyError):
        report["recommendation"] = "CORRECT_INVALID_MASTER_PATTERN"
        return report

    # Prefer the configured year tree, keeping OneDrive traversals bounded.
    candidates_to_scan = (
        base / "Inversiones" / str(cutoff.year),
        base / str(cutoff.year),
    )
    search_root = next((p for p in candidates_to_scan if p.is_dir()), base)
    found: list[str] = []
    seen = 0
    truncated = False
    try:
        for path in search_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in _EXTENSION_SET:
                continue
            seen += 1
            if seen > _MAX_SCANNED_FILES:
                truncated = True
                break
            if _contains_exact_cutoff(path.stem, cutoff):
                if len(found) < _MAX_MATCHES_REPORTED:
                    found.append(path.relative_to(base).as_posix())
    except (OSError, PermissionError):
        report["recommendation"] = "CHECK_MASTER_DIRECTORY_ACCESS"
        return report
    report["scanned_spreadsheet_count"] = min(seen, _MAX_SCANNED_FILES)
    report["alternate_cutoff_candidates"] = sorted(found)
    report["scan_truncated"] = truncated
    if status == "EXACT_CUTOFF_MASTER_FOUND_NOT_CERTIFIED":
        report["recommendation"] = "EXECUTE_EXISTING_INVESTMENT_AUDIT"
    elif status == "AMBIGUOUS_MASTER_FILES":
        report["recommendation"] = "RESOLVE_MULTIPLE_STRICT_CUTOFF_MASTERS"
    elif found:
        report["recommendation"] = "VERIFY_CANDIDATE_AND_CORRECT_PATTERN_WITH_APPROVAL"
    elif truncated:
        report["recommendation"] = "SEARCH_INSTITUTIONAL_MASTER_ROOT_MORE_NARROWLY"
    else:
        report["recommendation"] = "VERIFY_REAL_MASTER_EXISTS_FOR_REQUESTED_CUTOFF"
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Diagnóstico sin escrituras del Maestro de inversiones"
    )
    parser.add_argument("--cutoff", default="2026-09-30")
    args = parser.parse_args(argv)
    try:
        cutoff = date.fromisoformat(args.cutoff)
    except ValueError:
        parser.error("--cutoff requiere YYYY-MM-DD")
    folder = EnvironmentLoader().load_source_config().folder_watch
    report = inspect_master_paths(
        root=folder.portfolio_root,
        pattern=folder.portfolio_master_pattern,
        cutoff=cutoff,
    )
    report["folder_watch_enabled"] = folder.enabled
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
