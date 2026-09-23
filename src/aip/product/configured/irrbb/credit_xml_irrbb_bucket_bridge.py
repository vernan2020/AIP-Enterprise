from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from aip.application.irrbb import (
    IRRBBSourceExclusion,
    IRRBBSourceMappingFailure,
    IRRBBSourceMappingFailureCode,
)
from aip.domain.irrbb.models import IRRBBTimeBucket
from aip.domain.irrbb.services.time_bucket_service import IRRBBTimeBucketService
from aip.product.configured.irrbb.credit_xml_batch_bridge import (
    CreditXMLNormalizationBatchResult,
)
from aip.product.configured.irrbb.credit_xml_rate_risk_normalizer import CreditXMLRateRiskFact


class CreditXMLNormalizationBatchPort(Protocol):
    """Pre-canonical monthly credit normalization required by the 19-band bridge."""

    def normalize(self, *, cutoff_date: date) -> CreditXMLNormalizationBatchResult: ...


@dataclass(frozen=True, slots=True)
class CreditXMLIRRBBBucketFact:
    """Auditable credit amount assigned to one canonical IRRBB time bucket.

    Source currency remains verbatim here because the governed currency catalog is a
    separate canonical-boundary gate. This DTO therefore proves temporal assignment
    only and must not be treated as a calculation-ready Money position.
    """

    source_record_id: str
    source_reference: str
    operation_id: str
    currency_source_code: str
    accounting_account_code: str
    principal_amount: Decimal
    product_amount: Decimal
    amount: Decimal
    rate_indicator: str
    source_rule_code: str
    risk_date: date
    bucket: IRRBBTimeBucket
    ordinal: int
    bucket_label: str

    def __post_init__(self) -> None:
        if not self.source_record_id.strip():
            raise ValueError("credit IRRBB bucket source_record_id is required")
        if not self.source_reference.strip():
            raise ValueError("credit IRRBB bucket source_reference is required")
        if not self.operation_id.strip():
            raise ValueError("credit IRRBB bucket operation_id is required")
        if not self.currency_source_code.strip():
            raise ValueError("credit IRRBB bucket currency_source_code is required")
        if not self.accounting_account_code.strip():
            raise ValueError("credit IRRBB bucket accounting_account_code is required")
        if self.principal_amount < 0:
            raise ValueError("credit IRRBB bucket principal_amount cannot be negative")
        if self.product_amount < 0:
            raise ValueError("credit IRRBB bucket product_amount cannot be negative")
        if self.amount < 0:
            raise ValueError("credit IRRBB bucket amount cannot be negative")
        if self.amount != self.principal_amount + self.product_amount:
            raise ValueError("credit IRRBB bucket amount must equal principal plus product")
        if not self.rate_indicator.strip():
            raise ValueError("credit IRRBB bucket rate_indicator is required")
        if not self.source_rule_code.strip():
            raise ValueError("credit IRRBB bucket source_rule_code is required")
        if self.ordinal <= 0:
            raise ValueError("credit IRRBB bucket ordinal must be positive")
        if not self.bucket_label.strip():
            raise ValueError("credit IRRBB bucket label is required")


@dataclass(frozen=True, slots=True)
class CreditXMLIRRBBBucketBatchResult:
    """One monthly credit XML represented exactly once across 19-band outcomes."""

    cutoff_date: date
    source_file_name: str
    source_sha256: str
    source_record_count: int
    bucket_facts: tuple[CreditXMLIRRBBBucketFact, ...]
    source_exclusions: tuple[IRRBBSourceExclusion, ...]
    mapping_failures: tuple[IRRBBSourceMappingFailure, ...]

    def __post_init__(self) -> None:
        represented = (
            len(self.bucket_facts) + len(self.source_exclusions) + len(self.mapping_failures)
        )
        if represented != self.source_record_count:
            raise ValueError("every credit XML source record must have one IRRBB bucket outcome")

        ids = (
            tuple(item.source_record_id for item in self.bucket_facts)
            + tuple(item.source_record_id for item in self.source_exclusions)
            + tuple(item.source_record_id for item in self.mapping_failures)
        )
        if len(ids) != len(set(ids)):
            raise ValueError("credit IRRBB bucket outcomes must have unique source_record_id")


class CreditXMLMonthlyIRRBBBucketBridge:
    """Map normalized credit facts to the canonical nineteen IRRBB time buckets.

    The bridge intentionally ignores SICVECA R1-R6 hints. A record crosses this
    temporal boundary only when an exact IRRBB risk date is available. Missing dates
    remain auditable mapping failures rather than receiving a synthetic date/bucket.
    """

    def __init__(
        self,
        *,
        normalization_bridge: CreditXMLNormalizationBatchPort,
        time_bucket_service: type[IRRBBTimeBucketService] = IRRBBTimeBucketService,
    ) -> None:
        self._normalization_bridge = normalization_bridge
        self._time_bucket_service = time_bucket_service

    def build(self, *, cutoff_date: date) -> CreditXMLIRRBBBucketBatchResult:
        normalized = self._normalization_bridge.normalize(cutoff_date=cutoff_date)
        bucket_facts: list[CreditXMLIRRBBBucketFact] = []
        failures = list(normalized.mapping_failures)

        for fact in normalized.normalized_facts:
            bucket_fact = self._assign_fact(fact=fact, cutoff_date=cutoff_date)
            if isinstance(bucket_fact, IRRBBSourceMappingFailure):
                failures.append(bucket_fact)
            else:
                bucket_facts.append(bucket_fact)

        return CreditXMLIRRBBBucketBatchResult(
            cutoff_date=cutoff_date,
            source_file_name=normalized.source_file_name,
            source_sha256=normalized.source_sha256,
            source_record_count=normalized.source_record_count,
            bucket_facts=tuple(bucket_facts),
            source_exclusions=normalized.source_exclusions,
            mapping_failures=tuple(failures),
        )

    def _assign_fact(
        self,
        *,
        fact: CreditXMLRateRiskFact,
        cutoff_date: date,
    ) -> CreditXMLIRRBBBucketFact | IRRBBSourceMappingFailure:
        risk_date = fact.sensitive_date
        if risk_date is None:
            return IRRBBSourceMappingFailure(
                source_record_id=fact.source_record_id,
                source_reference=fact.source_reference,
                code=IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD,
                canonical_field="IRRBB risk_date",
                message=(
                    "Exact IRRBB risk_date is unavailable for this credit record. "
                    "SICVECA R1-R6 bucket hints are audit-only and cannot substitute "
                    "for an exact repricing/risk date in the 19-band RTILB pipeline."
                ),
            )

        assignment = self._time_bucket_service.assign(
            valuation_date=cutoff_date,
            risk_date=risk_date,
        )
        return CreditXMLIRRBBBucketFact(
            source_record_id=fact.source_record_id,
            source_reference=fact.source_reference,
            operation_id=fact.operation_id,
            currency_source_code=fact.currency_source_code,
            accounting_account_code=fact.accounting_account_code,
            principal_amount=fact.principal_amount,
            product_amount=fact.product_amount,
            amount=fact.total_gap_amount,
            rate_indicator=fact.rate_indicator,
            source_rule_code=fact.rule_code,
            risk_date=risk_date,
            bucket=assignment.bucket,
            ordinal=assignment.ordinal,
            bucket_label=assignment.label,
        )
