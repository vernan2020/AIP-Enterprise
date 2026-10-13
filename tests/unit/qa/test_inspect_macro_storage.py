"""Regression checks for non-destructive AIP macro storage diagnostics."""

from __future__ import annotations

from pathlib import Path

import duckdb

from scripts.qa.inspect_macro_storage import inspect_database


def test_missing_preview_does_not_create_an_empty_database(tmp_path: Path) -> None:
    missing = tmp_path / "preview" / "database" / "aip.duckdb"
    state = inspect_database(missing)
    assert not state.exists
    assert state.observations is None
    assert not missing.exists()


def test_inspection_reads_existing_macro_history_and_scenarios(tmp_path: Path) -> None:
    path = tmp_path / "database" / "aip.duckdb"
    path.parent.mkdir(parents=True)
    connection = duckdb.connect(str(path))
    try:
        connection.execute(
            "CREATE TABLE economic_history_observations (indicator_code VARCHAR)"
        )
        connection.execute(
            "INSERT INTO economic_history_observations VALUES ('TPM'), ('TBP')"
        )
        connection.execute(
            "CREATE TABLE institutional_macro_scenarios (status VARCHAR)"
        )
        connection.execute(
            "INSERT INTO institutional_macro_scenarios VALUES "
            "('APPROVED'), ('DRAFT'), ('approved')"
        )
    finally:
        connection.close()
    state = inspect_database(path)
    assert state.exists
    assert state.observations == 2
    assert state.scenarios == 3
    assert state.approved == 2
    assert state.error is None


def test_inspection_handles_an_unreadable_file_without_modifying_it(
    tmp_path: Path,
) -> None:
    path = tmp_path / "aip.duckdb"
    path.write_bytes(b"NOT A DUCKDB")
    original = path.read_bytes()
    state = inspect_database(path)
    assert state.exists
    assert state.error is not None
    assert path.read_bytes() == original
