"""Read-only CLI for contractual XML field coverage (no identifiers or amounts)."""

from __future__ import annotations

import argparse
import json
from datetime import date
from xml.etree.ElementTree import ParseError

from aip.product.configured.configuration.institutional_paths import expand_environment_path
from aip.product.configured.irrbb.xml_confia_source import XMLConfiaMonthlySourceReader
from aip.product.configured.irrbb.xml_contractual_coverage import inspect_xml_contractual_coverage
from aip.product.demo.configuration.environment_loader import EnvironmentLoader


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RTILB contractual XML coverage")
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
        result = inspect_xml_contractual_coverage(
            XMLConfiaMonthlySourceReader(root), cutoff_date=cutoff
        )
    except (OSError, ValueError, KeyError, ParseError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason_type": type(exc).__name__}))
        return 2
    print(
        json.dumps(
            {
                "status": "COVERAGE_INSPECTED",
                "cutoff": cutoff.isoformat(),
                "sources": [
                    {
                        "source": item.key,
                        "filename": item.filename,
                        "period": item.period.isoformat(),
                        "entity_id": item.entity_id,
                        "records": item.record_count,
                        "field_status": item.status,
                        "missing_by_field": dict(item.missing_by_field),
                    }
                    for item in result
                ],
                "investment_source": "INSTITUTIONAL_PORTFOLIO_MASTER",
                "note": "Coverage only: no contractual flows, 19-band certification, EVE or NII.",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
