"""Configured CLI: auditable XML term-deposit maturity, not financial RTILB GAP."""

from __future__ import annotations

import argparse
import json
from datetime import date
from xml.etree.ElementTree import ParseError

from aip.product.configured.configuration.institutional_paths import expand_environment_path
from aip.product.configured.irrbb.captaciones_maturity_19band_audit import (
    inspect_fixed_term_maturities,
)
from aip.product.configured.irrbb.xml_confia_source import XMLConfiaMonthlySourceReader
from aip.product.demo.configuration.environment_loader import EnvironmentLoader


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AIP RTILB: 19-band maturity evidence")
    parser.add_argument("--cutoff", default="2026-09-30")
    args = parser.parse_args(argv)
    try:
        cutoff = date.fromisoformat(args.cutoff)
    except ValueError:
        parser.error("--cutoff requires YYYY-MM-DD")
    config = EnvironmentLoader().load_source_config().xml_confia
    root = expand_environment_path(config.root)
    if not config.enabled or not root:
        print(json.dumps({"status": "UNCONFIGURED"}))
        return 2
    try:
        results = inspect_fixed_term_maturities(XMLConfiaMonthlySourceReader(root), cutoff)
    except (OSError, ValueError, KeyError, ParseError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason_type": type(exc).__name__}))
        return 2
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
