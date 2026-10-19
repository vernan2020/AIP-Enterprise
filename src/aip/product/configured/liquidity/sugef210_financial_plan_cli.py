"""Read-only diagnostic of the real 2026 planning matrix; no cash booking."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date
from decimal import Decimal

from aip.product.configured.liquidity.financial_plan_source import (
    read_financial_plan_assumptions,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="AIP SUGEF 2-10: inspeccionar supuestos de plan financiero institucional"
    )
    parser.add_argument("--cutoff", required=True, help="AAAA-MM-DD, fecha de corte")
    parser.add_argument("--file", required=True, help="Ruta local de matriz .xlsx")
    args = parser.parse_args(argv)
    try:
        cutoff = date.fromisoformat(args.cutoff)
        report = read_financial_plan_assumptions(args.file, cutoff=cutoff)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({
            "status": "BLOCKED_PLANNING_SOURCE",
            "error_type": type(exc).__name__,
            "cutoff": args.cutoff,
            "cashflows_booked": 0,
        }, ensure_ascii=False, indent=2))
        return 2

    future_by_driver: dict[str, Decimal] = defaultdict(Decimal)
    counts: dict[str, int] = defaultdict(int)
    for item in report.monthly_inputs:
        counts[item.classification] += 1
        if item.status == "PENDING_APPROVAL_CURRENCY_DATE_AND_DUPLICATION_REVIEW":
            future_by_driver[item.driver] += item.reported_value
    print(json.dumps({
        "status": report.status,
        "cutoff": cutoff.isoformat(),
        "plan_year": report.plan_year,
        "source_name": report.source_name,
        "source_sha256": report.sha256,
        "parameters_found": len(report.parameters),
        "monthly_source_rows": len(report.monthly_inputs),
        "classification_counts": dict(counts),
        "future_monthly_reference_totals_crc_millions": {
            key: str(value) for key, value in sorted(future_by_driver.items())
        },
        "plan_driver_parameters": [
            {
                "id": parameter.plan_id,
                "name": parameter.name,
                "value": parameter.value,
                "unit": parameter.unit,
                "source_cell": parameter.source_cell,
                "plan_reference": parameter.plan_reference,
                "liquidity_role": parameter.liquidity_role,
            }
            for parameter in report.parameters
            if parameter.plan_id in {1, 9, 34, 35, 38, 40, 42, 43, 44, 49, 50}
        ],
        "warnings": list(report.observations),
        "liquidity_cashflows_added": 0,
        "ready_for_regulatory_publication": False,
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
