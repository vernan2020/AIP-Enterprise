from __future__ import annotations

import argparse
from pathlib import Path

from aip.product.configured.readers.portfolio_master_reader import PortfolioMasterReader


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a portfolio master workbook without exposing row values")
    parser.add_argument("path")
    args = parser.parse_args()

    path = Path(args.path)
    reader = PortfolioMasterReader()
    result = reader.read(path)
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


if __name__ == "__main__":
    main()
