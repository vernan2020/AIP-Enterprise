from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from openpyxl.utils import get_column_letter

from aip.product.configured.irrbb.borrowing_inspection_report_contract import (
    BORROWING_INSPECTION_REPORT_VERSION,
    DISCOVERY_REPORT_TYPE,
    HEADER_REPORT_TYPE,
)
from aip.product.configured.irrbb.physical_source_registry import BORROWING_WORKBOOK_SOURCE

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_DISCOVERY_KEYS = frozenset(
    {
        "report_type",
        "report_version",
        "source_id",
        "source_reference",
        "source_file_name",
        "file_sha256",
        "sheets",
    }
)
_HEADER_KEYS = frozenset(
    {
        "report_type",
        "report_version",
        "source_id",
        "source_reference",
        "source_file_name",
        "file_sha256",
        "sheet_name",
        "header_row",
        "cells",
        "blank_column_indexes",
        "duplicate_labels",
    }
)
_SHEET_KEYS = frozenset(
    {
        "sheet_name",
        "visibility",
        "worksheet_max_row",
        "worksheet_max_column",
        "observed_non_empty_row_count",
        "observed_non_empty_cell_count",
        "observed_last_non_empty_row",
        "observed_last_non_empty_column",
    }
)
_CELL_KEYS = frozenset({"column_index", "column_letter", "label"})
_ALLOWED_VISIBILITY = frozenset({"visible", "hidden", "veryHidden"})


@dataclass(frozen=True, slots=True)
class ValidatedBorrowingSheetEvidence:
    """Validated worksheet topology from a Phase 18 discovery report."""

    sheet_name: str
    visibility: str
    worksheet_max_row: int
    worksheet_max_column: int
    observed_non_empty_row_count: int
    observed_non_empty_cell_count: int
    observed_last_non_empty_row: int
    observed_last_non_empty_column: int


@dataclass(frozen=True, slots=True)
class ValidatedBorrowingDiscoveryEvidence:
    """Validated discovery evidence for the governed borrowing workbook."""

    report_version: str
    source_id: str
    source_reference: str
    source_file_name: str
    file_sha256: str
    sheets: tuple[ValidatedBorrowingSheetEvidence, ...]


@dataclass(frozen=True, slots=True)
class ValidatedBorrowingHeaderCellEvidence:
    """Validated exact header-cell evidence transferred from Phase 18."""

    column_index: int
    column_letter: str
    label: str | None


@dataclass(frozen=True, slots=True)
class ValidatedBorrowingHeaderEvidence:
    """Validated declared-header evidence for the governed borrowing workbook."""

    report_version: str
    source_id: str
    source_reference: str
    source_file_name: str
    file_sha256: str
    sheet_name: str
    header_row: int
    cells: tuple[ValidatedBorrowingHeaderCellEvidence, ...]
    blank_column_indexes: tuple[int, ...]
    duplicate_labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BorrowingInspectionEvidenceBundle:
    """Discovery and header evidence proven to refer to the same inspected workbook."""

    discovery: ValidatedBorrowingDiscoveryEvidence
    header: ValidatedBorrowingHeaderEvidence


