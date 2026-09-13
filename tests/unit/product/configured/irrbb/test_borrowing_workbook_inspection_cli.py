from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import openpyxl

from aip.product.configured.irrbb.borrowing_workbook_inspection_cli import (
    BORROWING_INSPECTION_REPORT_VERSION,
    DISCOVERY_REPORT_TYPE,
    HEADER_REPORT_TYPE,
    run,
)
from aip.product.configured.irrbb.physical_source_registry import BORROWING_WORKBOOK_SOURCE


def _workbook_path(tmp_path: Path) -> Path:
    return tmp_path / BORROWING_WORKBOOK_SOURCE.logical_name


def _save_workbook(path: Path) -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Obligaciones"
    sheet.append(["Operacion", "Saldo", None, "operacion"])
    sheet.append(["OP-001-CONTRACT-DATA", 125000.0, None, "X"])
    workbook.save(path)
    workbook.close()


def _run(argv: list[str]) -> tuple[int, StringIO, StringIO]:
    stdout = StringIO()
    stderr = StringIO()
    exit_code = run(argv, stdout=stdout, stderr=stderr)
    return exit_code, stdout, stderr


def test_discovery_mode_emits_safe_schema_evidence_without_contract_rows(tmp_path: Path) -> None:
    path = _workbook_path(tmp_path)
    _save_workbook(path)

    exit_code, stdout, stderr = _run(["--path", str(path)])
    report = json.loads(stdout.getvalue())
    serialized = stdout.getvalue()

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert report["report_type"] == DISCOVERY_REPORT_TYPE
    assert report["report_version"] == BORROWING_INSPECTION_REPORT_VERSION
    assert report["source_id"] == BORROWING_WORKBOOK_SOURCE.source_id
    assert report["source_file_name"] == BORROWING_WORKBOOK_SOURCE.logical_name
    assert report["sheets"][0]["sheet_name"] == "Obligaciones"
    assert str(tmp_path) not in serialized
    assert "C:\\Users\\" not in serialized
    assert "OP-001-CONTRACT-DATA" not in serialized
    assert "certification" not in serialized.casefold()
    assert '"status"' not in serialized.casefold()


def test_header_mode_emits_only_declared_header_evidence(tmp_path: Path) -> None:
    path = _workbook_path(tmp_path)
    _save_workbook(path)

    exit_code, stdout, stderr = _run(
        [
            "--path",
            str(path),
            "--sheet",
            "Obligaciones",
            "--header-row",
            "1",
        ]
    )
    report = json.loads(stdout.getvalue())
    serialized = stdout.getvalue()

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert report["report_type"] == HEADER_REPORT_TYPE
    assert report["sheet_name"] == "Obligaciones"
    assert report["header_row"] == 1
    assert [cell["label"] for cell in report["cells"]] == [
        "Operacion",
        "Saldo",
        None,
        "operacion",
    ]
    assert report["blank_column_indexes"] == [3]
    assert report["duplicate_labels"] == ["Operacion"]
    assert "OP-001-CONTRACT-DATA" not in serialized
    assert str(tmp_path) not in serialized


def test_sheet_and_header_row_must_be_supplied_together_without_running_inspection(
    tmp_path: Path,
) -> None:
    path = _workbook_path(tmp_path)
    _save_workbook(path)

    sheet_only_code, sheet_only_stdout, sheet_only_stderr = _run(
        ["--path", str(path), "--sheet", "Obligaciones"]
    )
    row_only_code, row_only_stdout, row_only_stderr = _run(
        ["--path", str(path), "--header-row", "1"]
    )

    assert sheet_only_code == 2
    assert row_only_code == 2
    assert sheet_only_stdout.getvalue() == ""
    assert row_only_stdout.getvalue() == ""
    assert "--sheet and --header-row must be supplied together" in sheet_only_stderr.getvalue()
    assert "--sheet and --header-row must be supplied together" in row_only_stderr.getvalue()
    assert str(tmp_path) not in sheet_only_stderr.getvalue()
    assert str(tmp_path) not in row_only_stderr.getvalue()


def test_missing_path_argument_returns_usage_error_without_process_exit() -> None:
    exit_code, stdout, stderr = _run([])

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert "usage error" in stderr.getvalue()
    assert "--path" in stderr.getvalue()


def test_missing_workbook_error_exposes_basename_not_parent_path(tmp_path: Path) -> None:
    path = _workbook_path(tmp_path)

    exit_code, stdout, stderr = _run(["--path", str(path)])

    assert exit_code == 1
    assert stdout.getvalue() == ""
    assert BORROWING_WORKBOOK_SOURCE.logical_name in stderr.getvalue()
    assert str(tmp_path) not in stderr.getvalue()


def test_unknown_sheet_failure_does_not_emit_partial_json(tmp_path: Path) -> None:
    path = _workbook_path(tmp_path)
    _save_workbook(path)

    exit_code, stdout, stderr = _run(
        [
            "--path",
            str(path),
            "--sheet",
            "No existe",
            "--header-row",
            "1",
        ]
    )

    assert exit_code == 1
    assert stdout.getvalue() == ""
    assert "worksheet was not found" in stderr.getvalue()
    assert str(tmp_path) not in stderr.getvalue()


def test_non_integer_header_row_is_a_usage_error() -> None:
    exit_code, stdout, stderr = _run(
        [
            "--path",
            "placeholder.xlsx",
            "--sheet",
            "Obligaciones",
            "--header-row",
            "not-an-integer",
        ]
    )

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert "usage error" in stderr.getvalue()
    assert "invalid int value" in stderr.getvalue()
