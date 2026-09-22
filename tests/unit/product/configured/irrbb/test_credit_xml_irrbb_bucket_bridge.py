from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.application.irrbb import (
    IRRBBSourceExclusion,
    IRRBBSourceMappingFailure,
    IRRBBSourceMappingFailureCode,
)
from aip.domain.irrbb.models import IRRBBTimeBucket
from aip.product.configured.irrbb.credit_xml_batch_bridge import (
    CreditXMLNormalizationBatchResult,
)
from aip.product.configured.irrbb.credit_xml_irrbb_bucket_bridge import (
    CreditXMLMonthlyIRRBBBucketBridge,
)
from aip.product.configured.irrbb.credit_xml_rate_risk_normalizer import (
    CREDIT_XML_RULE_FIXED_MATURITY,
    CREDIT_XML_RULE_FV_CHANGE_DATE,
    CREDIT_XML_RULE_VARIABLE_R1,
    CreditXMLRateRiskFact,
)

CUTOFF = date(2026, 8, 31)
SHA256 = "a" * 64


def _fact(
    *,
    record_id: str,
    rate_indicator: str,
    rule_code: str,
    sensitive_date: date | None,
) -> CreditXMLRateRiskFact:
    return CreditXMLRateRiskFact(
        source_record_id=f"XML_CONFIA:credit.xml:record:{record_id}",
        source_reference=f"XML_CONFIA:credit.xml|record={record_id}",
        operation_id=f"OP-{record_id}",
        currency_source_code="1",
        accounting_account_code="13131101",
        principal_amount=Decimal("1000.00"),
        product_amount=Decimal("10.00"),
        days_past_due=0,
        rate_indicator=rate_indicator,
        nominal_rate_percent=Decimal("17.50"),
        origination_date=date(2020, 1, 1),
        maturity_date=date(2029, 10, 10),
        next_interest_payment_date=date(2026, 9, 10),
        rate_change_date=sensitive_date if rate_indicator == "FV" else None,
        repricing_frequency_source_code="4" if rate_indicator == "V" else None,
        rule_code=rule_code,
        sensitive_date=sensitive_date,
        sicveca_bucket_hint=1 if rate_indicator == "V" else None,
    )


class _NormalizationBridge:
    def __init__(self, result: CreditXMLNormalizationBatchResult) -> None:
        self._result = result
        self.calls: list[date] = []

    def normalize(self, *, cutoff_date: date) -> CreditXMLNormalizationBatchResult:
        self.calls.append(cutoff_date)
        return self._result


def _batch(
    *facts: CreditXMLRateRiskFact,
    exclusions: tuple[IRRBBSourceExclusion, ...] = (),
    failures: tuple[IRRBBSourceMappingFailure, ...] = (),
) -> CreditXMLNormalizationBatchResult:
    return CreditXMLNormalizationBatchResult(
        cutoff_date=CUTOFF,
        source_file_name="NEC2024_Operaciones_5103.xml",
        source_sha256=SHA256,
        source_record_count=len(facts) + len(exclusions) + len(failures),
        normalized_facts=tuple(facts),
        source_exclusions=exclusions,
        mapping_failures=failures,
    )


def test_fixed_credit_uses_exact_maturity_date_in_canonical_19_bucket_service() -> None:
    bridge = _NormalizationBridge(
        _batch(
            _fact(
                record_id="1",
                rate_indicator="F",
                rule_code=CREDIT_XML_RULE_FIXED_MATURITY,
                sensitive_date=date(2026, 12, 15),
            )
        )
    )

    result = CreditXMLMonthlyIRRBBBucketBridge(normalization_bridge=bridge).build(
        cutoff_date=CUTOFF
    )

    assert bridge.calls == [CUTOFF]
    assert result.source_record_count == 1
    assert result.mapping_failures == ()
    assert len(result.bucket_facts) == 1

    fact = result.bucket_facts[0]
    assert fact.risk_date == date(2026, 12, 15)
    assert fact.bucket is IRRBBTimeBucket.MONTH_3_TO_6
    assert fact.ordinal == 4
    assert fact.amount == Decimal("1010.00")
    assert fact.currency_source_code == "1"
    assert fact.source_rule_code == CREDIT_XML_RULE_FIXED_MATURITY


def test_fv_credit_uses_exact_change_date_without_sicveca_range_translation() -> None:
    result = CreditXMLMonthlyIRRBBBucketBridge(
        normalization_bridge=_NormalizationBridge(
            _batch(
                _fact(
                    record_id="2",
                    rate_indicator="FV",
                    rule_code=CREDIT_XML_RULE_FV_CHANGE_DATE,
                    sensitive_date=date(2026, 11, 15),
                )
            )
        )
    ).build(cutoff_date=CUTOFF)

    fact = result.bucket_facts[0]
    assert fact.bucket is IRRBBTimeBucket.MONTH_1_TO_3
    assert fact.ordinal == 3
    assert fact.risk_date == date(2026, 11, 15)


def test_variable_credit_with_only_r1_hint_is_blocked_instead_of_receiving_fake_date() -> None:
    source_fact = _fact(
        record_id="3",
        rate_indicator="V",
        rule_code=CREDIT_XML_RULE_VARIABLE_R1,
        sensitive_date=None,
    )

    result = CreditXMLMonthlyIRRBBBucketBridge(
        normalization_bridge=_NormalizationBridge(_batch(source_fact))
    ).build(cutoff_date=CUTOFF)

    assert result.bucket_facts == ()
    assert len(result.mapping_failures) == 1

    failure = result.mapping_failures[0]
    assert failure.source_record_id == source_fact.source_record_id
    assert failure.code is IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD
    assert failure.canonical_field == "IRRBB risk_date"
    assert "R1-R6 bucket hints are audit-only" in failure.message
    assert "exact repricing/risk date" in failure.message


def test_existing_exclusions_and_mapping_failures_are_preserved_with_lineage() -> None:
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
        canonical_field="IndicadorTipoTasa",
        message="unsupported",
    )

    result = CreditXMLMonthlyIRRBBBucketBridge(
        normalization_bridge=_NormalizationBridge(
            _batch(
                _fact(
                    record_id="4",
                    rate_indicator="F",
                    rule_code=CREDIT_XML_RULE_FIXED_MATURITY,
                    sensitive_date=date(2027, 8, 31),
                ),
                exclusions=(exclusion,),
                failures=(failure,),
            )
        )
    ).build(cutoff_date=CUTOFF)

    assert len(result.bucket_facts) == 1
    assert result.source_exclusions == (exclusion,)
    assert result.mapping_failures == (failure,)
    assert result.source_record_count == 3


def test_variable_blocker_keeps_every_physical_record_represented_once() -> None:
    result = CreditXMLMonthlyIRRBBBucketBridge(
        normalization_bridge=_NormalizationBridge(
            _batch(
                _fact(
                    record_id="5",
                    rate_indicator="V",
                    rule_code=CREDIT_XML_RULE_VARIABLE_R1,
                    sensitive_date=None,
                ),
                _fact(
                    record_id="6",
                    rate_indicator="F",
                    rule_code=CREDIT_XML_RULE_FIXED_MATURITY,
                    sensitive_date=date(2027, 2, 28),
                ),
            )
        )
    ).build(cutoff_date=CUTOFF)

    assert result.source_record_count == 2
    assert len(result.bucket_facts) == 1
    assert len(result.mapping_failures) == 1
    assert {
        result.bucket_facts[0].source_record_id,
        result.mapping_failures[0].source_record_id,
    } == {
        "XML_CONFIA:credit.xml:record:5",
        "XML_CONFIA:credit.xml:record:6",
    }
