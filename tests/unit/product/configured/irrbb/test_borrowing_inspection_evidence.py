from __future__ import annotations

import copy
import json

import pytest

from aip.product.configured.irrbb.borrowing_inspection_evidence import (
    BorrowingInspectionEvidenceValidator,
    ValidatedBorrowingDiscoveryEvidence,
    ValidatedBorrowingHeaderEvidence,
)
from aip.product.configured.irrbb.borrowing_workbook_inspection_cli import (
    borrowing_discovery_report,
    borrowing_header_report,
)
from aip.product.configured.irrbb.borrowing_workbook_inspector import (
    BorrowingWorkbookDiscovery,
    BorrowingWorkbookHeaderCellEvidence,
    BorrowingWorkbookHeaderInspection,
    BorrowingWorkbookSheetTopology,
)
from aip.product.configured.irrbb.physical_source_registry import BORROWING_WORKBOOK_SOURCE

_FILE_SHA256 = "a" * 64
_SOURCE_REFERENCE = (
    f"{BORROWING_WORKBOOK_SOURCE.source_id}:"
    f"{BORROWING_WORKBOOK_SOURCE.logical_name}#sha256={_FILE_SHA256}"
)


def _inspection_objects() -> tuple[BorrowingWorkbookDiscovery, BorrowingWorkbookHeaderInspection]:
    discovery = BorrowingWorkbookDiscovery(
        source_id=BORROWING_WORKBOOK_SOURCE.source_id,
        source_reference=_SOURCE_REFERENCE,
        source_file_name=BORROWING_WORKBOOK_SOURCE.logical_name,
        file_sha256=_FILE_SHA256,
        sheets=(
            BorrowingWorkbookSheetTopology(
                sheet_name="Obligaciones",
                visibility="visible",
                worksheet_max_row=20,
                worksheet_max_column=4,
                observed_non_empty_row_count=16,
                observed_non_empty_cell_count=55,
                observed_last_non_empty_row=20,
                observed_last_non_empty_column=4,
            ),
            BorrowingWorkbookSheetTopology(
                sheet_name="Notas",
                visibility="hidden",
                worksheet_max_row=1,
                worksheet_max_column=1,
                observed_non_empty_row_count=0,
                observed_non_empty_cell_count=0,
                observed_last_non_empty_row=0,
                observed_last_non_empty_column=0,
            ),
        ),
    )
    header = BorrowingWorkbookHeaderInspection(
        discovery=discovery,
        sheet_name="Obligaciones",
        header_row=5,
        cells=(
            BorrowingWorkbookHeaderCellEvidence(1, "A", "Entidad"),
            BorrowingWorkbookHeaderCellEvidence(2, "B", "Tasa"),
            BorrowingWorkbookHeaderCellEvidence(3, "C", None),
            BorrowingWorkbookHeaderCellEvidence(4, "D", " tasa "),
        ),
        blank_column_indexes=(3,),
        duplicate_labels=("Tasa",),
    )
    return discovery, header


def _reports() -> tuple[dict[str, object], dict[str, object]]:
    discovery, header = _inspection_objects()
    return borrowing_discovery_report(discovery), borrowing_header_report(header)


def test_phase18_reports_validate_and_bind_to_one_snapshot() -> None:
    discovery_report, header_report = _reports()
    validator = BorrowingInspectionEvidenceValidator()

    discovery = validator.validate_discovery(discovery_report)
    header = validator.validate_header(header_report)
    bundle = validator.bind(discovery, header)

    assert isinstance(discovery, ValidatedBorrowingDiscoveryEvidence)
    assert isinstance(header, ValidatedBorrowingHeaderEvidence)
    assert bundle.discovery.file_sha256 == _FILE_SHA256
    assert bundle.header.sheet_name == "Obligaciones"
    assert bundle.header.blank_column_indexes == (3,)
    assert bundle.header.duplicate_labels == ("Tasa",)

    parsed = validator.parse_json_document(json.dumps(header_report, ensure_ascii=False))
    assert parsed == header


def test_wrong_governed_identity_or_reference_is_rejected() -> None:
    discovery_report, _ = _reports()
    validator = BorrowingInspectionEvidenceValidator()

    wrong_source = copy.deepcopy(discovery_report)
    wrong_source["source_id"] = "other.source"
    with pytest.raises(ValueError, match="source_id"):
        validator.validate_discovery(wrong_source)

    wrong_reference = copy.deepcopy(discovery_report)
    wrong_reference["source_reference"] = "tampered"
    with pytest.raises(ValueError, match="source_reference"):
        validator.validate_discovery(wrong_reference)


