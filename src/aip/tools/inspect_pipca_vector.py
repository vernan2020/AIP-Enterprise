from __future__ import annotations

import argparse
from pathlib import Path

from aip.product.configured.readers.pipca_vector_reader import InstitutionalPiPCAVectorReader


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a PiPCA vector file without exposing confidential values")
    parser.add_argument("path")
    args = parser.parse_args()

    path = Path(args.path)
    reader = InstitutionalPiPCAVectorReader()
    result = reader.read(path)
    print(f"encoding: {result.encoding}")
    print(f"line_count: {result.diagnostics.get('line_count', 0)}")
    print(f"layout: {result.diagnostics.get('layout', 'unknown')}")
    print(f"accepted_count: {result.accepted_count}")
    print(f"rejected_count: {result.rejected_count}")
    print("examples:")
    for record in result.records[:3]:
        print(f"  - issuer={record.issuer} mnemonic={record.instrument_type_or_mnemonic} series={record.series_or_security_code} maturity={record.maturity_date_if_present}")


if __name__ == "__main__":
    main()
