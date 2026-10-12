from __future__ import annotations

import hashlib
import io
import json
from dataclasses import replace
from datetime import date
from pathlib import Path

from aip.product.configured.readers.institutional_portfolio_master_reader import (
    InstitutionalPortfolioMasterReadResult,
)
from aip.product.configured.services.institutional_scenario_readiness_cli import (
    inspect,
    run,
    summarize_native_master,
)

CUTOFF = date(2026, 10, 2)


def _reader_result() -> InstitutionalPortfolioMasterReadResult:
    return InstitutionalPortfolioMasterReadResult(
        source_file="master-02-10-2026.xlsx",
        valuation_date=CUTOFF,
        sheet_selected="Cartera",
        normalized_positions=[
            {
                "source_row": 2,
                "contract_number": "CONTRACT-A",
                "isin": "TEST-A",
                "source_currency": "CRC",
                "market_value": 600,
                "market_value_crc": 600,
            }
        ],
        warnings=(),
        rejected_row_count=0,
        source_status="HEALTHY",
        detected_column_mapping={
            name: name
            for name in (
                "market_value_crc",
                "market_value",
                "currency",
                "issuer",
                "isin",
                "classification",
                "product_code",
                "contract_number",
            )
        },
    )


def test_structural_readiness_is_not_scenario_certification() -> None:
    report = summarize_native_master(_reader_result())
    assert report["source_structural_ready"] is True
    assert report["scenario_ready"] is False
    assert report["production_activation_authorized"] is False
    assert "APPROVED_REGULATORY_EXPOSURES" in report["pending_independent_evidence"]
    assert "CONTRACT-A" not in json.dumps(report)
    assert "600" not in json.dumps(report)


def test_duplicate_lots_missing_columns_fx_and_crc_mismatch_are_reported() -> None:
    first = _reader_result()
    rows = list(first.normalized_positions)
    rows.append(
        {
            **rows[0],
            "source_row": 3,
            "source_currency": "USD",
            "market_value": 10,
            "market_value_crc": 4500,
        }
    )
    result = replace(
        first,
        normalized_positions=rows,
        detected_column_mapping={
            key: value
            for key, value in first.detected_column_mapping.items()
            if key != "contract_number"
        },
    )
    report = summarize_native_master(result)
    assert report["source_structural_ready"] is False
    assert "NATIVE_COLUMNS_MISSING" in report["blocking_codes"]
    assert "CONTRACT_ISIN_IDENTITY_INVALID" in report["blocking_codes"]
    assert "APPROVED_HISTORICAL_FX_CONVERSION" in report["pending_independent_evidence"]

    wrong = replace(first, normalized_positions=[{**rows[0], "market_value_crc": 550}])
    assert "CRC_NATIVE_VALUATION_MISMATCH" in summarize_native_master(wrong)["blocking_codes"]


class _Reader:
    def __init__(self, result: InstitutionalPortfolioMasterReadResult) -> None:
        self.result = result

    def read(self, path: Path, *, valuation_date_override: date):
        assert valuation_date_override == CUTOFF
        return self.result


def test_cli_is_read_only_and_does_not_print_sensitive_values(tmp_path: Path) -> None:
    path = tmp_path / "02-10-2026.xlsx"
    path.write_bytes(b"synthetic workbook bytes")
    stdout, stderr = io.StringIO(), io.StringIO()
    code = run(
        ["--path", str(path), "--cutoff", CUTOFF.isoformat(), "--require-source-ready"],
        stdout=stdout,
        stderr=stderr,
        reader=_Reader(_reader_result()),
    )
    report = json.loads(stdout.getvalue())
    assert code == 0
    assert stderr.getvalue() == ""
    assert report["master_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert report["source_file_name"] == path.name
    assert "CONTRACT-A" not in stdout.getvalue()

    degraded = replace(_reader_result(), rejected_row_count=1)
    stdout = io.StringIO()
    code = run(
        ["--path", str(path), "--cutoff", CUTOFF.isoformat(), "--require-source-ready"],
        stdout=stdout,
        stderr=io.StringIO(),
        reader=_Reader(degraded),
    )
    assert code == 3
    assert "MASTER_READER_DEGRADED" in stdout.getvalue()


def test_bad_cutoff_filename_and_missing_file_are_rejected_without_path_leak(
    tmp_path: Path,
) -> None:
    file = tmp_path / "02-10-2026.xlsx"
    file.write_bytes(b"test")
    stdout, stderr = io.StringIO(), io.StringIO()
    assert run(
        ["--path", str(file), "--cutoff", "2026-10-01"],
        stdout=stdout,
        stderr=stderr,
        reader=_Reader(_reader_result()),
    ) == 2
    assert stdout.getvalue() == ""
    assert str(tmp_path) not in stderr.getvalue()
    assert "invalid arguments or source evidence" in stderr.getvalue()
    assert run([], stdout=io.StringIO(), stderr=io.StringIO()) == 2
    file.unlink()
    assert run(
        ["--path", str(file), "--cutoff", CUTOFF.isoformat()],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    ) == 2


def test_changed_bytes_during_inspection_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "02-10-2026.xlsx"
    path.write_bytes(b"original")

    class _MutatingReader(_Reader):
        def read(self, file_path: Path, *, valuation_date_override: date):
            file_path.write_bytes(b"changed")
            return super().read(file_path, valuation_date_override=valuation_date_override)

    stdout, stderr = io.StringIO(), io.StringIO()
    assert run(
        ["--path", str(path), "--cutoff", CUTOFF.isoformat()],
        stdout=stdout,
        stderr=stderr,
        reader=_MutatingReader(_reader_result()),
    ) == 2
    assert stdout.getvalue() == ""
    assert "failed" in stderr.getvalue()
