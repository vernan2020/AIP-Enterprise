from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from aip.application.irrbb import IRRBBSourceMappingFailure
from aip.domain.irrbb.models import IRRBBTimeBucket
from aip.product.configured.irrbb.captaciones_capf_bucket_bridge import (
    CaptacionesCAPFPrincipalBucketBridge,
    CaptacionesCAPFPrincipalBucketFact,
)
from aip.product.configured.irrbb.captaciones_capf_operation_binding import (
    CaptacionesCAPFJoinedFact,
)
from aip.shared.money import Currency, Money


@dataclass(frozen=True, slots=True)
class CaptacionesCAPFPrincipalBucketTotal:
    """Aggregated CAPF principal for one currency and canonical IRRBB bucket."""

    currency: Currency
    bucket: IRRBBTimeBucket
    ordinal: int
    bucket_label: str
    principal: Money
    record_count: int

    def __post_init__(self) -> None:
        if self.principal.currency is not self.currency:
            raise ValueError("CAPF bucket total currency must match principal currency")
        if self.principal.amount < 0:
            raise ValueError("CAPF bucket total principal cannot be negative")
        if self.ordinal <= 0:
            raise ValueError("CAPF bucket total ordinal must be positive")
        if not self.bucket_label.strip():
            raise ValueError("CAPF bucket total label is required")
        if self.record_count <= 0:
            raise ValueError("CAPF bucket total record_count must be positive")

    @property
    def eve_ready(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class CaptacionesCAPFPrincipalBucketBatchResult:
    """One-outcome-per-joined-record CAPF principal view for the 19 buckets.

    This result is intentionally a GAP component, not a complete contractual
    schedule and not an EVE input. Inherited failures let the caller preserve
    upstream join outcomes without converting missing data to zero.
    """

    cutoff_date: date
    source_record_count: int
    bucket_facts: tuple[CaptacionesCAPFPrincipalBucketFact, ...]
    mapping_failures: tuple[IRRBBSourceMappingFailure, ...]
    bucket_totals: tuple[CaptacionesCAPFPrincipalBucketTotal, ...]

    def __post_init__(self) -> None:
        if self.source_record_count < 0:
            raise ValueError("CAPF bucket source_record_count cannot be negative")
        if len(self.bucket_facts) + len(self.mapping_failures) != self.source_record_count:
            raise ValueError("every joined CAPF record must have one bucket outcome")
        ids = tuple(
            item.joined_fact.xml_fact.source_record_id for item in self.bucket_facts
        ) + tuple(item.source_record_id for item in self.mapping_failures)
        if len(ids) != len(set(ids)):
            raise ValueError("CAPF bucket outcomes must have unique XML source_record_id")

    @property
    def eve_ready(self) -> bool:
        return False


class CaptacionesCAPFPrincipalBucketBatchBridge:
    """Batch joined CAPF principal into the existing canonical 19-band service."""

    def __init__(self, *, item_bridge: CaptacionesCAPFPrincipalBucketBridge | None = None) -> None:
        self._item_bridge = item_bridge or CaptacionesCAPFPrincipalBucketBridge()

    def build(
        self,
        *,
        cutoff_date: date,
        joined_facts: tuple[CaptacionesCAPFJoinedFact, ...],
        inherited_mapping_failures: tuple[IRRBBSourceMappingFailure, ...] = (),
    ) -> CaptacionesCAPFPrincipalBucketBatchResult:
        facts: list[CaptacionesCAPFPrincipalBucketFact] = []
        failures = list(inherited_mapping_failures)
        for joined_fact in joined_facts:
            outcome = self._item_bridge.assign(fact=joined_fact, cutoff_date=cutoff_date)
            if isinstance(outcome, IRRBBSourceMappingFailure):
                failures.append(outcome)
            else:
                facts.append(outcome)

        return CaptacionesCAPFPrincipalBucketBatchResult(
            cutoff_date=cutoff_date,
            source_record_count=len(joined_facts) + len(inherited_mapping_failures),
            bucket_facts=tuple(facts),
            mapping_failures=tuple(failures),
            bucket_totals=self._aggregate(tuple(facts)),
        )

    @staticmethod
    def _aggregate(
        facts: tuple[CaptacionesCAPFPrincipalBucketFact, ...],
    ) -> tuple[CaptacionesCAPFPrincipalBucketTotal, ...]:
        amounts: dict[tuple[Currency, IRRBBTimeBucket], Decimal] = defaultdict(Decimal)
        counts: dict[tuple[Currency, IRRBBTimeBucket], int] = defaultdict(int)
        metadata: dict[tuple[Currency, IRRBBTimeBucket], tuple[int, str]] = {}
        for fact in facts:
            key = (fact.principal.currency, fact.assignment.bucket)
            amounts[key] += fact.principal.amount
            counts[key] += 1
            metadata[key] = (fact.assignment.ordinal, fact.assignment.label)

        ordered = sorted(amounts, key=lambda item: (item[0].value, metadata[item][0]))
        return tuple(
            CaptacionesCAPFPrincipalBucketTotal(
                currency=currency,
                bucket=bucket,
                ordinal=metadata[(currency, bucket)][0],
                bucket_label=metadata[(currency, bucket)][1],
                principal=Money(amounts[(currency, bucket)], currency),
                record_count=counts[(currency, bucket)],
            )
            for currency, bucket in ordered
        )
