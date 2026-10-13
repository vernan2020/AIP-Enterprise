"""Safe, read-only source audit contracts; never expose configured secrets."""

from __future__ import annotations

from scripts.qa.audit_configured_sources import audit_source_configuration


def test_source_audit_reports_database_divergence_and_masks_tokens(tmp_path) -> None:
    preview = tmp_path / "preview"
    certified = tmp_path / "certified"
    for path in (preview, certified):
        (path / "database").mkdir(parents=True)
    (preview / "database" / "aip.duckdb").write_bytes(b"x" * 12288)
    (certified / "database" / "aip.duckdb").write_bytes(b"x" * 28000)
    secret = "NEVER-PRINT-THIS-TOKEN"
    output = "\n".join(
        audit_source_configuration(
            preview,
            certified,
            {
                "AIP_BCCR_TOKEN": secret,
                "AIP_BCCR_NAME": "never-print-name",
                "AIP_BCCR_EMAIL": "never-print-email",
                "AIP_SUGEF_FINANCIAL_API_ENABLED": "false",
                "AIP_RUNTIME_LOCAL_CMD": "private-path",
            },
        )
    )
    assert "12,288 bytes" in output
    assert "28,000 bytes" in output
    assert "BCCR token en entorno: PRESENTE" in output
    assert "SUGEF API: DESHABILITADA" in output
    for private in (secret, "never-print-name", "never-print-email", "private-path"):
        assert private not in output


def test_source_audit_marks_absence_without_touching_files(tmp_path) -> None:
    preview = tmp_path / "preview"
    certified = tmp_path / "certified"
    output = "\n".join(audit_source_configuration(preview, certified, {}))
    assert "BCCR token en entorno: NO VISIBLE" in output
    assert "PREVIEW: DuckDB no encontrado" in output
    assert "CERTIFICADA: DuckDB no encontrado" in output
    assert not preview.exists()
    assert not certified.exists()



def test_historical_inventory_is_read_only(tmp_path) -> None:
    import duckdb

    root = tmp_path / "archive"
    candidate = root / "database" / "aip.duckdb"
    candidate.parent.mkdir(parents=True)
    with duckdb.connect(str(candidate)) as con:
        con.execute(
            "CREATE TABLE economic_history_observations "
            "(indicator_code VARCHAR, observation_date DATE)"
        )
        con.execute(
            "INSERT INTO economic_history_observations VALUES "
            "('TPM', DATE '2026-09-30'), ('TBP', DATE '2026-09-30')"
        )
    from scripts.qa.audit_configured_sources import _historical_inventory

    result = _historical_inventory(root)
    assert "economic_history_observations: 2 registros" in result
    assert "institutional_macro_scenarios: tabla ausente" in result
    with duckdb.connect(str(candidate), read_only=True) as con:
        assert con.execute(
            "SELECT count(*) FROM economic_history_observations"
        ).fetchone()[0] == 2
