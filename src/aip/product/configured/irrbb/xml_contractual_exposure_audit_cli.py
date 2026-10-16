"""Read-only exposure-weighted quality audit of CONFÍA contractual XML data.

No scheduling, repricing classification, currency conversion or personal identifiers.
Amounts remain grouped by their reported currency and product codes.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from xml.etree.ElementTree import ParseError

from aip.product.configured.configuration.institutional_paths import (
    expand_environment_path,
)
from aip.product.configured.irrbb.xml_confia_source import XMLConfiaMonthlySourceReader
from aip.product.configured.irrbb.xml_contractual_coverage import REQUIRED_FIELDS
from aip.product.configured.irrbb.xml_contractual_gap_drilldown_cli import GROUP_FIELDS
from aip.product.demo.configuration.environment_loader import EnvironmentLoader

BALANCE_FIELDS = {
    "CREDIT": ("SaldoPrincipalOperacionCrediticia", "TipoMonedaOperacion"),
    "BORROWING": ("SaldoPrincipal", "TipoMonedaObligacion"),
    "CAPTACIONES": ("SaldoPrincipal", "TipoMonedaObligacion"),
}


@dataclass
class _Accumulator:
    records: int = 0
    valued_records: int = 0
    invalid_balance_records: int = 0
    negative_balance_records: int = 0
    missing_currency_records: int = 0
    balance: Decimal = Decimal(0)
    missing_count: dict[str, int] = field(default_factory=dict)
    missing_balance: dict[str, Decimal] = field(default_factory=dict)


def _nonnegative_amount(raw: str) -> Decimal | None:
    try:
        amount = Decimal(raw)
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite() or amount < 0:
        return None
    return amount


def audit(reader: XMLConfiaMonthlySourceReader, cutoff: date) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    expected_entity: str | None = None
    expected_period: date | None = None
    for source_key, categories in GROUP_FIELDS.items():
        source = reader.resolve_source(key=source_key, cutoff_date=cutoff)
        entity = source.header.id_entidad
        period = source.header.periodo
        if expected_entity is not None and entity != expected_entity:
            raise ValueError("XML sources contain different entity identifiers")
        if (period.year, period.month) != (cutoff.year, cutoff.month):
            raise ValueError("XML source does not match requested cutoff")
        if expected_period is not None and period != expected_period:
            raise ValueError("XML sources contain different reporting periods")
        expected_entity, expected_period = entity, period
        balance_field, currency_field = BALANCE_FIELDS[source_key]
        groups: dict[tuple[str, ...], _Accumulator] = {}
        for record in reader.iter_records(source):
            currency = record.values.get(currency_field, "").strip()
            values = tuple(
                record.values.get(field, "").strip() or "(VACIO)" for field in categories
            )
            key = (currency or "(VACIO)", *values)
            row = groups.setdefault(key, _Accumulator())
            row.records += 1
            missing = [
                field_name
                for field_name in REQUIRED_FIELDS[source_key]
                if not record.values.get(field_name, "").strip()
            ]
            for field_name in missing:
                row.missing_count[field_name] = row.missing_count.get(field_name, 0) + 1
            raw_balance = record.values.get(balance_field, "").strip()
            amount = _nonnegative_amount(raw_balance)
            if amount is None:
                if raw_balance:
                    try:
                        parsed = Decimal(raw_balance)
                    except (InvalidOperation, ValueError):
                        parsed = None
                    if parsed is not None and parsed.is_finite() and parsed < 0:
                        row.negative_balance_records += 1
                    else:
                        row.invalid_balance_records += 1
                else:
                    row.invalid_balance_records += 1
                continue
            if not currency:
                row.missing_currency_records += 1
                continue
            row.valued_records += 1
            row.balance += amount
            for field_name in missing:
                row.missing_balance[field_name] = (
                    row.missing_balance.get(field_name, Decimal(0)) + amount
                )
        output.append(
            {
                "source": source_key,
                "filename": source.path.name,
                "records": sum(row.records for row in groups.values()),
                "groups": [
                    {
                        "currency_code": key[0],
                        "category_codes": dict(zip(categories, key[1:])),
                        "records": row.records,
                        "valued_records": row.valued_records,
                        "invalid_balance_records": row.invalid_balance_records,
                        "negative_balance_records": row.negative_balance_records,
                        "missing_currency_records": row.missing_currency_records,
                        "principal_balance": str(row.balance),
                        "missing_by_field": {
                            field_name: {
                                "records": row.missing_count.get(field_name, 0),
                                "principal_balance": str(
                                    row.missing_balance.get(field_name, Decimal(0))
                                ),
                            }
                            for field_name in REQUIRED_FIELDS[source_key]
                        },
                    }
                    for key, row in sorted(groups.items())
                ],
            }
        )
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RTILB aggregate principal exposure audit")
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
        results = audit(XMLConfiaMonthlySourceReader(root), cutoff)
    except (OSError, ValueError, KeyError, ParseError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason_type": type(exc).__name__}))
        return 2
    print(
        json.dumps(
            {
                "status": "AGGREGATE_EXPOSURE_AUDITED",
                "cutoff": cutoff.isoformat(),
                "sources": results,
                "note": "Amounts are unconverted source principal by currency and product code; not IRRBB cash flows or certified 19-band results.",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
