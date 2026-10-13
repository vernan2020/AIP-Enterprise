"""Conservative migration: preview only, no loss of certified data."""

from __future__ import annotations

import duckdb
import pytest

from scripts.qa.recover_macro_history import inventory, recover


def _db(path, *, amount: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(path)) as connection:
        connection.execute(
            "CREATE TABLE economic_history_observations ("
            "indicator_code VARCHAR, observation_date DATE, value VARCHAR, "
            "source VARCHAR, source_series_code VARCHAR, unit VARCHAR, "
            "frequency VARCHAR, updated_at TIMESTAMP)"
        )
        for n in range(amount):
            connection.execute(
                "INSERT INTO economic_history_observations VALUES (?, "
                "DATE '2026-09-01', '3.00', 'BCCR', NULL, '%', 'MONTHLY', now())",
                [f"TPM_{n}"],
            )


def test_dry_run_does_not_modify_either_database(tmp_path) -> None:
    source = tmp_path / "certified" / "database" / "aip.duckdb"
    target = tmp_path / "preview" / "database" / "aip.duckdb"
    _db(source, amount=2)
    _db(target, amount=0)
    before = target.read_bytes()
    lines = recover(source, target)
    assert "SOLO DIAGNÓSTICO" in lines[-1]
    assert target.read_bytes() == before
    assert inventory(source)["economic_history_observations"] == 2


def test_recovery_preserves_original_and_backs_up_preview(tmp_path) -> None:
    source = tmp_path / "certified" / "database" / "aip.duckdb"
    target = tmp_path / "preview" / "database" / "aip.duckdb"
    _db(source, amount=2)
    _db(target, amount=0)
    result = recover(source, target, apply=True)
    assert any("restauradas 2 filas" in message for message in result)
    assert inventory(source)["economic_history_observations"] == 2
    assert inventory(target)["economic_history_observations"] == 2
    assert len(list((target.parent / "backups").glob("*/aip.duckdb"))) == 1
    second = recover(source, target, apply=True)
    assert "Nada por restaurar" in second[-1]


def test_refuses_same_source_and_target(tmp_path) -> None:
    path = tmp_path / "database" / "aip.duckdb"
    _db(path, amount=1)
    with pytest.raises(ValueError, match="misma base"):
        recover(path, path, apply=True)


def test_partial_scenario_history_is_not_mixed_with_certified_history(tmp_path) -> None:
    source = tmp_path / "certified" / "database" / "aip.duckdb"
    target = tmp_path / "preview" / "database" / "aip.duckdb"
    _db(source, amount=0)
    _db(target, amount=0)
    with duckdb.connect(str(source)) as con:
        con.execute(
            "CREATE TABLE institutional_macro_scenarios " "(scenario_id VARCHAR, version INTEGER)"
        )
        con.execute("INSERT INTO institutional_macro_scenarios VALUES ('C', 1)")
    with duckdb.connect(str(target)) as con:
        con.execute("CREATE TABLE institutional_macro_scenario_events " "(event_id VARCHAR)")
        con.execute("INSERT INTO institutional_macro_scenario_events VALUES ('P')")
    with pytest.raises(ValueError, match="conciliación"):
        recover(source, target, apply=True)
    assert not (target.parent / "backups").exists()
    with duckdb.connect(str(source), read_only=True) as con:
        assert con.execute("SELECT COUNT(*) FROM institutional_macro_scenarios").fetchone()[0] == 1


def test_incompatible_table_schema_does_not_copy_partial_data(tmp_path) -> None:
    source = tmp_path / "certified" / "database" / "aip.duckdb"
    target = tmp_path / "preview" / "database" / "aip.duckdb"
    _db(source, amount=2)
    _db(target, amount=0)
    with duckdb.connect(str(source)) as con:
        con.execute("ALTER TABLE economic_history_observations ADD COLUMN extra VARCHAR")
    with pytest.raises(ValueError, match="Esquema incompatible"):
        recover(source, target, apply=True)
    assert inventory(source)["economic_history_observations"] == 2
    assert inventory(target)["economic_history_observations"] == 0
    assert len(list((target.parent / "backups").glob("*/aip.duckdb"))) == 1
