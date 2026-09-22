from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.application.irrbb import (
    IRRBBSourceExclusion,
    IRRBBSourceMappingFailure,
    IRRBBSourceMappingFailureCode,
)
from aip.domain.irrbb.models import IRRBBTimeBucket
from aip.product.configured.irrbb.credit_xml_currency_bridge import (
    CreditXMLCanonicalBucketBatchResult,
    CreditXMLCanonicalBucketFact,
)
from aip.product.configured.irrbb.credit_xml_gap_readiness import (
    CreditXMLGapReadinessService,
    CreditXMLGapReadinessStatus,
)
from aip.shared.money import Currency, Money


def _fact(*, record_id: str, rate_indicator: str) -> CreditXMLCanonicalBucketFact:
    return CreditXMLCanonicalBucketFact(
        source_record_id=f"XML_CONFIA:credit.xml:record:{record_id}",
        source_reference=f"XML_CONFIA:credit.xml|record={record_id}",
        operation_id=f"OP-{record_id}",
        accounting_account_code="13131101",
        amount=Money(Decimal("1010.00"), Currency.CRC),
        rate_indicator=rate_indicator,
        source_rule_code="RULE",
        risk_date=date(2026, 12, 15),
        bucket=IRRBBTimeBucket.MONTH_3_TO_6,
        ordinal=4,
        bucket_label="3 a 6 meses",
    )


def test_fixed_credit_is_blocked_until_contractual_payment_schedule_exists() -> None:
    assessment = CreditXMLGapReadinessService.assess_fact(_fact(record_id="1", rate_indicator="F"))

    assert assessment.status is CreditXMLGapReadinessStatus.BLOCKED_CONTRACTUAL_SCHEDULE
    assert assessment.missing_capabilities == (
        "CONTRACTUAL_PAYMENT_SCHEDULE",
        "PAYMENT_AMOUNT_BY_DATE",
    )
    assert "cannot be collapsed to one maturity bucket" in assessment.message


def test_semivariable_credit_requires_schedule_and_residual_principal_at_repricing() -> None:
    assessment = CreditXMLGapReadinessService.assess_fact(_fact(record_id="2", rate_indicator="FV"))

    assert assessment.status is CreditXMLGapReadinessStatus.BLOCKED_CONTRACTUAL_SCHEDULE
    assert assessment.missing_capabilities == (
        "CONTRACTUAL_PAYMENT_SCHEDULE_THROUGH_REPRICING",
        "OUTSTANDING_PRINCIPAL_AT_REPRICING_OR_PRINCIPAL_COMPONENTS",
    )
    assert "must not be inferred" in assessment.message


def test_batch_preserves_exclusions_and_mapping_failures_without_fabricating_gap_rows() -> None:
    exclusion = IRRBBSourceExclusion(
        source_record_id="excluded",
        source_reference="XML_CONFIA:credit.xml|record=excluded",
        reason_code="CREDIT_MORA_EXCLUDE",
        message="excluded",
        rule_reference="rule",
    )
    failure = IRRBBSourceMappingFailure(
        source_record_id="failed",
        source_reference="XML_CONFIA:credit.xml|record=failed",
        code=IRRBBSourceMappingFailureCode.UNSUPPORTED_SOURCE_VALUE,
        canonical_field="currency",
        message="unmapped",
    )
    batch = CreditXMLCanonicalBucketBatchResult(
        source_record_count=3,
        canonical_bucket_facts=(_fact(record_id="3", rate_indicator="F"),),
        source_exclusions=(exclusion,),
        mapping_failures=(failure,),
    )

    result = CreditXMLGapReadinessService.assess_batch(batch)

    assert len(result.assessments) == 1
    assert result.source_exclusions == (exclusion,)
    assert result.mapping_failures == (failure,)
    assert result.source_record_count == 3
