from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from aip.product.configured.irrbb.credit_xml_batch_bridge import (
    CreditXMLMonthlyNormalizationBridge,
)
from aip.product.configured.irrbb.credit_xml_rate_risk_normalizer import (
    CREDIT_XML_RULE_MORA_EXCLUDE,
    CREDIT_XML_RULE_VARIABLE_R1,
)
from aip.product.configured.irrbb.xml_confia_source import (
    XMLConfiaHeader,
    XMLConfiaRecord,
    XMLConfiaResolvedSource,
)

CUTOFF = date(2026, 8, 31)
SOURCE_PATH = Path(r"C:\Institutional\XML CONFÍA\2026\08-AGOSTO\NEC2024_Operaciones_5103.xml")
SHA256 = "a" * 64


def _record(
    record_id: str,
    **overrides: str,
) -> XMLConfiaRecord:
    values = {
        "IdOperacionCredito": f"OP-{record_id}",
        "DiasMaximaMorosidad": "0",
        "TipoMonedaOperacion": "1",
        "CuentaContablePrincipal": "13131101",
        "SaldoPrincipalOperacionCrediticia": "1000.00",
        "CuentaContableProductosPorCobrar": "13831101",
        "SaldoProductosPorCobrar": "10.00",
        "FechaFormalizacion": "10/10/2017",
        "FechaVencimiento": "10/10/2029",
        "TasaInteresNominalVigente": "17.50",
        "IndicadorTipoTasa": "V",
        "FechaProximoPagoIntereses": "10/09/2026",
        "FechaCambioTipoTasa": "",
        "TipoFrecuenciaAjusteTasaInteresVariable": "4",
    }
    values.update(overrides)
    return XMLConfiaRecord(record_id=record_id, action="insertar", values=values)


class _Reader:
    def __init__(self, records: tuple[XMLConfiaRecord, ...]) -> None:
        self._records = records
        self.resolve_calls: list[tuple[str, date]] = []
        self.sha_calls: list[Path] = []

    def resolve_source(self, *, key: str, cutoff_date: date) -> XMLConfiaResolvedSource:
        self.resolve_calls.append((key, cutoff_date))
        return XMLConfiaResolvedSource(
            key=key,
            path=SOURCE_PATH,
            header=XMLConfiaHeader(
                clase_dato="1",
                archivo="5103",
                periodo=CUTOFF,
                id_entidad="5103",
                tipo_carga="1",
                tipo_moneda="1",
            ),
        )

    def iter_records(self, source: XMLConfiaResolvedSource):
        assert source.path == SOURCE_PATH
        yield from self._records

    def sha256(self, path: Path, *, chunk_size: int = 1024 * 1024) -> str:
        assert chunk_size == 1024 * 1024
        self.sha_calls.append(path)
        return SHA256


def test_monthly_bridge_preserves_every_record_as_fact_exclusion_or_failure() -> None:
    reader = _Reader(
        (
            _record("1"),
            _record("2", DiasMaximaMorosidad="45"),
            _record("3", IndicadorTipoTasa="FV", FechaCambioTipoTasa=""),
        )
    )

    result = CreditXMLMonthlyNormalizationBridge(source_reader=reader).normalize(cutoff_date=CUTOFF)

    assert reader.resolve_calls == [("CREDIT", CUTOFF)]
    assert reader.sha_calls == [SOURCE_PATH]
    assert result.source_record_count == 3
    assert result.source_file_name == "NEC2024_Operaciones_5103.xml"
    assert result.source_sha256 == SHA256
    assert len(result.normalized_facts) == 1
    assert len(result.source_exclusions) == 1
    assert len(result.mapping_failures) == 1

    fact = result.normalized_facts[0]
    assert fact.rule_code == CREDIT_XML_RULE_VARIABLE_R1
    assert fact.source_record_id.endswith(":record:1")
    assert fact.source_reference == "XML_CONFIA:NEC2024_Operaciones_5103.xml|record=1"
    assert "Institutional" not in fact.source_reference

    exclusion = result.source_exclusions[0]
    assert exclusion.reason_code == CREDIT_XML_RULE_MORA_EXCLUDE
    assert exclusion.source_record_id.endswith(":record:2")

    failure = result.mapping_failures[0]
    assert failure.source_record_id.endswith(":record:3")
    assert failure.canonical_field == "FechaCambioTipoTasa"


def test_empty_credit_xml_batch_is_explicitly_empty() -> None:
    result = CreditXMLMonthlyNormalizationBridge(source_reader=_Reader(())).normalize(
        cutoff_date=CUTOFF
    )

    assert result.source_record_count == 0
    assert result.normalized_facts == ()
    assert result.source_exclusions == ()
    assert result.mapping_failures == ()


def test_bridge_rejects_duplicate_xml_registro_lineage() -> None:
    reader = _Reader((_record("7"), _record("7")))

    with pytest.raises(ValueError, match="lineage must be unique"):
        CreditXMLMonthlyNormalizationBridge(source_reader=reader).normalize(cutoff_date=CUTOFF)


def test_bridge_rejects_blank_xml_registro_id() -> None:
    reader = _Reader((_record(" "),))

    with pytest.raises(ValueError, match="Registro id is required"):
        CreditXMLMonthlyNormalizationBridge(source_reader=reader).normalize(cutoff_date=CUTOFF)
