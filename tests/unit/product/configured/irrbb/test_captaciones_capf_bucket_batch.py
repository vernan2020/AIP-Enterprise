from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from aip.application.irrbb import IRRBBSourceMappingFailure, IRRBBSourceMappingFailureCode
from aip.domain.irrbb.models import IRRBBTimeBucket, RateType
from aip.product.configured.irrbb.captaciones_capf_bucket_batch import (
    CaptacionesCAPFPrincipalBucketBatchBridge,
)
from aip.product.configured.irrbb.captaciones_capf_contractual import (
    CaptacionesCAPFContractualFact,
)
from aip.product.configured.irrbb.captaciones_capf_operation_binding import (
    CaptacionesCAPFJoinedFact,
    CaptacionesCAPFOperationJoinService,
)
from aip.product.configured.irrbb.captaciones_xml_currency_bridge import (
    CaptacionesXMLCanonicalCurrencyFact,
)
from aip.shared.money import Currency, Money


def _xml_fact(record: int, operation: str, principal: str) -> CaptacionesXMLCanonicalCurrencyFact:
    return CaptacionesXMLCanonicalCurrencyFact(
        source_record_id=f"XML_CONFIA:Pasivos_210.xml:record:{record}",
        source_reference=f"XML_CONFIA:Pasivos_210.xml|record={record}",
        creditor_id=f"ACR-{record}",
        operation_id=operation,
        operation_type_source_code="1",
        guarantee_indicator="N",
        account_type_source_code="4",
        rate_type_source_code="F",
        variable_rate_source_code=None,
        nominal_rate_percent=Decimal("7.25"),
        sugef_catalog_source_code="14",
        accounting_account_code="21312100",
        principal=Money(Decimal(principal), Currency.CRC),
        product_account_code="21900100",
        product=Money(Decimal("100"), Currency.CRC),
        amount=Money(Decimal(principal) + Decimal("100"), Currency.CRC),
        origination_date=date(2026, 1, 31),
        maturity_date=None,
        reserve_requirement_indicator="S",
        deposit_fgd_source_code="1",
    )


def _contract(operation: str, maturity: date) -> CaptacionesCAPFContractualFact:
    return CaptacionesCAPFContractualFact(
        source_record_id=f"CAPF_XLSX:detalle.xlsx:row:{operation}",
        source_reference=f"CAPF_XLSX:detalle.xlsx|sha256=abc|row={operation}",
        certificate_number=operation,
        source_status_code="A",
        product_code="346",
        product_name="CAP GANO MÁS",
        currency_source_label="Colones",
        certificate_amount_colonized=Decimal("999999999"),
        interest_rate_percent=Decimal("7.25"),
        contractual_rate_type=RateType.FIXED,
        rate_type_rule_reference="TEST:ALL-CAP-FIXED-RATE",
        preferential_rate_percent=None,
        term_months=12,
        issue_date=date(2026, 1, 31),
        maturity_date=maturity,
        explicit_payment_date=None,
        interest_payment_frequency_source_label="TRIMESTRAL",
        renewal_indicator_source_code="N",
        renewal_amount_source_value=None,
        capitalizes_at_interest_payment_frequency=True,
        capitalization_frequency_source_label="TRIMESTRAL",
        product_rule_reference="TEST:product=346",
    )


def _joined(
    record: int,
    operation: str,
    principal: str,
    maturity: date,
) -> CaptacionesCAPFJoinedFact:
    xml = _xml_fact(record, operation, principal)
    service = CaptacionesCAPFOperationJoinService()
    result = service.join(
        xml_fact=xml,
        contractual_facts_by_certificate=service.index_contractual_facts(
            (_contract(operation, maturity),)
        ),
    )
    assert isinstance(result, CaptacionesCAPFJoinedFact)
    return result


def test_batch_aggregates_xml_principal_by_currency_and_canonical_bucket() -> None:
    cutoff = date(2026, 6, 30)
    result = CaptacionesCAPFPrincipalBucketBatchBridge().build(
        cutoff_date=cutoff,
        joined_facts=(
            _joined(1, "CAP-1", "1000", date(2026, 7, 30)),
            _joined(2, "CAP-2", "2500", date(2026, 7, 15)),
            _joined(3, "CAP-3", "7000", date(2026, 10, 1)),
        ),
    )

    assert result.source_record_count == 3
    assert len(result.bucket_facts) == 3
    assert not result.mapping_failures
    assert not result.eve_ready
    observed = [
        (item.bucket, item.principal.amount, item.record_count)
        for item in result.bucket_totals
    ]
    assert observed == [
        (IRRBBTimeBucket.DAY_1_TO_MONTH_1, Decimal("3500"), 2),
        (IRRBBTimeBucket.MONTH_3_TO_6, Decimal("7000"), 1),
    ]
    assert all(not item.eve_ready for item in result.bucket_totals)


def test_batch_preserves_inherited_and_new_failures_without_zero_fill() -> None:
    joined = _joined(1, "CAP-1", "1000", date(2026, 7, 30))
    inherited = IRRBBSourceMappingFailure(
        source_record_id="XML_CONFIA:Pasivos_210.xml:record:2",
        source_reference="XML_CONFIA:Pasivos_210.xml|record=2",
        code=IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD,
        canonical_field="capf_contractual_record",
        message="No exact Número Certificado = IdOperacion match.",
    )
    matured = replace(
        joined,
        xml_fact=replace(
            joined.xml_fact,
            source_record_id="XML_CONFIA:Pasivos_210.xml:record:3",
            source_reference="XML_CONFIA:Pasivos_210.xml|record=3",
            operation_id="CAP-3",
        ),
        contractual_fact=replace(
            joined.contractual_fact,
            source_record_id="CAPF_XLSX:detalle.xlsx:row:CAP-3",
            source_reference="CAPF_XLSX:detalle.xlsx|sha256=abc|row=CAP-3",
            certificate_number="CAP-3",
            maturity_date=date(2026, 5, 31),
        ),
        binding_reference="TEST|operation=CAP-3|certificate=CAP-3",
        risk_date=date(2026, 5, 31),
    )

    result = CaptacionesCAPFPrincipalBucketBatchBridge().build(
        cutoff_date=date(2026, 6, 30),
        joined_facts=(joined, matured),
        inherited_mapping_failures=(inherited,),
    )

    assert result.source_record_count == 3
    assert len(result.bucket_facts) == 1
    assert len(result.mapping_failures) == 2
    assert {item.source_record_id for item in result.mapping_failures} == {
        "XML_CONFIA:Pasivos_210.xml:record:2",
        "XML_CONFIA:Pasivos_210.xml:record:3",
    }
    assert result.bucket_totals[0].principal.amount == Decimal("1000")
    assert all(item.principal.amount != 0 for item in result.bucket_totals)


def test_batch_rejects_duplicate_xml_lineage_across_outcomes() -> None:
    joined = _joined(1, "CAP-1", "1000", date(2026, 7, 30))
    duplicate = IRRBBSourceMappingFailure(
        source_record_id=joined.xml_fact.source_record_id,
        source_reference=joined.xml_fact.source_reference,
        code=IRRBBSourceMappingFailureCode.SOURCE_RECORD_REJECTED,
        canonical_field="capf_contractual_record",
        message="Duplicate test outcome.",
    )

    try:
        CaptacionesCAPFPrincipalBucketBatchBridge().build(
            cutoff_date=date(2026, 6, 30),
            joined_facts=(joined,),
            inherited_mapping_failures=(duplicate,),
        )
    except ValueError as exc:
        assert "unique XML source_record_id" in str(exc)
    else:
        raise AssertionError("duplicate source lineage must fail closed")
