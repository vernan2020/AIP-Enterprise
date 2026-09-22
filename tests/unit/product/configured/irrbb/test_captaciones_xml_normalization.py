from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from aip.application.irrbb import IRRBBSourceMappingFailure
from aip.product.configured.irrbb.captaciones_xml_batch_bridge import (
    CaptacionesXMLMonthlyNormalizationBridge,
)
from aip.product.configured.irrbb.captaciones_xml_normalizer import (
    CaptacionesXMLFact,
    CaptacionesXMLNormalizer,
)
from aip.product.configured.irrbb.source_acl import IRRBBSourceRecordEnvelope
from aip.product.configured.irrbb.xml_confia_source import (
    XMLConfiaHeader,
    XMLConfiaRecord,
    XMLConfiaResolvedSource,
)

CUTOFF = date(2026, 8, 31)
SOURCE_PATH = Path("/Institutional/XML CONFÍA/2026/08-AGOSTO/Pasivos_Cuentas_Contables_210.xml")
SHA256 = "a" * 64


def _record(record_id: str = "1", **overrides: str) -> XMLConfiaRecord:
    values = {
        "IdAcreedor": "110910782",
        "IdOperacion": "CR14081300210006484323",
        "TipoOperacionObligaciones": "1",
        "IndicadorRecibidoGarantia": "N",
        "TipoMonedaObligacion": "1",
        "TipoTasa": "V",
        "TipoTasaVariable": "7",
        "Tasa": ".25",
        "TipoCatalogoSUGEF": "14",
        "CuentaContablePrincipal": "21103100",
        "SaldoPrincipal": "1304692.36",
        "CuentaContableProductos": "",
        "SaldoProducto": "0",
        "FechaFormalizacion": "14/04/2023",
        "FechaVencimiento": "01/09/2026",
        "IndicadorSujetoEncaje": "S",
        "TipoCuenta": "4",
        "TipoDepositoFGDLEY9816": "1",
    }
    values.update(overrides)
    return XMLConfiaRecord(record_id=record_id, action="insertar", values=values)


def _envelope(record: XMLConfiaRecord) -> IRRBBSourceRecordEnvelope[XMLConfiaRecord]:
    return IRRBBSourceRecordEnvelope(
        source_record_id=f"XML_CONFIA:Pasivos_Cuentas_Contables_210.xml:record:{record.record_id}",
        source_reference=f"XML_CONFIA:Pasivos_Cuentas_Contables_210.xml|record={record.record_id}",
        payload=record,
    )


def test_normalizer_preserves_source_codes_without_inventing_deposit_semantics() -> None:
    result = CaptacionesXMLNormalizer().normalize(_envelope(_record()))

    assert isinstance(result, CaptacionesXMLFact)
    assert result.creditor_id == "110910782"
    assert result.operation_id == "CR14081300210006484323"
    assert result.currency_source_code == "1"
    assert result.rate_type_source_code == "V"
    assert result.variable_rate_source_code == "7"
    assert result.accounting_account_code == "21103100"
    assert result.account_type_source_code == "4"
    assert result.principal_amount == Decimal("1304692.36")
    assert result.product_amount == Decimal("0")
    assert result.total_balance == Decimal("1304692.36")
    assert result.maturity_date == date(2026, 9, 1)


def test_missing_account_type_is_explicit_mapping_failure_not_nmd_inference() -> None:
    result = CaptacionesXMLNormalizer().normalize(_envelope(_record(TipoCuenta="")))

    assert isinstance(result, IRRBBSourceMappingFailure)
    assert result.canonical_field == "TipoCuenta"
    assert "required" in result.message.lower()


def test_negative_balance_fails_closed() -> None:
    result = CaptacionesXMLNormalizer().normalize(_envelope(_record(SaldoPrincipal="-1")))

    assert isinstance(result, IRRBBSourceMappingFailure)
    assert result.canonical_field == "principal/product"


class _Reader:
    def __init__(self, records: tuple[XMLConfiaRecord, ...]) -> None:
        self._records = records
        self.resolve_calls: list[tuple[str, date]] = []

    def resolve_source(self, *, key: str, cutoff_date: date) -> XMLConfiaResolvedSource:
        self.resolve_calls.append((key, cutoff_date))
        return XMLConfiaResolvedSource(
            key=key,
            path=SOURCE_PATH,
            header=XMLConfiaHeader(
                clase_dato="27",
                archivo="2702",
                periodo=date(2026, 8, 1),
                id_entidad="3004045138",
                tipo_carga="1",
                tipo_moneda="1",
            ),
        )

    def iter_records(self, source: XMLConfiaResolvedSource):
        assert source.path == SOURCE_PATH
        yield from self._records

    def sha256(self, path: Path, *, chunk_size: int = 1024 * 1024) -> str:
        assert path == SOURCE_PATH
        assert chunk_size == 1024 * 1024
        return SHA256


def test_monthly_bridge_preserves_fact_and_failure_lineage() -> None:
    reader = _Reader((_record("1"), _record("2", TipoCuenta="")))

    result = CaptacionesXMLMonthlyNormalizationBridge(source_reader=reader).normalize(
        cutoff_date=CUTOFF
    )

    assert reader.resolve_calls == [("CAPTACIONES", CUTOFF)]
    assert result.source_file_name == "Pasivos_Cuentas_Contables_210.xml"
    assert result.source_sha256 == SHA256
    assert result.source_record_count == 2
    assert len(result.normalized_facts) == 1
    assert len(result.mapping_failures) == 1
    assert result.normalized_facts[0].source_record_id.endswith(":record:1")
    assert result.mapping_failures[0].source_record_id.endswith(":record:2")
