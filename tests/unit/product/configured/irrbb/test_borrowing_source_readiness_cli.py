from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

from aip.product.configured.irrbb.borrowing_inspection_report_contract import (
    BORROWING_INSPECTION_REPORT_VERSION,
    DISCOVERY_REPORT_TYPE,
    HEADER_REPORT_TYPE,
)
from aip.product.configured.irrbb.borrowing_source_readiness_cli import run
from aip.product.configured.irrbb.physical_source_registry import BORROWING_WORKBOOK_SOURCE

_FILE_SHA256 = "a" * 64
_SOURCE_REFERENCE = (
    f"{BORROWING_WORKBOOK_SOURCE.source_id}:"
    f"{BORROWING_WORKBOOK_SOURCE.logical_name}#sha256={_FILE_SHA256}"
)
_LABELS = (
    "No. Operación",
    "Saldo",
    "Fecha Apertura",
    "Fecha Vencimiento",
    "Tasa Interes",
    "SPREAD",
    "Tasa Piso",
    "Fecha Pago",
)


def _discovery_report() -> dict[str, object]:
    return {
        "report_type": DISCOVERY_REPORT_TYPE,
        "report_version": BORROWING_INSPECTION_REPORT_VERSION,
        "source_id": BORROWING_WORKBOOK_SOURCE.source_id,
        "source_reference": _SOURCE_REFERENCE,
        "source_file_name": BORROWING_WORKBOOK_SOURCE.logical_name,
        "file_sha256": _FILE_SHA256,
        "sheets": [
            {
                "sheet_name": "JUN-24",
                "visibility": "visible",
                "worksheet_max_row": 20,
                "worksheet_max_column": len(_LABELS),
                "observed_non_empty_row_count": 1,
                "observed_non_empty_cell_count": len(_LABELS),
                "observed_last_non_empty_row": 7,
                "observed_last_non_empty_column": len(_LABELS),
            }
        ],
    }


def _header_report() -> dict[str, object]:
    return {
        "report_type": HEADER_REPORT_TYPE,
        "report_version": BORROWING_INSPECTION_REPORT_VERSION,
        "source_id": BORROWING_WORKBOOK_SOURCE.source_id,
        "source_reference": _SOURCE_REFERENCE,
        "source_file_name": BORROWING_WORKBOOK_SOURCE.logical_name,
        "file_sha256": _FILE_SHA256,
        "sheet_name": "JUN-24",
        "header_row": 7,
        "cells": [
            {
                "column_index": index,
                "column_letter": chr(ord("A") + index - 1),
                "label": label,
            }
            for index, label in enumerate(_LABELS, start=1)
        ],
        "blank_column_indexes": [],
        "duplicate_labels": [],
    }


def _write_evidence(tmp_path: Path) -> tuple[Path, Path]:
    discovery_path = tmp_path / "borrowing-discovery.json"
    header_path = tmp_path / "borrowing-header.json"
    discovery_path.write_text(
        json.dumps(_discovery_report(), ensure_ascii=False),
        encoding="utf-8",
    )
    header_path.write_text(
        json.dumps(_header_report(), ensure_ascii=False),
        encoding="utf-8",
    )
    return discovery_path, header_path


def test_valid_evidence_renders_fail_closed_metadata_only_report(tmp_path: Path) -> None:
    discovery_path, header_path = _write_evidence(tmp_path)
    stdout = StringIO()
    stderr = StringIO()

    status = run(
        [
            "--discovery-json",
            str(discovery_path),
            "--header-json",
            str(header_path),
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert status == 0
    assert stderr.getvalue() == ""
    report = json.loads(stdout.getvalue())
    assert report["report_type"] == "IRRBB_BORROWING_SOURCE_READINESS"
    assert report["certification_status"] == "BLOCKED"
    assert "BRW_CURRENCY" in report["blocking_requirement_ids"]
    assert "BRW_RATE_TYPE" in report["blocking_requirement_ids"]
    assert "BRW_NEXT_RESET_DATE" in report["blocking_requirement_ids"]
    assert "BRW_CUTOFF" in report["blocking_requirement_ids"]
    assert "BRW_NEXT_PAYMENT_DATE" in report["not_assessed_requirement_ids"]
    assert report["unresolved_candidate_labels"] == ["Fecha Pago"]
    assert str(tmp_path) not in stdout.getvalue()
    assert '"rows"' not in stdout.getvalue()


def test_require_ready_returns_three_after_rendering_blocked_report(tmp_path: Path) -> None:
    discovery_path, header_path = _write_evidence(tmp_path)
    stdout = StringIO()
    stderr = StringIO()

    status = run(
        [
            "--discovery-json",
            str(discovery_path),
            "--header-json",
            str(header_path),
            "--require-ready",
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert status == 3
    assert json.loads(stdout.getvalue())["certification_status"] == "BLOCKED"
    assert stderr.getvalue() == ""


def test_swapped_report_roles_fail_closed(tmp_path: Path) -> None:
    discovery_path, header_path = _write_evidence(tmp_path)
    stdout = StringIO()
    stderr = StringIO()

    status = run(
        [
            "--discovery-json",
            str(header_path),
            "--header-json",
            str(discovery_path),
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert status == 1
    assert stdout.getvalue() == ""
    assert "--discovery-json must contain a borrowing discovery report" in stderr.getvalue()


def test_different_snapshot_hashes_are_rejected(tmp_path: Path) -> None:
    discovery_path, header_path = _write_evidence(tmp_path)
    header = _header_report()
    other_sha = "b" * 64
    header["file_sha256"] = other_sha
    header["source_reference"] = (
        f"{BORROWING_WORKBOOK_SOURCE.source_id}:"
        f"{BORROWING_WORKBOOK_SOURCE.logical_name}#sha256={other_sha}"
    )
    header_path.write_text(json.dumps(header, ensure_ascii=False), encoding="utf-8")
    stdout = StringIO()
    stderr = StringIO()

    status = run(
        [
            "--discovery-json",
            str(discovery_path),
            "--header-json",
            str(header_path),
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert status == 1
    assert stdout.getvalue() == ""
    assert "different snapshots" in stderr.getvalue()


def test_file_access_failure_does_not_echo_local_path(tmp_path: Path) -> None:
    missing_path = tmp_path / "private" / "missing.json"
    stdout = StringIO()
    stderr = StringIO()

    status = run(
        [
            "--discovery-json",
            str(missing_path),
            "--header-json",
            str(missing_path),
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert status == 1
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "IRRBB borrowing readiness failed: evidence file access error\n"
    assert str(tmp_path) not in stderr.getvalue()
