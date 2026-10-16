from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from aip.product.configured.irrbb.xml_contractual_exposure_audit_cli import audit


class Reader:
    def __init__(self, *, stale: bool = False, mixed_entity: bool = False) -> None:
        self.stale = stale
        self.mixed_entity = mixed_entity

    def resolve_source(self, *, key: str, cutoff_date: date):
        assert cutoff_date == date(2026, 9, 30)
        period = date(2026, 8, 1) if self.stale and key == "CAPTACIONES" else date(2026, 9, 1)
        entity = "OTHER" if self.mixed_entity and key == "BORROWING" else "COOPEALIANZA"
        return SimpleNamespace(
            key=key,
            path=Path(key + ".xml"),
            header=SimpleNamespace(periodo=period, id_entidad=entity),
        )

    def iter_records(self, source):
        if source.key == "CREDIT":
            yield SimpleNamespace(
                values={
                    "TipoOperacion": "3",
                    "TipoEstadoOperacionCrediticia": "1",
                    "TipoCuotaPrincipal": "",
                    "SaldoPrincipalOperacionCrediticia": "100.50",
                    "TipoMonedaOperacion": "CRC",
                    "FechaVencimiento": "2027-10-31",
                    "FechaProximoPagoPrincipal": "",
                    "FechaProximoPagoIntereses": "",
                    "IndicadorTipoTasa": "",
                }
            )
            yield SimpleNamespace(
                values={
                    "TipoOperacion": "3",
                    "TipoEstadoOperacionCrediticia": "1",
                    "TipoCuotaPrincipal": "",
                    "SaldoPrincipalOperacionCrediticia": "20.25",
                    "TipoMonedaOperacion": "USD",
                    "FechaVencimiento": "2027-10-31",
                    "FechaProximoPagoPrincipal": "2026-10-15",
                    "FechaProximoPagoIntereses": "2026-10-15",
                    "IndicadorTipoTasa": "V",
                }
            )
        elif source.key == "BORROWING":
            yield SimpleNamespace(
                values={
                    "TipoOperacionObligaciones": "99",
                    "TipoTasa": "F",
                    "SaldoPrincipal": "-5.0",
                    "TipoMonedaObligacion": "CRC",
                    "FechaVencimiento": "2027-09-01",
                    "FechaProximoPagoPrincipal": "",
                    "FechaProximoPagoInteres": "",
                }
            )
        else:
            yield SimpleNamespace(
                values={
                    "TipoCuenta": "2",
                    "TipoOperacionObligaciones": "1",
                    "TipoTasa": "V",
                    "SaldoPrincipal": "200",
                    "TipoMonedaObligacion": "CRC",
                }
            )


def test_audit_keeps_currency_codes_separate_and_preserves_decimal() -> None:
    result = audit(Reader(), date(2026, 9, 30))
    assert [source["source"] for source in result] == ["CREDIT", "BORROWING", "CAPTACIONES"]
    credit_groups = result[0]["groups"]
    assert len(credit_groups) == 2
    crc = next(group for group in credit_groups if group["currency_code"] == "CRC")
    usd = next(group for group in credit_groups if group["currency_code"] == "USD")
    assert crc["principal_balance"] == "100.50"
    assert usd["principal_balance"] == "20.25"
    assert crc["missing_by_field"]["FechaProximoPagoPrincipal"] == {
        "records": 1,
        "principal_balance": "100.50",
    }
    assert usd["missing_by_field"]["FechaProximoPagoPrincipal"]["records"] == 0
    assert result[1]["groups"][0]["negative_balance_records"] == 1
    assert result[1]["groups"][0]["valued_records"] == 0
    assert result[2]["groups"][0]["principal_balance"] == "200"
    assert "IdOperacion" not in str(result)


def test_audit_rejects_mixed_entities() -> None:
    with pytest.raises(ValueError, match="different entity"):
        audit(Reader(mixed_entity=True), date(2026, 9, 30))


def test_audit_rejects_stale_month() -> None:
    with pytest.raises(ValueError, match="does not match requested cutoff"):
        audit(Reader(stale=True), date(2026, 9, 30))
