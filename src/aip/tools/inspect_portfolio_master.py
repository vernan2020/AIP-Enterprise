from __future__ import annotations

import argparse
from pathlib import Path

from aip.product.configured.readers.institutional_portfolio_master_reader import InstitutionalPortfolioMasterReader


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a portfolio master workbook without exposing row values")
    parser.add_argument("path")
    args = parser.parse_args()

    path = Path(args.path)
    reader = InstitutionalPortfolioMasterReader()
    result = reader.read(path, diagnostic_mode=True)
    print(f"workbook_type: {result.diagnostics.get('workbook_type', 'unknown')}")
    print(f"sheet_names: {result.diagnostics.get('sheets', [])}")
    print(f"sheet_selected: {result.sheet_selected}")
    print(f"header_row: {result.diagnostics.get('header_row')}")
    print(f"rows_read: {result.diagnostics.get('rows_read')}")
    print(f"rows_accepted: {result.diagnostics.get('rows_accepted')}")
    print(f"rows_rejected: {result.diagnostics.get('rows_rejected')}")
    print("normalized_headers:")
    for header in result.diagnostics.get("normalized_headers", []):
        print(f"  - {header}")
    print("detected_mappings:")
    for key, value in result.detected_column_mapping.items():
        print(f"  - {key}: {value}")
    first_rejected_row = result.diagnostics.get("first_rejected_row")
    if first_rejected_row:
        print("first_rejected_row:")
        print(f"  row: {first_rejected_row.get('row')}")
        print(f"  raw_row_values: {first_rejected_row.get('raw_row_values')}")
        print(f"  required_fields: {first_rejected_row.get('required_fields')}")
        print(f"  validation_result: {first_rejected_row.get('validation_result')}")
        print(f"  rejection_reason: {first_rejected_row.get('rejection_reason')}")


if __name__ == "__main__":
    main()
