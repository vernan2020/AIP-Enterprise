from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from aip.product.configured.irrbb.xml_contractual_gap_drilldown_cli import summarize
from aip.product.configured.irrbb.xml_contractual_coverage import REQUIRED_FIELDS


class Reader:
    def resolve_source(self, *, key, cutoff_date):
        assert cutoff_date == date(2026, 9, 30)
        return SimpleNamespace(
            key=key,
            path=Path(key + ".xml"),
            header=SimpleNamespace(id_entidad="3004045138", periodo=date(2026, 9, 1)),
        )

    def iter_records(self, source):
        values = {key: "1" for key in REQUIRED_FIELDS[source.key]}
        if source.key == "CREDIT":
            values.update(
                TipoOperacion="2",
                TipoEstadoOperacionCrediticia="1",
                TipoCuotaPrincipal="3",
                FechaProximoPagoPrincipal="",
            )
        elif source.key == "BORROWING":
            values.update(TipoOperacionObligaciones="5", TipoTasa="1")
        else:
            values.update(TipoCuenta="1", TipoOperacionObligaciones="2", TipoTasa="1")
        yield SimpleNamespace(values=values)


def test_aggregate_product_groups_and_missing_fields():
    result = summarize(Reader(), date(2026, 9, 30))
    assert [row["source"] for row in result] == ["CREDIT", "BORROWING", "CAPTACIONES"]
    assert result[0]["records"] == 1
    group = result[0]["groups"][0]
    assert group["category"]["TipoOperacion"] == "2"
    assert group["missing_by_field"]["FechaProximoPagoPrincipal"] == 1
    assert result[1]["groups"][0]["missing_by_field"]["FechaVencimiento"] == 0
    assert "IdOperacion" not in str(result)


def test_captaciones_grouped_by_account_and_product():
    result = summarize(Reader(), date(2026, 9, 30))
    captaciones = next(row for row in result if row["source"] == "CAPTACIONES")
    assert captaciones["groups"][0]["category"]["TipoCuenta"] == "1"
    assert captaciones["records"] == 1
