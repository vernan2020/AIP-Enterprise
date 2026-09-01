from __future__ import annotations

import argparse
from pathlib import Path

from aip.product.configured.readers.pipca_vector_reader import InstitutionalPiPCAVectorReader


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect a PiPCA vector file without exposing confidential values"
    )
    parser.add_argument("path")
    parser.add_argument(
        "--search",
        dest="search",
        default=None,
        help="Filter diagnostics to lines containing the provided token",
    )
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
        matches = [
            entry
            for entry in trace.get("line_diagnostics", [])
            if args.search.lower() in str(entry.get("raw_line", "")).lower()
        ]
        if not matches:
            print(f"No raw lines contained token '{args.search}'.")
            return
        for entry in matches:
            issuer_slice = entry.get("issuer_slice", {})
            product_series_slice = entry.get("product_series_slice", {})
            maturity_slice = entry.get("maturity_slice", {})
            print(f"line={entry.get('line')}")
            print(f"raw_line_length={entry.get('raw_line_length')}")
            print(f"masked_raw_line={entry.get('masked_raw_line')}")
            print(f"parser_branch={entry.get('parser_branch', 'unknown')}")
            print(
                f"issuer_slice[{issuer_slice.get('start')}:{issuer_slice.get('end')}]={issuer_slice.get('text', '')}"
            )
            print(
                f"product_series_slice[{product_series_slice.get('start')}:{product_series_slice.get('end')}]={product_series_slice.get('text', '')}"
            )
            print(
                f"maturity_slice[{maturity_slice.get('start')}:{maturity_slice.get('end')}]={maturity_slice.get('text', '')}"
            )
            print(f"parsed_issuer={entry.get('parsed_issuer', '')}")
            print(f"parsed_product={entry.get('parsed_product', '')}")
            print(f"parsed_series={entry.get('parsed_series', '')}")
            print(f"raw_maturity={entry.get('raw_maturity', '')}")
            print(f"parsed_maturity={entry.get('parsed_maturity', '')}")
            print(f"status={entry.get('status', 'unknown')}")
            print(f"reason={entry.get('reason', '')}")
            print(f"raw_identifier={entry.get('raw_identifier', '')}")
        return

    print("examples:")
    for record in result.records[:3]:
        print(
            f"  - issuer={record.issuer} mnemonic={record.instrument_type_or_mnemonic} series={record.series_or_security_code} maturity={record.maturity_date_if_present}"
        )


if __name__ == "__main__":
    main()
