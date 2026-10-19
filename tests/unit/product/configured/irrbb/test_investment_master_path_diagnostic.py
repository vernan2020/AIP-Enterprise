from __future__ import annotations

from datetime import date

from aip.product.configured.irrbb.investment_master_path_diagnostic import (
    inspect_master_paths,
)

CUTOFF = date(2026, 9, 30)
PATTERN = r"Inversiones\{year}\maestro\{month}\*.xls*"


def _touch(tmp_path, relative):
    file = tmp_path / relative
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(b"header only for name discovery")
    return file


def test_strict_exact_cutoff_found_without_certifying_source(tmp_path):
    _touch(tmp_path, "Inversiones/2026/maestro/09/30-09-2026.xlsx")
    found = inspect_master_paths(root=str(tmp_path), pattern=PATTERN, cutoff=CUTOFF)
    assert found["strict_discovery_status"] == "EXACT_CUTOFF_MASTER_FOUND_NOT_CERTIFIED"
    assert found["strict_matching_count"] == 1
    assert found["root_exists"] is True
    assert found["financially_certified"] is False
    assert found["recommendation"] == "EXECUTE_EXISTING_INVESTMENT_AUDIT"


def test_month_folder_with_name_is_detected_but_never_auto_selected(tmp_path):
    _touch(tmp_path, "Inversiones/2026/maestro/09-SETIEMBRE/30-09-2026.xlsx")
    found = inspect_master_paths(root=str(tmp_path), pattern=PATTERN, cutoff=CUTOFF)
    assert found["strict_discovery_status"] == "EXACT_CUTOFF_MASTER_NOT_FOUND"
    assert found["strict_matching_count"] == 0
    assert found["alternate_cutoff_candidates"] == [
        "Inversiones/2026/maestro/09-SETIEMBRE/30-09-2026.xlsx"
    ]
    assert found["recommendation"] == "VERIFY_CANDIDATE_AND_CORRECT_PATTERN_WITH_APPROVAL"


def test_iso_filename_is_reported_without_being_substituted(tmp_path):
    _touch(tmp_path, "Inversiones/2026/maestro/09/2026-09-30.xlsx")
    found = inspect_master_paths(root=str(tmp_path), pattern=PATTERN, cutoff=CUTOFF)
    assert found["strict_discovery_status"] == "EXACT_CUTOFF_MASTER_NOT_FOUND"
    assert found["alternate_cutoff_candidates"] == ["Inversiones/2026/maestro/09/2026-09-30.xlsx"]


def test_neither_earlier_cutoff_nor_unrelated_spreadsheet_is_used(tmp_path):
    _touch(tmp_path, "Inversiones/2026/maestro/09/29-09-2026.xlsx")
    _touch(tmp_path, "Inversiones/2026/maestro/09/vector.xls")
    result = inspect_master_paths(root=str(tmp_path), pattern=PATTERN, cutoff=CUTOFF)
    assert result["strict_discovery_status"] == "EXACT_CUTOFF_MASTER_NOT_FOUND"
    assert result["alternate_cutoff_candidates"] == []
    assert result["recommendation"] == "VERIFY_REAL_MASTER_EXISTS_FOR_REQUESTED_CUTOFF"


def test_diagnoses_missing_root_and_invalid_pattern(tmp_path):
    missing = inspect_master_paths(root=None, pattern=PATTERN, cutoff=CUTOFF)
    assert missing["recommendation"] == "CONFIGURE_PORTFOLIO_ROOT"
    invalid = inspect_master_paths(root=str(tmp_path), pattern="../*.xlsx", cutoff=CUTOFF)
    assert invalid["recommendation"] == "CORRECT_INVALID_MASTER_PATTERN"
    assert invalid["strict_discovery_status"] == "INVALID_PATTERN"


def test_multiple_strict_candidates_remain_ambiguous(tmp_path):
    _touch(tmp_path, "Inversiones/2026/maestro/09/30-09-2026.xlsx")
    _touch(tmp_path, "Inversiones/2026/maestro/09/30-09-2026.xls")
    report = inspect_master_paths(root=str(tmp_path), pattern=PATTERN, cutoff=CUTOFF)
    assert report["strict_discovery_status"] == "AMBIGUOUS_MASTER_FILES"
    assert report["strict_matching_count"] == 2
    assert report["recommendation"] == "RESOLVE_MULTIPLE_STRICT_CUTOFF_MASTERS"
