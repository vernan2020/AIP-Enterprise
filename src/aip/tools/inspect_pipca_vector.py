from __future__ import annotations

import argparse
from pathlib import Path

from aip.product.configured.readers.pipca_vector_reader import InstitutionalPiPCAVectorReader


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a PiPCA vector file without exposing confidential values")
    parser.add_argument("path")
    parser.add_argument("--search", dest="search", default=None, help="Filter diagnostics to lines containing the provided token")
    args = parser.parse_args()

    path = Path(args.path)
    reader = InstitutionalPiPCAVectorReader()
    result = reader.read(path, diagnostic_mode=True)
    print(f"encoding: {result.encoding}")
    print(f"line_count: {result.diagnostics.get('line_count', 0)}")
    print(f"layout: {result.diagnostics.get('layout', 'unknown')}")
    print(f"accepted_count: {result.accepted_count}")
    print(f"rejected_count: {result.rejected_count}")

    trace = result.diagnostics.get("trace", {})
    if args.search:
        for entry in trace.get("record_trace", []):
            if args.search.lower() in str(entry.get("raw_identifier", "")).lower() or args.search.lower() in str(entry.get("issuer", "")).lower() or args.search.lower() in str(entry.get("series_or_security_code", "")).lower():
                status = entry.get("status", "unknown")
                print(f"line={entry.get('line')} status={status} reason={entry.get('reason')} branch={entry.get('branch')} field_widths={entry.get('field_widths')} raw_identifier={entry.get('raw_identifier')}")
        return

    print("examples:")
    for record in result.records[:3]:
        print(f"  - issuer={record.issuer} mnemonic={record.instrument_type_or_mnemonic} series={record.series_or_security_code} maturity={record.maturity_date_if_present}")


if __name__ == "__main__":
    main()
