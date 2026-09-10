from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import NoReturn, TextIO

from aip.product.configured.irrbb.borrowing_workbook_inspector import (
    BorrowingWorkbookDiscovery,
    BorrowingWorkbookHeaderInspection,
    BorrowingWorkbookSchemaInspector,
)

BORROWING_INSPECTION_REPORT_VERSION = "2026.09.10"
DISCOVERY_REPORT_TYPE = "IRRBB_BORROWING_WORKBOOK_DISCOVERY"
HEADER_REPORT_TYPE = "IRRBB_BORROWING_WORKBOOK_HEADER"


class _CLIUsageError(ValueError):
    """Safe command-line usage failure without argparse process termination."""


class _SafeArgumentParser(argparse.ArgumentParser):
    """Argument parser that reports usage errors through the CLI return contract."""

    def error(self, message: str) -> NoReturn:
        raise _CLIUsageError(message)


def borrowing_discovery_report(discovery: BorrowingWorkbookDiscovery) -> dict[str, object]:
    """Serialize discovery evidence without filesystem parent paths or data rows."""

    return {
        "report_type": DISCOVERY_REPORT_TYPE,
        "report_version": BORROWING_INSPECTION_REPORT_VERSION,
        "source_id": discovery.source_id,
        "source_reference": discovery.source_reference,
        "source_file_name": discovery.source_file_name,
        "file_sha256": discovery.file_sha256,
        "sheets": [
            {
                "sheet_name": sheet.sheet_name,
                "visibility": sheet.visibility,
                "worksheet_max_row": sheet.worksheet_max_row,
                "worksheet_max_column": sheet.worksheet_max_column,
                "observed_non_empty_row_count": sheet.observed_non_empty_row_count,
                "observed_non_empty_cell_count": sheet.observed_non_empty_cell_count,
                "observed_last_non_empty_row": sheet.observed_last_non_empty_row,
                "observed_last_non_empty_column": sheet.observed_last_non_empty_column,
            }
            for sheet in discovery.sheets
        ],
    }


def borrowing_header_report(inspection: BorrowingWorkbookHeaderInspection) -> dict[str, object]:
    """Serialize explicit header evidence without reading or exporting contract rows."""

    discovery = inspection.discovery
    return {
        "report_type": HEADER_REPORT_TYPE,
        "report_version": BORROWING_INSPECTION_REPORT_VERSION,
        "source_id": discovery.source_id,
        "source_reference": discovery.source_reference,
        "source_file_name": discovery.source_file_name,
        "file_sha256": discovery.file_sha256,
        "sheet_name": inspection.sheet_name,
        "header_row": inspection.header_row,
        "cells": [
            {
                "column_index": cell.column_index,
                "column_letter": cell.column_letter,
                "label": cell.label,
            }
            for cell in inspection.cells
        ],
        "blank_column_indexes": list(inspection.blank_column_indexes),
        "duplicate_labels": list(inspection.duplicate_labels),
    }


def _build_parser() -> _SafeArgumentParser:
    parser = _SafeArgumentParser(
        prog="irrbb-borrowing-inspect",
        description="Capture schema evidence from the governed obligations workbook.",
    )
    parser.add_argument(
        "--path",
        required=True,
        help="Path to the governed obligations workbook on the local workstation.",
    )
    parser.add_argument(
        "--sheet",
        help="Exact worksheet name to inspect. Must be supplied with --header-row.",
    )
    parser.add_argument(
        "--header-row",
        type=int,
        help="Exact 1-based header row. Must be supplied with --sheet.",
    )
    return parser


def _write_report(report: dict[str, object], *, stdout: TextIO) -> None:
    json.dump(report, stdout, ensure_ascii=False, indent=2, sort_keys=True)
    stdout.write("\n")


def run(
    argv: Sequence[str],
    *,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    """Execute one local inspection and return a process-style status code."""

    try:
        args = _build_parser().parse_args(tuple(argv))
        if (args.sheet is None) != (args.header_row is None):
            raise _CLIUsageError("--sheet and --header-row must be supplied together")

        inspector = BorrowingWorkbookSchemaInspector()
        if args.sheet is None:
            report = borrowing_discovery_report(inspector.discover(args.path))
        else:
            report = borrowing_header_report(
                inspector.inspect_declared_header(
                    args.path,
                    sheet_name=args.sheet,
                    header_row=args.header_row,
                )
            )
        _write_report(report, stdout=stdout)
        return 0
    except _CLIUsageError as exc:
        stderr.write(f"IRRBB borrowing inspection usage error: {exc}\n")
        return 2
    except (FileNotFoundError, KeyError, ValueError) as exc:
        stderr.write(f"IRRBB borrowing inspection failed: {exc}\n")
        return 1
    except OSError:
        stderr.write("IRRBB borrowing inspection failed: filesystem access error\n")
        return 1


def main() -> int:
    """Run the local diagnostic using process standard streams."""

    return run(sys.argv[1:], stdout=sys.stdout, stderr=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
