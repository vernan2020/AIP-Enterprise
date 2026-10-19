"""Read-only XML coverage fixtures; not production or forecast data."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from decimal import Decimal

from aip.product.configured.irrbb.xml_confia_source import (
    XMLConfiaHeader,
    XMLConfiaRecord,
    XMLConfiaResolvedSource,
)
from aip.product.configured.liquidity.sugef210_xml_perimeter_audit import (
    audit_xml_liquidity_perimeters,
    summarize_xml_liquidity_perimeters,
)


CUTOFF = date(2026, 9, 30)


class Reader:
    def resolve_source(self, *, key: str, cutoff_date: date) -> XMLConfiaResolvedSource:
        assert cutoff_date == CUTOFF
        if key == "BORROWING_MATURITY":
            raise FileNotFoundError("missing month")
        return XMLConfiaResolvedSource(
            key,
            Path(key + ".xml"),
            XMLConfiaHeader("1", key, date(2026, 9, 1), "3004045138", "1", "1"),
        )

    def iter_records(self, source: XMLConfiaResolvedSource):
        if source.key == "CREDIT":
            yield XMLConfiaRecord(
                "1", "insertar",
                {
                    "SaldoPrincipalOperacionCrediticia": "75.50",
                    "TipoMonedaOperacion": "1",
                    "CuentaContablePrincipal": "131",
                    "FechaVencimiento": "30/12/2027",
                    "FechaProximoPagoPrincipal": "31/10/2026",
                    "FechaProximoPagoIntereses": "not-date",
                },
            )
        if source.key == "CAPTACIONES":
            yield XMLConfiaRecord(
                "2", "insertar",
                {
                    "SaldoPrincipal": "150",
                    "TipoMonedaObligacion": "2",
                    "CuentaContablePrincipal": "211",
                    "TipoCuenta": "D",
                },
            )
            yield XMLConfiaRecord(
                "3", "insertar",
                {
                    "SaldoPrincipal": "unreadable",
                    "TipoMonedaObligacion": "2",
                    "CuentaContablePrincipal": "211",
                    "TipoCuenta": "P",
                    "FechaVencimiento": "31/10/2026",
                },
            )
        if source.key == "BORROWING":
            yield XMLConfiaRecord(
                "4", "insertar",
                {
                    "SaldoPrincipal": "800",
                    "TipoMonedaObligacion": "1",
                    "CuentaContablePrincipal": "220",
                    "FechaVencimiento": "30/09/2027",
                    "FechaProximoPagoPrincipal": "",
                    "FechaProximoPagoInteres": "",
                },
            )

    @staticmethod
    def sha256(path: Path) -> str:
        return "a" * 64


def test_real_xml_shapes_are_audited_without_cash_booking():
    reports = audit_xml_liquidity_perimeters(reader=Reader(), cutoff=CUTOFF)
    assert [r.key for r in reports] == [
        "CREDIT", "CAPTACIONES", "BORROWING", "BORROWING_MATURITY"
    ]
    credit, deposits, borrowing, maturity = reports
    assert credit.records == 1
    assert credit.native_balances == (("1", Decimal("75.50")),)
    assert ("FechaProximoPagoIntereses", 0, 0, 1) in credit.date_counts
    assert deposits.records == 2
    assert deposits.invalid_balance == 1
    assert ("FechaVencimiento", 1, 1, 0) in deposits.date_counts
    assert deposits.original_categories == (("D", 1), ("P", 1))
    assert borrowing.date_counts[1][2] == 1
    assert maturity.status == "SOURCE_UNAVAILABLE_NOT_ASSUMED_ZERO"
    assert maturity.error_type == "FileNotFoundError"
    assert all(not row.payment_amounts_certified for row in reports)


def test_raw_currency_codes_do_not_become_crc_or_usd_without_catalog():
    result = summarize_xml_liquidity_perimeters(
        audit_xml_liquidity_perimeters(reader=Reader(), cutoff=CUTOFF)
    )
    assert result[1]["source_currency_balances_not_cashflows"] == {"2": "150"}
    assert result[3]["individual_payment_amounts_certified"] is False
    assert result[3]["records"] == 0
