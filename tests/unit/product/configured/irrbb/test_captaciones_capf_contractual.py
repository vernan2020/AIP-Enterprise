from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from aip.application.irrbb import (
    IRRBBSourceMappingFailure,
    IRRBBSourceMappingFailureCode,
)
from aip.domain.irrbb.models import RateType
from aip.product.configured.irrbb.captaciones_capf_contractual import (
    INSTITUTIONAL_CAPF_PRODUCT_POLICY,
    CaptacionesCAPFContractualFact,
    CaptacionesCAPFContractualNormalizer,
)


def _row(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "Número Certificado": "CERT-346-1",
        "Estado": "A",
        "Tipo de Certificado": "346 - CAP GANO MÁS",
        "Moneda": "Colones",
        "Monto Certificado Colonizado": Decimal("1000000.00"),
        " Saldo Interes Col. ": Decimal("10000.00"),
        "Tasa Interés": Decimal("7.25"),
        "Tasa Preferencial": Decimal("0.25"),
        "Plazo Meses": 12,
        "Fecha Emisión": datetime(2026, 1, 31, 0, 0),
        "Fecha Vencimiento": datetime(2027, 1, 31, 0, 0),
        "Fecha Pago": "",
        "Frecuencia Pago Intereses": "TRIMESTRAL",
        "Indica Renovación": "S",
        " Monto Renovación ": Decimal("1000000.00"),
    }
    values.update(overrides)
    return values


def _normalize(values: dict[str, object]):
    return CaptacionesCAPFContractualNormalizer(
        product_policy=INSTITUTIONAL_CAPF_PRODUCT_POLICY
    ).normalize(
        source_record_id="CAPF_XLSX:source.xlsx:row:2",
        source_reference="CAPF_XLSX:source.xlsx|sha256=abc|row=2",
        values=values,
    )


def test_product_346_capitalizes_at_the_source_interest_payment_frequency() -> None:
    result = _normalize(_row())

    assert isinstance(result, CaptacionesCAPFContractualFact)
    assert result.product_code == "346"
    assert result.capitalizes_at_interest_payment_frequency is True
    assert result.capitalization_frequency_source_label == "TRIMESTRAL"
    assert result.product_rule_reference is not None
    assert "product=346" in result.product_rule_reference


def test_all_capf_records_use_the_governed_fixed_rate_rule() -> None:
    product_346 = _normalize(_row())
    product_434 = _normalize(
        _row(
            **{
                "Número Certificado": "CERT-434-1",
                "Tipo de Certificado": "434 - GANO MÁS PLUS COLONES",
            }
        )
    )

    assert isinstance(product_346, CaptacionesCAPFContractualFact)
    assert isinstance(product_434, CaptacionesCAPFContractualFact)
    assert product_346.contractual_rate_type is RateType.FIXED
    assert product_434.contractual_rate_type is RateType.FIXED
    assert "ALL-CAP-FIXED-RATE" in product_346.rate_type_rule_reference


def test_missing_payment_date_remains_none_and_does_not_create_a_schedule() -> None:
    result = _normalize(_row())

    assert isinstance(result, CaptacionesCAPFContractualFact)
    assert result.explicit_payment_date is None
    assert result.issue_date == date(2026, 1, 31)
    assert result.maturity_date == date(2027, 1, 31)


def test_non_346_product_is_not_inferred_to_be_capitalizable() -> None:
    result = _normalize(
        _row(
            **{
                "Número Certificado": "CERT-434-1",
                "Tipo de Certificado": "434 - GANO MÁS PLUS COLONES",
                "Frecuencia Pago Intereses": "MENSUAL",
            }
        )
    )

    assert isinstance(result, CaptacionesCAPFContractualFact)
    assert result.capitalizes_at_interest_payment_frequency is False
    assert result.capitalization_frequency_source_label is None
    assert result.product_rule_reference is None


def test_currency_label_and_colonized_amount_do_not_cross_the_canonical_money_boundary() -> None:
    result = _normalize(
        _row(
            **{
                "Moneda": "Dólares",
                "Monto Certificado Colonizado": Decimal("530000.00"),
            }
        )
    )

    assert isinstance(result, CaptacionesCAPFContractualFact)
    assert result.currency_source_label == "Dólares"
    assert result.certificate_amount_colonized == Decimal("530000.00")
    assert not hasattr(result, "currency")
    assert not hasattr(result, "principal")


def test_production_batch_rejects_csv_even_when_used_as_schema_evidence() -> None:
    with pytest.raises(ValueError, match="must be an XLSX workbook"):
        CaptacionesCAPFContractualNormalizer.normalize_batch(
            cutoff_date=date(2026, 6, 30),
            source_file_name="evidence.csv",
            source_sha256="a" * 64,
            rows=(_row(),),
            product_policy=INSTITUTIONAL_CAPF_PRODUCT_POLICY,
        )


def test_batch_rejects_every_row_of_a_duplicate_certificate_group() -> None:
    result = CaptacionesCAPFContractualNormalizer.normalize_batch(
        cutoff_date=date(2026, 6, 30),
        source_file_name="Detalle_Ahorro_Plazo_Fijo_Junio_2026.xlsx",
        source_sha256="a" * 64,
        rows=(_row(), _row()),
        product_policy=INSTITUTIONAL_CAPF_PRODUCT_POLICY,
    )

    assert result.source_record_count == 2
    assert not result.normalized_facts
    assert len(result.mapping_failures) == 2
    assert all(
        failure.code is IRRBBSourceMappingFailureCode.SOURCE_RECORD_REJECTED
        for failure in result.mapping_failures
    )
    assert all(
        failure.canonical_field == "certificate_number" for failure in result.mapping_failures
    )


def test_whitespace_bearing_production_headers_are_governed_aliases() -> None:
    result = _normalize(_row())

    assert isinstance(result, CaptacionesCAPFContractualFact)
    assert result.renewal_amount_source_value == Decimal("1000000.00")


def test_missing_product_346_frequency_is_an_explicit_mapping_failure() -> None:
    result = _normalize(_row(**{"Frecuencia Pago Intereses": ""}))

    assert isinstance(result, IRRBBSourceMappingFailure)
    assert result.code is IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD
    assert result.canonical_field == "Frecuencia Pago Intereses"


def test_batch_preserves_one_outcome_per_physical_workbook_row() -> None:
    result = CaptacionesCAPFContractualNormalizer.normalize_batch(
        cutoff_date=date(2026, 6, 30),
        source_file_name="Detalle_Ahorro_Plazo_Fijo_Junio_2026.xlsx",
        source_sha256="b" * 64,
        rows=(
            _row(),
            _row(
                **{
                    "Número Certificado": "CERT-434-2",
                    "Tipo de Certificado": "434 - GANO MÁS PLUS COLONES",
                }
            ),
            _row(**{"Número Certificado": "", "Tipo de Certificado": "233 - D"}),
        ),
        product_policy=INSTITUTIONAL_CAPF_PRODUCT_POLICY,
    )

    assert result.source_record_count == 3
    assert len(result.normalized_facts) == 2
    assert len(result.mapping_failures) == 1
    assert result.mapping_failures[0].canonical_field == "Número Certificado"
