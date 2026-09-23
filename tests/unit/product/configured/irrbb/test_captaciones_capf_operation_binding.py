from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from aip.application.irrbb import IRRBBSourceMappingFailure, IRRBBSourceMappingFailureCode
from aip.domain.irrbb.models import RateType
from aip.product.configured.irrbb.captaciones_capf_contractual import CaptacionesCAPFContractualFact
from aip.product.configured.irrbb.captaciones_capf_operation_binding import (
    CAPF_CERTIFICATE_OPERATION_RULE_REFERENCE,
    CaptacionesCAPFJoinedFact,
    CaptacionesCAPFOperationJoinService,
)
from aip.product.configured.irrbb.captaciones_xml_currency_bridge import (
    CaptacionesXMLCanonicalCurrencyFact,
)
from aip.shared.money import Currency, Money


def _xml_fact(
    *,
    operation_id: str = "CERT-346-1",
    rate_type: str = "F",
    maturity_date: date | None = date(2027, 1, 31),
) -> CaptacionesXMLCanonicalCurrencyFact:
    return CaptacionesXMLCanonicalCurrencyFact(
        source_record_id="XML_CONFIA:Pasivos_210.xml:record:1",
        source_reference="XML_CONFIA:Pasivos_210.xml|record=1",
        creditor_id="ACR-1",
        operation_id=operation_id,
        operation_type_source_code="1",
        guarantee_indicator="N",
        account_type_source_code="4",
        rate_type_source_code=rate_type,
        variable_rate_source_code=None,
        nominal_rate_percent=Decimal("7.25"),
        sugef_catalog_source_code="14",
        accounting_account_code="21312100",
        principal=Money(Decimal("1000000"), Currency.CRC),
        product_account_code="21900100",
        product=Money(Decimal("10000"), Currency.CRC),
        amount=Money(Decimal("1010000"), Currency.CRC),
        origination_date=date(2026, 1, 31),
        maturity_date=maturity_date,
        reserve_requirement_indicator="S",
        deposit_fgd_source_code="1",
    )


def _contractual_fact(
    *,
    certificate_number: str = "CERT-346-1",
    maturity_date: date = date(2027, 1, 31),
    rate_type: RateType = RateType.FIXED,
) -> CaptacionesCAPFContractualFact:
    return CaptacionesCAPFContractualFact(
        source_record_id="CAPF_XLSX:detalle.xlsx:row:2",
        source_reference="CAPF_XLSX:detalle.xlsx|sha256=abc|row=2",
        certificate_number=certificate_number,
        source_status_code="A",
        product_code="346",
        product_name="CAP GANO MÁS",
        currency_source_label="Colones",
        certificate_amount_colonized=Decimal("999999999"),
        interest_rate_percent=Decimal("7.25"),
        contractual_rate_type=rate_type,
        rate_type_rule_reference="TEST:ALL-CAP-FIXED-RATE",
        preferential_rate_percent=Decimal("0.25"),
        term_months=12,
        issue_date=date(2026, 1, 31),
        maturity_date=maturity_date,
        explicit_payment_date=None,
        interest_payment_frequency_source_label="TRIMESTRAL",
        renewal_indicator_source_code="S",
        renewal_amount_source_value=Decimal("1000000"),
        capitalizes_at_interest_payment_frequency=True,
        capitalization_frequency_source_label="TRIMESTRAL",
        product_rule_reference="TEST:product=346",
    )


def _join(
    xml_fact: CaptacionesXMLCanonicalCurrencyFact,
    facts: tuple[CaptacionesCAPFContractualFact, ...],
):
    service = CaptacionesCAPFOperationJoinService()
    return service.join(
        xml_fact=xml_fact,
        contractual_facts_by_certificate=service.index_contractual_facts(facts),
    )


def test_governed_join_preserves_xml_principal_and_contractual_maturity() -> None:
    result = _join(_xml_fact(), (_contractual_fact(),))

    assert isinstance(result, CaptacionesCAPFJoinedFact)
    assert result.operation_id == "CERT-346-1"
    assert result.certificate_number == "CERT-346-1"
    assert result.principal == Money(Decimal("1000000"), Currency.CRC)
    assert result.principal.amount != result.contractual_fact.certificate_amount_colonized
    assert result.currency is Currency.CRC
    assert result.risk_date == date(2027, 1, 31)
    assert result.contractual_rate_type is RateType.FIXED
    assert "operation=CERT-346-1" in result.binding_reference
    assert "certificate=CERT-346-1" in result.binding_reference


