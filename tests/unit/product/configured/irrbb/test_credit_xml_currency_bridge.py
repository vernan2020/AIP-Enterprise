from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.application.irrbb import (
    IRRBBSourceExclusion,
    IRRBBSourceMappingFailure,
    IRRBBSourceMappingFailureCode,
)
from aip.domain.irrbb.models import IRRBBTimeBucket
from aip.product.configured.irrbb.credit_xml_currency_bridge import CreditXMLCurrencyBridge
from aip.product.configured.irrbb.credit_xml_currency_catalog import (
    CreditXMLCurrencyCatalog,
    CreditXMLCurrencyCodeBinding,
)
from aip.product.configured.irrbb.credit_xml_irrbb_bucket_bridge import (
    CreditXMLIRRBBBucketBatchResult,
    CreditXMLIRRBBBucketFact,
)
from aip.shared.money import Currency

CUTOFF = date(2026, 8, 31)


def _fact(*, record_id: str, source_code: str) -> CreditXMLIRRBBBucketFact:
    return CreditXMLIRRBBBucketFact(
        source_record_id=f"XML_CONFIA:credit.xml:record:{record_id}",
        source_reference=f"XML_CONFIA:credit.xml|record={record_id}",
        operation_id=f"OP-{record_id}",
        currency_source_code=source_code,
        accounting_account_code="13131101",
        principal_amount=Decimal("1000.00"),
        product_amount=Decimal("10.00"),
        amount=Decimal("1010.00"),
        rate_indicator="F",
        source_rule_code="CREDIT_FIXED_MATURITY",
        risk_date=date(2026, 12, 15),
        bucket=IRRBBTimeBucket.MONTH_3_TO_6,
        ordinal=4,
        bucket_label="3 a 6 meses",
    )


def _catalog() -> CreditXMLCurrencyCatalog:
    return CreditXMLCurrencyCatalog(
        code="TEST-CREDIT-CURRENCY",
        version="1",
        evidence_reference="test-governed-evidence",
        bindings=(
            CreditXMLCurrencyCodeBinding(
                source_code="CRC_CODE",
                currency=Currency.CRC,
                evidence_reference="test-crc-binding",
            ),
            CreditXMLCurrencyCodeBinding(
                source_code="USD_CODE",
                currency=Currency.USD,
                evidence_reference="test-usd-binding",
            ),
        ),
    )


def test_governed_catalog_maps_bucket_fact_into_money_without_default_codes() -> None:
    batch = CreditXMLIRRBBBucketBatchResult(
        cutoff_date=CUTOFF,
        source_file_name="NEC2024_Operaciones_5103.xml",
        source_sha256="a" * 64,
        source_record_count=2,
        bucket_facts=(
            _fact(record_id="1", source_code="CRC_CODE"),
            _fact(record_id="2", source_code="USD_CODE"),
        ),
        source_exclusions=(),
        mapping_failures=(),
    )

    result = CreditXMLCurrencyBridge(catalog=_catalog()).map_batch(batch)

    assert result.mapping_failures == ()
    assert [item.currency for item in result.canonical_bucket_facts] == [
        Currency.CRC,
        Currency.USD,
    ]
    assert [item.amount.amount for item in result.canonical_bucket_facts] == [
        Decimal("1010.00"),
        Decimal("1010.00"),
    ]
    assert result.canonical_bucket_facts[0].principal.amount == Decimal("1000.00")
    assert result.canonical_bucket_facts[0].product.amount == Decimal("10.00")
    assert result.canonical_bucket_facts[0].bucket is IRRBBTimeBucket.MONTH_3_TO_6


def test_unmapped_source_code_fails_closed_instead_of_assuming_crc_or_usd() -> None:
    source = _fact(record_id="3", source_code="1")
    batch = CreditXMLIRRBBBucketBatchResult(
        cutoff_date=CUTOFF,
        source_file_name="NEC2024_Operaciones_5103.xml",
        source_sha256="a" * 64,
        source_record_count=1,
        bucket_facts=(source,),
        source_exclusions=(),
        mapping_failures=(),
    )

    result = CreditXMLCurrencyBridge(catalog=_catalog()).map_batch(batch)

    assert result.canonical_bucket_facts == ()
    assert len(result.mapping_failures) == 1
    failure = result.mapping_failures[0]
    assert failure.source_record_id == source.source_record_id
    assert failure.code is IRRBBSourceMappingFailureCode.UNSUPPORTED_SOURCE_VALUE
    assert failure.canonical_field == "currency"
    assert "'1'" in failure.message
    assert "TEST-CREDIT-CURRENCY:1" in failure.message


def test_existing_exclusions_and_failures_are_preserved_through_currency_boundary() -> None:
    exclusion = IRRBBSourceExclusion(
        source_record_id="excluded",
        source_reference="XML_CONFIA:credit.xml|record=excluded",
        reason_code="RULE",
        message="excluded",
        rule_reference="rule",
    )
    failure = IRRBBSourceMappingFailure(
        source_record_id="failed",
        source_reference="XML_CONFIA:credit.xml|record=failed",
        code=IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD,
        canonical_field="IRRBB risk_date",
        message="missing",
    )
    batch = CreditXMLIRRBBBucketBatchResult(
        cutoff_date=CUTOFF,
        source_file_name="NEC2024_Operaciones_5103.xml",
        source_sha256="a" * 64,
        source_record_count=3,
        bucket_facts=(_fact(record_id="4", source_code="CRC_CODE"),),
        source_exclusions=(exclusion,),
        mapping_failures=(failure,),
    )

    result = CreditXMLCurrencyBridge(catalog=_catalog()).map_batch(batch)

    assert len(result.canonical_bucket_facts) == 1
    assert result.source_exclusions == (exclusion,)
    assert result.mapping_failures == (failure,)
    assert result.source_record_count == 3