class BorrowingInspectionEvidenceValidator:
    """Validate transferred Phase 18 JSON without assigning RTILB business meaning."""

    def parse_json_document(
        self,
        document: str,
    ) -> ValidatedBorrowingDiscoveryEvidence | ValidatedBorrowingHeaderEvidence:
        """Parse and validate one complete Phase 18 JSON report."""

        try:
            payload = json.loads(document)
        except json.JSONDecodeError as exc:
            raise ValueError("borrowing inspection evidence is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("borrowing inspection evidence JSON root must be an object")
        return self.validate_report(payload)

    def validate_report(
        self,
        payload: dict[str, Any],
    ) -> ValidatedBorrowingDiscoveryEvidence | ValidatedBorrowingHeaderEvidence:
        """Validate one report and return a typed evidence contract."""

        report_type = self._require_string(payload.get("report_type"), "report_type")
        if report_type == DISCOVERY_REPORT_TYPE:
            return self.validate_discovery(payload)
        if report_type == HEADER_REPORT_TYPE:
            return self.validate_header(payload)
        raise ValueError(f"unsupported borrowing inspection report_type: {report_type}")

    def validate_discovery(
        self,
        payload: dict[str, Any],
    ) -> ValidatedBorrowingDiscoveryEvidence:
        """Validate exact discovery-report shape and governed source identity."""

        self._require_exact_keys(payload, _DISCOVERY_KEYS, "discovery report")
        identity = self._validate_identity(payload, expected_report_type=DISCOVERY_REPORT_TYPE)
        raw_sheets = self._require_list(payload["sheets"], "sheets")
        if not raw_sheets:
            raise ValueError("borrowing discovery evidence must contain at least one worksheet")

        sheets = tuple(
            self._validate_sheet(self._require_dict(item, f"sheets[{index}]"), index=index)
            for index, item in enumerate(raw_sheets)
        )
        names = [sheet.sheet_name for sheet in sheets]
        if len(names) != len(set(names)):
            raise ValueError("borrowing discovery evidence contains duplicate worksheet names")

        return ValidatedBorrowingDiscoveryEvidence(
            report_version=identity[0],
            source_id=identity[1],
            source_reference=identity[2],
            source_file_name=identity[3],
            file_sha256=identity[4],
            sheets=sheets,
        )

    def validate_header(
        self,
        payload: dict[str, Any],
    ) -> ValidatedBorrowingHeaderEvidence:
        """Validate exact header-report shape and recomputable diagnostics."""

        self._require_exact_keys(payload, _HEADER_KEYS, "header report")
        identity = self._validate_identity(payload, expected_report_type=HEADER_REPORT_TYPE)
        sheet_name = self._require_string(payload["sheet_name"], "sheet_name")
        header_row = self._require_int(payload["header_row"], "header_row", minimum=1)
        raw_cells = self._require_list(payload["cells"], "cells")
        if not raw_cells:
            raise ValueError("borrowing header evidence must contain at least one cell")

        cells = tuple(
            self._validate_cell(self._require_dict(item, f"cells[{index}]"), expected_index=index + 1)
            for index, item in enumerate(raw_cells)
        )
        if all(cell.label is None for cell in cells):
            raise ValueError("borrowing header evidence contains no text labels")

        blank_column_indexes = tuple(
            self._require_int(value, f"blank_column_indexes[{index}]", minimum=1)
            for index, value in enumerate(
                self._require_list(payload["blank_column_indexes"], "blank_column_indexes")
            )
        )
        expected_blank_indexes = tuple(cell.column_index for cell in cells if cell.label is None)
        if blank_column_indexes != expected_blank_indexes:
            raise ValueError("borrowing header blank-column diagnostics do not match cell evidence")

        duplicate_labels = tuple(
            self._require_string(value, f"duplicate_labels[{index}]")
            for index, value in enumerate(
                self._require_list(payload["duplicate_labels"], "duplicate_labels")
            )
        )
        expected_duplicate_labels = self._duplicate_labels(cells)
        if duplicate_labels != expected_duplicate_labels:
            raise ValueError("borrowing header duplicate-label diagnostics do not match cell evidence")

        return ValidatedBorrowingHeaderEvidence(
            report_version=identity[0],
            source_id=identity[1],
            source_reference=identity[2],
            source_file_name=identity[3],
            file_sha256=identity[4],
            sheet_name=sheet_name,
            header_row=header_row,
            cells=cells,
            blank_column_indexes=blank_column_indexes,
            duplicate_labels=duplicate_labels,
        )

    def bind(
        self,
        discovery: ValidatedBorrowingDiscoveryEvidence,
        header: ValidatedBorrowingHeaderEvidence,
    ) -> BorrowingInspectionEvidenceBundle:
        """Require discovery and header evidence to describe the same source snapshot."""

        discovery_identity = (
            discovery.report_version,
            discovery.source_id,
            discovery.source_reference,
            discovery.source_file_name,
            discovery.file_sha256,
        )
        header_identity = (
            header.report_version,
            header.source_id,
            header.source_reference,
            header.source_file_name,
            header.file_sha256,
        )
        if discovery_identity != header_identity:
            raise ValueError("borrowing discovery and header evidence refer to different snapshots")

        topology = next(
            (sheet for sheet in discovery.sheets if sheet.sheet_name == header.sheet_name),
            None,
        )
        if topology is None:
            raise ValueError("borrowing header worksheet is absent from discovery evidence")
        if header.header_row > topology.observed_last_non_empty_row:
            raise ValueError("borrowing header row exceeds discovered worksheet topology")
        if len(header.cells) != topology.observed_last_non_empty_column:
            raise ValueError("borrowing header cell span does not match discovered worksheet topology")

        return BorrowingInspectionEvidenceBundle(discovery=discovery, header=header)

    @staticmethod
    def _validate_identity(
        payload: dict[str, Any],
        *,
        expected_report_type: str,
    ) -> tuple[str, str, str, str, str]:
        report_type = BorrowingInspectionEvidenceValidator._require_string(
            payload["report_type"], "report_type"
        )
        if report_type != expected_report_type:
            raise ValueError("borrowing inspection report_type does not match validation contract")

        report_version = BorrowingInspectionEvidenceValidator._require_string(
            payload["report_version"], "report_version"
        )
        if report_version != BORROWING_INSPECTION_REPORT_VERSION:
            raise ValueError("unsupported borrowing inspection report_version")

        source_id = BorrowingInspectionEvidenceValidator._require_string(
            payload["source_id"], "source_id"
        )
        if source_id != BORROWING_WORKBOOK_SOURCE.source_id:
            raise ValueError("borrowing inspection source_id is not the governed physical source")

        source_file_name = BorrowingInspectionEvidenceValidator._require_string(
            payload["source_file_name"], "source_file_name"
        )
        if source_file_name != BORROWING_WORKBOOK_SOURCE.logical_name:
            raise ValueError("borrowing inspection source filename is not the governed physical source")

        file_sha256 = BorrowingInspectionEvidenceValidator._require_string(
            payload["file_sha256"], "file_sha256"
        )
        if _SHA256_PATTERN.fullmatch(file_sha256) is None:
            raise ValueError("borrowing inspection file_sha256 must be 64 lowercase hexadecimal chars")

        source_reference = BorrowingInspectionEvidenceValidator._require_string(
            payload["source_reference"], "source_reference"
        )
        expected_reference = f"{source_id}:{source_file_name}#sha256={file_sha256}"
        if source_reference != expected_reference:
            raise ValueError("borrowing inspection source_reference is inconsistent with source identity")

        return report_version, source_id, source_reference, source_file_name, file_sha256

    @staticmethod
    def _validate_sheet(
        payload: dict[str, Any],
        *,
        index: int,
    ) -> ValidatedBorrowingSheetEvidence:
        context = f"sheets[{index}]"
        BorrowingInspectionEvidenceValidator._require_exact_keys(payload, _SHEET_KEYS, context)
        sheet_name = BorrowingInspectionEvidenceValidator._require_string(
            payload["sheet_name"], f"{context}.sheet_name"
        )
        visibility = BorrowingInspectionEvidenceValidator._require_string(
            payload["visibility"], f"{context}.visibility"
        )
        if visibility not in _ALLOWED_VISIBILITY:
            raise ValueError(f"{context}.visibility is not a supported worksheet state")

        worksheet_max_row = BorrowingInspectionEvidenceValidator._require_int(
            payload["worksheet_max_row"], f"{context}.worksheet_max_row", minimum=0
        )
        worksheet_max_column = BorrowingInspectionEvidenceValidator._require_int(
            payload["worksheet_max_column"], f"{context}.worksheet_max_column", minimum=0
        )
        observed_non_empty_row_count = BorrowingInspectionEvidenceValidator._require_int(
            payload["observed_non_empty_row_count"],
            f"{context}.observed_non_empty_row_count",
            minimum=0,
        )
        observed_non_empty_cell_count = BorrowingInspectionEvidenceValidator._require_int(
            payload["observed_non_empty_cell_count"],
            f"{context}.observed_non_empty_cell_count",
            minimum=0,
        )
        observed_last_non_empty_row = BorrowingInspectionEvidenceValidator._require_int(
            payload["observed_last_non_empty_row"],
            f"{context}.observed_last_non_empty_row",
            minimum=0,
        )
        observed_last_non_empty_column = BorrowingInspectionEvidenceValidator._require_int(
            payload["observed_last_non_empty_column"],
            f"{context}.observed_last_non_empty_column",
            minimum=0,
        )

        if observed_non_empty_row_count > worksheet_max_row:
            raise ValueError(f"{context} observed row count exceeds worksheet maximum")
        if observed_last_non_empty_row > worksheet_max_row:
            raise ValueError(f"{context} observed last row exceeds worksheet maximum")
        if observed_last_non_empty_column > worksheet_max_column:
            raise ValueError(f"{context} observed last column exceeds worksheet maximum")
        if observed_non_empty_cell_count < observed_non_empty_row_count:
            raise ValueError(f"{context} observed cell count is inconsistent with observed rows")
        if observed_non_empty_cell_count > worksheet_max_row * worksheet_max_column:
            raise ValueError(f"{context} observed cell count exceeds worksheet capacity")

        if observed_non_empty_row_count == 0:
            if any(
                (
                    observed_non_empty_cell_count,
                    observed_last_non_empty_row,
                    observed_last_non_empty_column,
                )
            ):
                raise ValueError(f"{context} empty topology contains non-empty observations")
        elif (
            observed_non_empty_cell_count == 0
            or observed_last_non_empty_row == 0
            or observed_last_non_empty_column == 0
        ):
            raise ValueError(f"{context} non-empty topology lacks observed bounds")

        return ValidatedBorrowingSheetEvidence(
            sheet_name=sheet_name,
            visibility=visibility,
            worksheet_max_row=worksheet_max_row,
            worksheet_max_column=worksheet_max_column,
            observed_non_empty_row_count=observed_non_empty_row_count,
            observed_non_empty_cell_count=observed_non_empty_cell_count,
            observed_last_non_empty_row=observed_last_non_empty_row,
            observed_last_non_empty_column=observed_last_non_empty_column,
        )

    @staticmethod
    def _validate_cell(
        payload: dict[str, Any],
        *,
        expected_index: int,
    ) -> ValidatedBorrowingHeaderCellEvidence:
        context = f"cells[{expected_index - 1}]"
        BorrowingInspectionEvidenceValidator._require_exact_keys(payload, _CELL_KEYS, context)
        column_index = BorrowingInspectionEvidenceValidator._require_int(
            payload["column_index"], f"{context}.column_index", minimum=1
        )
        if column_index != expected_index:
            raise ValueError("borrowing header cell indexes must be contiguous and 1-based")

        column_letter = BorrowingInspectionEvidenceValidator._require_string(
            payload["column_letter"], f"{context}.column_letter"
        )
        if column_letter != get_column_letter(column_index):
            raise ValueError("borrowing header column letter does not match column index")

        raw_label = payload["label"]
        if raw_label is None:
            label = None
        elif not isinstance(raw_label, str) or not raw_label.strip():
            raise ValueError("borrowing header label must be nonblank text or null")
        else:
            label = raw_label

        return ValidatedBorrowingHeaderCellEvidence(
            column_index=column_index,
            column_letter=column_letter,
            label=label,
        )

    @staticmethod
    def _duplicate_labels(
        cells: tuple[ValidatedBorrowingHeaderCellEvidence, ...],
    ) -> tuple[str, ...]:
        first_exact_label_by_key: dict[str, str] = {}
        duplicate_keys: set[str] = set()
        for cell in cells:
            if cell.label is None:
                continue
            key = " ".join(cell.label.split()).casefold()
            if key in first_exact_label_by_key:
                duplicate_keys.add(key)
            else:
                first_exact_label_by_key[key] = cell.label
        return tuple(first_exact_label_by_key[key] for key in sorted(duplicate_keys))

    @staticmethod
    def _require_exact_keys(
        payload: dict[str, Any],
        expected_keys: frozenset[str],
        context: str,
    ) -> None:
        actual_keys = frozenset(payload)
        if actual_keys == expected_keys:
            return
        missing = sorted(expected_keys - actual_keys)
        unexpected = sorted(actual_keys - expected_keys)
        raise ValueError(
            f"{context} shape mismatch; missing={missing!r}, unexpected={unexpected!r}"
        )

    @staticmethod
    def _require_dict(value: object, context: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError(f"{context} must be an object")
        if not all(isinstance(key, str) for key in value):
            raise ValueError(f"{context} keys must be strings")
        return value

    @staticmethod
    def _require_list(value: object, context: str) -> list[Any]:
        if not isinstance(value, list):
            raise ValueError(f"{context} must be an array")
        return value

    @staticmethod
    def _require_string(value: object, context: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{context} must be nonblank text")
        return value

    @staticmethod
    def _require_int(value: object, context: str, *, minimum: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValueError(f"{context} must be an integer >= {minimum}")
        return value
