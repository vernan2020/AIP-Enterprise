"""Read-only per-product classification of missing RTILB contractual XML fields."""

from __future__ import annotations

import argparse
import json
from datetime import date
from typing import TypedDict
from xml.etree.ElementTree import ParseError

from aip.product.configured.configuration.institutional_paths import (
    expand_environment_path,
)
from aip.product.configured.irrbb.xml_confia_source import (
    XMLConfiaMonthlySourceReader,
)
from aip.product.configured.irrbb.xml_contractual_coverage import REQUIRED_FIELDS
from aip.product.demo.configuration.environment_loader import EnvironmentLoader


class _GroupCounts(TypedDict):
    records: int
    missing: dict[str, int]


GROUP_FIELDS = {
    "CREDIT": ("TipoOperacion", "TipoEstadoOperacionCrediticia", "TipoCuotaPrincipal"),
    "BORROWING": ("TipoOperacionObligaciones", "TipoTasa"),
    "CAPTACIONES": ("TipoCuenta", "TipoOperacionObligaciones", "TipoTasa"),
}


def summarize(reader: XMLConfiaMonthlySourceReader, cutoff: date) -> list[dict]:
    result = []
    expected_entity = None
    expected_period = None
    for key, categories in GROUP_FIELDS.items():
        source = reader.resolve_source(key=key, cutoff_date=cutoff)
        entity = source.header.id_entidad
        if expected_entity is not None and entity != expected_entity:
            raise ValueError("Inconsistent entity across contractual XML sources")
        expected_entity = entity
        period = source.header.periodo
        if (period.year, period.month) != (cutoff.year, cutoff.month):
            raise ValueError("Contractual XML period differs from requested cutoff")
        if expected_period is not None and period != expected_period:
            raise ValueError("Inconsistent period across contractual XML sources")
        expected_period = period
        grouped: dict[tuple[str, ...], _GroupCounts] = {}
        for record in reader.iter_records(source):
            group_key = tuple(
                record.values.get(field, "").strip() or "(VACIO)" for field in categories
            )
            group = grouped.setdefault(
                group_key,
                {"records": 0, "missing": {field: 0 for field in REQUIRED_FIELDS[key]}},
            )
            group["records"] += 1
            for field in REQUIRED_FIELDS[key]:
                if not record.values.get(field, "").strip():
                    group["missing"][field] += 1
        groups = [
            {
                "category": dict(zip(categories, values)),
                "records": count["records"],
                "missing_by_field": {
                    field: count["missing"][field] for field in REQUIRED_FIELDS[key]
                },
            }
            for values, count in sorted(grouped.items())
        ]
        result.append(
            {
                "source": key,
                "filename": source.path.name,
                "group_fields": list(categories),
                "records": sum(group["records"] for group in groups),
                "groups": groups,
            }
        )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RTILB field gaps by product")
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
        sources = summarize(XMLConfiaMonthlySourceReader(root), cutoff)
    except (OSError, ValueError, KeyError, ParseError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason_type": type(exc).__name__}))
        return 2
    print(
        json.dumps(
            {
                "status": "AGGREGATE_GAPS_INSPECTED",
                "cutoff": cutoff.isoformat(),
                "sources": sources,
                "note": "Field presence only; not cash flows or 19-band certification.",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
