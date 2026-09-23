from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from aip.application.irrbb import IRRBBSourceMappingFailure
from aip.product.configured.irrbb.borrowing_xml_batch_bridge import (
    BorrowingXMLMonthlyNormalizationBridge,
)
from aip.product.configured.irrbb.borrowing_xml_normalizer import (
    BorrowingXMLFact,
    BorrowingXMLNormalizer,
)
from aip.product.configured.irrbb.source_acl import IRRBBSourceRecordEnvelope
from aip.product.configured.irrbb.xml_confia_source import (
    XMLConfiaHeader,
    XMLConfiaRecord,
    XMLConfiaResolvedSource,
)

CUTOFF = date(2026, 8, 31)
SOURCE_PATH = Path(
    "/Institutional/XML CONFÍA/2026/08-AGOSTO/"
    "Pasivos_Cuentas_Contables_220_230_260_270_280.xml"
)
SHA256 = "b" * 64


def _record(record_id: str = "1", **overrides: str) -> XMLConfiaRecord:
    values = {
        "IdAcreedor": "3007782679",
        "IdOperacion": "211",
        "TipoOperacionObligaciones": "12",
        "IndicadorRecibidoGarantia": "N",
        "TipoMonedaObligacion": "1",
        "IndicadorObligacion": "L",
        "IndicadorRevolutiva": "S",
        "IdLineaCredito": "LC-211",
        "IndicadorCondicional": "S",
        "PaisOrigen": "CR",
        "TipoMonedaContrato": "1",
        "TipoMonedaDesembolso": "1",
        "TipoTasa": "V",
        "TipoTasaVariable": "4",
        "Tasa": "4",
        "TipoCatalogoSUGEF": "14",
        "CuentaContablePrincipal": "23221100",
        "SaldoPrincipal": "1987217366.87",
        "MontoContratado": "4500000000",
        "CuentaContableProductos": "23801100",
        "SaldoProducto": "2208019.30",
        "FechaFormalizacion": "23/09/2024",
        "FechaVencimiento": "13/08/2038",
        "FechaProximoPagoPrincipal": "",
        "FechaProximoPagoInteres": "20/09/2026",
        "FrecuenciaPagoActualPrincipal": "",
        "FrecuenciaPagoActualIntereses": "4",
    }
    values.update(overrides)
    return XMLConfiaRecord(record_id=record_id, action="insertar", values=values)


def _envelope(record: XMLConfiaRecord) -> IRRBBSourceRecordEnvelope[XMLConfiaRecord]:
    return IRRBBSourceRecordEnvelope(
        source_record_id=f"XML_CONFIA:obligaciones.xml:record:{record.record_id}",
        source_reference=f"XML_CONFIA:obligaciones.xml|record={record.record_id}",
        payload=record,
    )


def test_normalizer_preserves_source_facts_without_repricing_inference() -> None:
    result = BorrowingXMLNormalizer().normalize(_envelope(_record()))

    assert isinstance(result, BorrowingXMLFact)
    assert result.creditor_id == "3007782679"
    assert result.operation_id == "211"
    assert result.currency_source_code == "1"
    assert result.rate_type_source_code == "V"
    assert result.variable_rate_source_code == "4"
    assert result.nominal_rate_percent == Decimal("4")
    assert result.accounting_account_code == "23221100"
    assert result.principal_amount == Decimal("1987217366.87")
    assert result.product_account_code == "23801100"
    assert result.product_amount == Decimal("2208019.30")
    assert result.maturity_date == date(2038, 8, 13)
    assert result.next_principal_payment_date is None
    assert result.next_interest_payment_date == date(2026, 9, 20)
    assert result.principal_payment_frequency_source_code is None
    assert result.interest_payment_frequency_source_code == "4"


def test_negative_source_balance_is_preserved_for_later_account_policy() -> None:
    result = BorrowingXMLNormalizer().normalize(
        _envelope(
            _record(
                CuentaContablePrincipal="23703100",
                SaldoPrincipal="-9186146.81",
                SaldoProducto="",
            )
        )
    )

    assert isinstance(result, BorrowingXMLFact)
    assert result.accounting_account_code == "23703100"
    assert result.principal_amount == Decimal("-9186146.81")
    assert result.product_amount is None


def test_blank_optional_values_remain_none_instead_of_zero() -> None:
    result = BorrowingXMLNormalizer().normalize(
        _envelope(
            _record(
                Tasa="",
                MontoContratado="",
                CuentaContableProductos="",
                SaldoProducto="",
                FechaFormalizacion="",
                FechaVencimiento="",
                FechaProximoPagoPrincipal="",
                FechaProximoPagoInteres="",
                FrecuenciaPagoActualPrincipal="",
                FrecuenciaPagoActualIntereses="",
            )
        )
    )

    assert isinstance(result, BorrowingXMLFact)
    assert result.nominal_rate_percent is None
    assert result.contracted_amount is None
    assert result.product_account_code is None
    assert result.product_amount is None
    assert result.origination_date is None
    assert result.maturity_date is None
    assert result.next_principal_payment_date is None
    assert result.next_interest_payment_date is None


def test_invalid_optional_date_is_explicit_mapping_failure() -> None:
    result = BorrowingXMLNormalizer().normalize(
        _envelope(_record(FechaVencimiento="2038-08-13"))
    )

    assert isinstance(result, IRRBBSourceMappingFailure)
    assert result.canonical_field == "FechaVencimiento"
    assert "DD/MM/YYYY" in result.message


class _Reader:
    def __init__(self, records: tuple[XMLConfiaRecord, ...]) -> None:
        self.records = records
        self.resolve_calls: list[tuple[str, date]] = []

    def resolve_source(self, *, key: str, cutoff_date: date) -> XMLConfiaResolvedSource:
        self.resolve_calls.append((key, cutoff_date))
        return XMLConfiaResolvedSource(
            key=key,
            path=SOURCE_PATH,
            header=XMLConfiaHeader(
                clase_dato="27",
                archivo="2701",
                periodo=CUTOFF,
                id_entidad="3004045138",
                tipo_carga="1",
                tipo_moneda="1",
            ),
        )

    def iter_records(self, source: XMLConfiaResolvedSource):
        assert source.path == SOURCE_PATH
        yield from self.records

    def sha256(self, path: Path, *, chunk_size: int = 1024 * 1024) -> str:
        assert path == SOURCE_PATH
        assert chunk_size == 1024 * 1024
        return SHA256


def test_monthly_bridge_preserves_every_record_and_source_lineage() -> None:
    reader = _Reader(
        (
            _record("1"),
            _record("2", FechaVencimiento="BAD"),
        )
    )

    result = BorrowingXMLMonthlyNormalizationBridge(source_reader=reader).normalize(
        cutoff_date=CUTOFF
    )

    assert reader.resolve_calls == [("BORROWING", CUTOFF)]
    assert result.source_file_name == SOURCE_PATH.name
    assert result.source_sha256 == SHA256
    assert result.source_record_count == 2
    assert len(result.normalized_facts) == 1
    assert len(result.mapping_failures) == 1
    assert result.normalized_facts[0].source_record_id.endswith(":record:1")
    assert result.mapping_failures[0].source_record_id.endswith(":record:2")
    assert "Institutional" not in result.normalized_facts[0].source_reference


def test_monthly_bridge_rejects_duplicate_record_lineage() -> None:
    reader = _Reader((_record("7"), _record("7")))

    with pytest.raises(ValueError, match="lineage must be unique"):
        BorrowingXMLMonthlyNormalizationBridge(source_reader=reader).normalize(
            cutoff_date=CUTOFF
        )