def test_documented_identity_join_needs_no_per_certificate_catalog() -> None:
    result = _join(_xml_fact(), (_contractual_fact(),))
    assert isinstance(result, CaptacionesCAPFJoinedFact)
    assert CAPF_CERTIFICATE_OPERATION_RULE_REFERENCE in result.binding_reference
    assert result.xml_fact.source_reference.startswith("XML_CONFIA:")
    assert result.contractual_fact.source_reference.startswith("CAPF_XLSX:")


@pytest.mark.parametrize("operation_id", ["000123", "123.0", "abc"])
def test_identifiers_are_not_numerically_or_case_normalized(operation_id: str) -> None:
    result = _join(
        _xml_fact(operation_id=operation_id),
        (_contractual_fact(certificate_number="123"), _contractual_fact(certificate_number="ABC")),
    )
    assert isinstance(result, IRRBBSourceMappingFailure)
    assert result.canonical_field == "capf_contractual_record"


@pytest.mark.parametrize("key", [" CERT-346-1", "CERT-346-1 "])
def test_invalid_xml_identity_is_a_mapping_failure(key: str) -> None:
    result = _join(_xml_fact(operation_id=key), (_contractual_fact(),))
    assert isinstance(result, IRRBBSourceMappingFailure)
    assert result.canonical_field == "operation_id"


@pytest.mark.parametrize("key", ["", " "])
def test_empty_xml_identity_is_rejected_before_join(key: str) -> None:
    with pytest.raises(ValueError, match="operation_id is required"):
        _xml_fact(operation_id=key)


@pytest.mark.parametrize("key", ["", " ", " CERT-346-1", "CERT-346-1 "])
def test_contractual_index_rejects_invalid_identity(key: str) -> None:
    with pytest.raises(ValueError, match="nonempty canonical text|certificate_number is required"):
        CaptacionesCAPFOperationJoinService.index_contractual_facts(
            (_contractual_fact(certificate_number=key),)
        )


def test_substituted_index_record_is_rejected() -> None:
    result = CaptacionesCAPFOperationJoinService().join(
        xml_fact=_xml_fact(),
        contractual_facts_by_certificate={
            "CERT-346-1": _contractual_fact(certificate_number="OTHER")
        },
    )
    assert isinstance(result, IRRBBSourceMappingFailure)
    assert result.canonical_field == "certificate_number"


def test_binding_to_absent_contractual_certificate_fails_closed() -> None:
    result = _join(_xml_fact(), ())

    assert isinstance(result, IRRBBSourceMappingFailure)
    assert result.canonical_field == "capf_contractual_record"


def test_conflicting_maturity_dates_are_rejected_without_selecting_one() -> None:
    result = _join(
        _xml_fact(maturity_date=date(2027, 2, 1)),
        (_contractual_fact(maturity_date=date(2027, 1, 31)),),
    )

    assert isinstance(result, IRRBBSourceMappingFailure)
    assert result.code is IRRBBSourceMappingFailureCode.SOURCE_RECORD_REJECTED
    assert result.canonical_field == "maturity_date"
    assert "neither date was selected" in result.message


def test_missing_xml_maturity_accepts_the_explicit_contractual_maturity() -> None:
    result = _join(_xml_fact(maturity_date=None), (_contractual_fact(),))

    assert isinstance(result, CaptacionesCAPFJoinedFact)
    assert result.risk_date == date(2027, 1, 31)


def test_non_fixed_xml_rate_type_conflicts_with_governed_capf_rule() -> None:
    result = _join(_xml_fact(rate_type="V"), (_contractual_fact(),))

    assert isinstance(result, IRRBBSourceMappingFailure)
    assert result.code is IRRBBSourceMappingFailureCode.SOURCE_RECORD_REJECTED
    assert result.canonical_field == "rate_type"


def test_contractual_index_rejects_duplicate_certificate_identity() -> None:
    with pytest.raises(ValueError, match="certificate numbers must be unique"):
        CaptacionesCAPFOperationJoinService.index_contractual_facts(
            (_contractual_fact(), _contractual_fact())
        )
