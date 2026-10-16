from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from aip.product.configured.irrbb.xml_contractual_coverage import (
    REQUIRED_FIELDS,
    inspect_xml_contractual_coverage,
)


class SourceReader:
    def __init__(self, *, missing: bool = False, wrong_entity: bool = False):
        self.missing = missing
        self.wrong_entity = wrong_entity

    def resolve_source(self, *, key: str, cutoff_date: date):
        assert cutoff_date == date(2026, 9, 30)
        entity = "OTHER" if self.wrong_entity and key == "BORROWING" else "3004045138"
        return SimpleNamespace(
            path=Path(f"{key}.xml"),
            header=SimpleNamespace(periodo=date(2026, 9, 1), id_entidad=entity),
            key=key,
        )

    def iter_records(self, source):
        values = {field: "nonempty" for field in REQUIRED_FIELDS[source.key]}
        if self.missing and source.key == "CREDIT":
            values["FechaVencimiento"] = ""
        yield SimpleNamespace(values=values)


def test_contractual_coverage_counts_field_gaps_without_exposing_records():
    results = inspect_xml_contractual_coverage(
        SourceReader(missing=True), cutoff_date=date(2026, 9, 30)
    )
    assert len(results) == 4
    credit = results[0]
    assert credit.record_count == 1
    assert credit.status == "FIELD_GAPS_FOUND"
    assert dict(credit.missing_by_field)["FechaVencimiento"] == 1
    assert all(result.key != "INVESTMENT" for result in results)


def test_contractual_coverage_requires_same_entity():
    with pytest.raises(ValueError, match="inconsistent entity"):
        inspect_xml_contractual_coverage(
            SourceReader(wrong_entity=True), cutoff_date=date(2026, 9, 30)
        )


def test_complete_fields_are_not_mistaken_for_certified_flows():
    results = inspect_xml_contractual_coverage(SourceReader(), cutoff_date=date(2026, 9, 30))
    assert all(row.status == "FIELDS_POPULATED" for row in results)
    assert not hasattr(results[0], "cash_flows")
