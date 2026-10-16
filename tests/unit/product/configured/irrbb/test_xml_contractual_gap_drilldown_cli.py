from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from aip.product.configured.irrbb.xml_contractual_gap_drilldown_cli import summarize
from aip.product.configured.irrbb.xml_contractual_coverage import REQUIRED_FIELDS


class Reader:
    def resolve_source(self, *, key, cutoff_date):
        assert cutoff_date == date(2026, 9, 30)
        return SimpleNamespace(key=key, path=Path(key + ".xml"))

    def iter_records(self, source):
        values = {key: "1" for key in REQUIRED_FIELDS[source.key]}
        if source.key == "CREDIT":
            values.update(
                TipoOperacion="2",
                TipoEstadoOperacionCrediticia="1",
                TipoCuotaPrincipal="3",
                FechaProximoPagoPrincipal="",
            )
        else:
            values.update(TipoOperacionObligaciones="5", TipoTasa="1")
        yield SimpleNamespace(values=values)


def test_aggregate_product_groups_and_missing_fields():
    result = summarize(Reader(), date(2026, 9, 30))
    assert [row["source"] for row in result] == ["CREDIT", "BORROWING"]
    assert result[0]["records"] == 1
    group = result[0]["groups"][0]
    assert group["category"]["TipoOperacion"] == "2"
    assert group["missing_by_field"]["FechaProximoPagoPrincipal"] == 1
    assert result[1]["groups"][0]["missing_by_field"]["FechaVencimiento"] == 0
    assert "IdOperacion" not in str(result)
