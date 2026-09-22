from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import IntEnum

from aip.product.configured.irrbb.credit_xml_rate_risk_normalizer import (
    CREDIT_XML_RULE_FIXED_MATURITY,
    CREDIT_XML_RULE_FV_CHANGE_DATE,
    CREDIT_XML_RULE_VARIABLE_R1,
    CreditXMLRateRiskFact,
)


class CreditSICVECARange(IntEnum):
    """Six audited SICVECA 205 interest-rate-gap ranges for credit."""

    R1 = 1
    R2 = 2
    R3 = 3
    R4 = 4
    R5 = 5
    R6 = 6


@dataclass(frozen=True, slots=True)
class CreditSICVECARangeAssignment:
    """Auditable six-range assignment kept separate from RTILB 19-band buckets."""

    source_record_id: str
    operation_id: str
    range: CreditSICVECARange
    days_sensitivity: int | None
    rule_code: str


class CreditSICVECARangeClassifier:
    """Assign normalized credit facts to the audited SICVECA R1-R6 ranges.

    This classifier deliberately does not use IRRBBTimeBucketService. SICVECA R1-R6
    and the RTILB 19-band structure are different regulatory classifications and must
    not share bucket semantics.
    """

    @classmethod
    def classify(
        cls,
        fact: CreditXMLRateRiskFact,
        *,
        cutoff_date: date,
    ) -> CreditSICVECARangeAssignment:
        if fact.rule_code == CREDIT_XML_RULE_VARIABLE_R1:
            if fact.sicveca_bucket_hint != CreditSICVECARange.R1:
                raise ValueError("variable credit rule requires audited SICVECA R1 hint")
            if fact.sensitive_date is not None:
                raise ValueError("variable credit R1 rule must not invent an exact sensitive date")
            return CreditSICVECARangeAssignment(
                source_record_id=fact.source_record_id,
                operation_id=fact.operation_id,
                range=CreditSICVECARange.R1,
                days_sensitivity=None,
                rule_code=fact.rule_code,
            )

        if fact.rule_code not in {
            CREDIT_XML_RULE_FIXED_MATURITY,
            CREDIT_XML_RULE_FV_CHANGE_DATE,
        }:
            raise ValueError(f"unsupported credit SICVECA rule_code: {fact.rule_code}")

        sensitive_date = fact.sensitive_date
        if sensitive_date is None:
            raise ValueError("dated credit SICVECA rule requires sensitive_date")

        days = (sensitive_date - cutoff_date).days
        if days < 0:
            raise ValueError("credit SICVECA sensitive_date cannot be before cutoff_date")

        return CreditSICVECARangeAssignment(
            source_record_id=fact.source_record_id,
            operation_id=fact.operation_id,
            range=cls._range_for_days(days),
            days_sensitivity=days,
            rule_code=fact.rule_code,
        )

    @staticmethod
    def _range_for_days(days: int) -> CreditSICVECARange:
        if days <= 30:
            return CreditSICVECARange.R1
        if days <= 90:
            return CreditSICVECARange.R2
        if days <= 180:
            return CreditSICVECARange.R3
        if days <= 360:
            return CreditSICVECARange.R4
        if days <= 720:
            return CreditSICVECARange.R5
        return CreditSICVECARange.R6