def test_unknown_fields_and_wrong_version_fail_closed() -> None:
    discovery_report, header_report = _reports()
    validator = BorrowingInspectionEvidenceValidator()

    with_extra_rows = copy.deepcopy(header_report)
    with_extra_rows["rows"] = [{"principal": 1}]
    with pytest.raises(ValueError, match="shape mismatch"):
        validator.validate_header(with_extra_rows)

    wrong_version = copy.deepcopy(discovery_report)
    wrong_version["report_version"] = "2099.01.01"
    with pytest.raises(ValueError, match="report_version"):
        validator.validate_discovery(wrong_version)


def test_sha256_must_be_lowercase_hex_and_reference_must_match_it() -> None:
    discovery_report, _ = _reports()
    validator = BorrowingInspectionEvidenceValidator()

    malformed = copy.deepcopy(discovery_report)
    malformed["file_sha256"] = "A" * 64
    malformed["source_reference"] = (
        f"{BORROWING_WORKBOOK_SOURCE.source_id}:"
        f"{BORROWING_WORKBOOK_SOURCE.logical_name}#sha256={'A' * 64}"
    )
    with pytest.raises(ValueError, match="file_sha256"):
        validator.validate_discovery(malformed)


def test_header_column_coordinates_are_recomputed() -> None:
    _, header_report = _reports()
    validator = BorrowingInspectionEvidenceValidator()

    wrong_index = copy.deepcopy(header_report)
    wrong_index["cells"][1]["column_index"] = 3  # type: ignore[index]
    with pytest.raises(ValueError, match="contiguous"):
        validator.validate_header(wrong_index)

    wrong_letter = copy.deepcopy(header_report)
    wrong_letter["cells"][1]["column_letter"] = "Z"  # type: ignore[index]
    with pytest.raises(ValueError, match="column letter"):
        validator.validate_header(wrong_letter)


def test_blank_and_duplicate_diagnostics_must_be_recomputable() -> None:
    _, header_report = _reports()
    validator = BorrowingInspectionEvidenceValidator()

    wrong_blanks = copy.deepcopy(header_report)
    wrong_blanks["blank_column_indexes"] = []
    with pytest.raises(ValueError, match="blank-column"):
        validator.validate_header(wrong_blanks)

    wrong_duplicates = copy.deepcopy(header_report)
    wrong_duplicates["duplicate_labels"] = []
    with pytest.raises(ValueError, match="duplicate-label"):
        validator.validate_header(wrong_duplicates)


def test_discovery_topology_inconsistency_is_rejected() -> None:
    discovery_report, _ = _reports()
    validator = BorrowingInspectionEvidenceValidator()

    impossible = copy.deepcopy(discovery_report)
    impossible["sheets"][0]["observed_last_non_empty_row"] = 21  # type: ignore[index]
    with pytest.raises(ValueError, match="last row exceeds"):
        validator.validate_discovery(impossible)


def test_binding_rejects_different_snapshot_or_unobserved_header() -> None:
    discovery_report, header_report = _reports()
    validator = BorrowingInspectionEvidenceValidator()
    discovery = validator.validate_discovery(discovery_report)

    other_snapshot_report = copy.deepcopy(header_report)
    other_sha = "b" * 64
    other_snapshot_report["file_sha256"] = other_sha
    other_snapshot_report["source_reference"] = (
        f"{BORROWING_WORKBOOK_SOURCE.source_id}:"
        f"{BORROWING_WORKBOOK_SOURCE.logical_name}#sha256={other_sha}"
    )
    other_snapshot = validator.validate_header(other_snapshot_report)
    with pytest.raises(ValueError, match="different snapshots"):
        validator.bind(discovery, other_snapshot)

    unknown_sheet_report = copy.deepcopy(header_report)
    unknown_sheet_report["sheet_name"] = "Otra Hoja"
    unknown_sheet = validator.validate_header(unknown_sheet_report)
    with pytest.raises(ValueError, match="absent from discovery"):
        validator.bind(discovery, unknown_sheet)

    out_of_bounds_report = copy.deepcopy(header_report)
    out_of_bounds_report["header_row"] = 21
    out_of_bounds = validator.validate_header(out_of_bounds_report)
    with pytest.raises(ValueError, match="exceeds discovered"):
        validator.bind(discovery, out_of_bounds)


def test_json_parser_rejects_non_object_and_unknown_report_type() -> None:
    validator = BorrowingInspectionEvidenceValidator()

    with pytest.raises(ValueError, match="root must be an object"):
        validator.parse_json_document("[]")
    with pytest.raises(ValueError, match="not valid JSON"):
        validator.parse_json_document("{")
    with pytest.raises(ValueError, match="unsupported"):
        validator.parse_json_document('{"report_type": "OTHER"}')
