from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from aip.product.configured.irrbb.credit_sicveca_range_classifier import (
    CreditSICVECARange,
    CreditSICVECARangeClassifier,
)
from aip.product.configured.irrbb.credit_xml_rate_risk_normalizer import (
    CREDIT_XML_RULE_FIXED_MATURITY,
    CREDIT_XML_RULE_VARIABLE_R1,
    CreditXMLRateRiskFact,
)

CUTOFF = date(2026, 8, 31)


def _fact(
    *,
    rule_code: str = CREDIT_XML_RULE_FIXED_MATURITY,
    sensitive_date: date | None = date(2026, 9, 30),
    bucket_hint: int | None = None,
) -> CreditXMLRateRiskFact:
    return CreditXMLRateRiskFact(
        source_record_id="ROW-1",
        source_reference="XML_CONFIA:credit.xml|record=1",
        operation_id="OP-1",
        currency_source_code="1",
        accounting_account_code="13131101",
        principal_amount=Decimal("1000"),
        product_amount=Decimal("10"),
        days_past_due=0,
        rate_indicator="F",
        nominal_rate_percent=Decimal("10"),
        origination_date=date(2025, 1, 1),
        maturity_date=date(2027, 1, 1),
        next_interest_payment_date=None,
        rate_change_date=None,
        repricing_frequency_source_code=None,
        rule_code=rule_code,
        sensitive_date=sensitive_date,
        sicveca_bucket_hint=bucket_hint,
    )


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        (0, CreditSICVECARange.R1),
        (30, CreditSICVECARange.R1),
        (31, CreditSICVECARange.R2),
        (90, CreditSICVECARange.R2),
        (91, CreditSICVECARange.R3),
        (180, CreditSICVECARange.R3),
        (181, CreditSICVECARange.R4),
        (360, CreditSICVECARange.R4),
        (361, CreditSICVECARange.R5),
        (720, CreditSICVECARange.R5),
        (721, CreditSICVECARange.R6),
        (2500, CreditSICVECARange.R6),
    ],
)
def test_dated_credit_rules_use_exact_audited_sicveca_boundaries(
    days: int,
    expected: CreditSICVECARange,
) -> None:
    fact = _fact(sensitive_date=date.fromordinal(CUTOFF.toordinal() + days))

    result = CreditSICVECARangeClassifier.classify(fact, cutoff_date=CUTOFF)

    assert result.range is expected
    assert result.days_sensitivity == days
    assert result.rule_code == CREDIT_XML_RULE_FIXED_MATURITY


def test_variable_credit_uses_certified_r1_hint_without_inventing_date() -> None:
    fact = _fact(
        rule_code=CREDIT_XML_RULE_VARIABLE_R1,
        sensitive_date=None,
        bucket_hint=1,
    )

    result = CreditSICVECARangeClassifier.classify(fact, cutoff_date=CUTOFF)

    assert result.range is CreditSICVECARange.R1
    assert result.days_sensitivity is None
    assert result.rule_code == CREDIT_XML_RULE_VARIABLE_R1


def test_variable_credit_rejects_missing_or_wrong_r1_hint() -> None:
    for hint in (None, 2, 6):
        fact = _fact(
            rule_code=CREDIT_XML_RULE_VARIABLE_R1,
            sensitive_date=None,
            bucket_hint=hint,
        )
        with pytest.raises(ValueError, match="requires audited SICVECA R1 hint"):
            CreditSICVECARangeClassifier.classify(fact, cutoff_date=CUTOFF)


def test_variable_credit_rejects_invented_exact_sensitive_date() -> None:
    fact = _fact(
        rule_code=CREDIT_XML_RULE_VARIABLE_R1,
        sensitive_date=date(2026, 9, 1),
        bucket_hint=1,
    )

    with pytest.raises(ValueError, match="must not invent an exact sensitive date"):
        CreditSICVECARangeClassifier.classify(fact, cutoff_date=CUTOFF)


def test_dated_rule_rejects_missing_sensitive_date() -> None:
    fact = _fact(sensitive_date=None)

    with pytest.raises(ValueError, match="requires sensitive_date"):
        CreditSICVECARangeClassifier.classify(fact, cutoff_date=CUTOFF)


def test_dated_rule_rejects_sensitive_date_before_cutoff() -> None:
    fact = _fact(sensitive_date=date(2026, 8, 30))

    with pytest.raises(ValueError, match="cannot be before cutoff_date"):
        CreditSICVECARangeClassifier.classify(fact, cutoff_date=CUTOFF)


def test_assignment_preserves_source_and_operation_lineage() -> None:
    fact = replace(_fact(), source_record_id="ROW-42", operation_id="OP-42")

    result = CreditSICVECARangeClassifier.classify(fact, cutoff_date=CUTOFF)

    assert result.source_record_id == "ROW-42"
    assert result.operation_id == "OP-42"



def test_classifier_rejects_unknown_rule_code() -> None:
    fact = _fact(rule_code="CREDIT_UNKNOWN", sensitive_date=date(2026, 9, 30))

    with pytest.raises(ValueError, match="unsupported credit SICVECA rule_code"):
        CreditSICVECARangeClassifier.classify(fact, cutoff_date=CUTOFF)
