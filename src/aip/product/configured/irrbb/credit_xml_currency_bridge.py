from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from aip.application.irrbb import (
    IRRBBSourceExclusion,
    IRRBBSourceMappingFailure,
    IRRBBSourceMappingFailureCode,
)
from aip.domain.irrbb.models import IRRBBTimeBucket
from aip.product.configured.irrbb.credit_xml_currency_catalog import CreditXMLCurrencyCatalog
from aip.product.configured.irrbb.credit_xml_irrbb_bucket_bridge import (
    CreditXMLIRRBBBucketBatchResult,
    CreditXMLIRRBBBucketFact,
)
from aip.shared.money import Currency, Money


@dataclass(frozen=True, slots=True)
class CreditXMLCanonicalBucketFact:
    """Credit 19-band fact after governed source-currency translation."""

    source_record_id: str
    source_reference: str
    operation_id: str
    accounting_account_code: str
    amount: Money
    rate_indicator: str
    source_rule_code: str
    risk_date: date
    bucket: IRRBBTimeBucket
    ordinal: int
    bucket_label: str

    def __post_init__(self) -> None:
        if not self.source_record_id.strip():
            raise ValueError("canonical credit bucket source_record_id is required")
        if not self.source_reference.strip():
            raise ValueError("canonical credit bucket source_reference is required")
        if not self.operation_id.strip():
            raise ValueError("canonical credit bucket operation_id is required")
        if not self.accounting_account_code.strip():
            raise ValueError("canonical credit bucket accounting_account_code is required")
        if self.amount.amount < 0:
            raise ValueError("canonical credit bucket amount cannot be negative")
        if not self.rate_indicator.strip():
            raise ValueError("canonical credit bucket rate_indicator is required")
        if not self.source_rule_code.strip():
            raise ValueError("canonical credit bucket source_rule_code is required")
        if self.ordinal <= 0:
            raise ValueError("canonical credit bucket ordinal must be positive")
        if not self.bucket_label.strip():
            raise ValueError("canonical credit bucket label is required")

    @property
    def currency(self) -> Currency:
        return self.amount.currency


@dataclass(frozen=True, slots=True)
class CreditXMLCanonicalBucketBatchResult:
    """19-band credit outcomes after the governed currency boundary."""

    source_record_count: int
    canonical_bucket_facts: tuple[CreditXMLCanonicalBucketFact, ...]
    source_exclusions: tuple[IRRBBSourceExclusion, ...]
    mapping_failures: tuple[IRRBBSourceMappingFailure, ...]

    def __post_init__(self) -> None:
        represented = (
            len(self.canonical_bucket_facts)
            + len(self.source_exclusions)
            + len(self.mapping_failures)
        )
        if represented != self.source_record_count:
            raise ValueError(
                "every credit XML source record must have one canonical currency outcome"
            )

        ids = (
            tuple(item.source_record_id for item in self.canonical_bucket_facts)
            + tuple(item.source_record_id for item in self.source_exclusions)
            + tuple(item.source_record_id for item in self.mapping_failures)
        )
        if len(ids) != len(set(ids)):
            raise ValueError("canonical credit currency outcomes must have unique source_record_id")


class CreditXMLCurrencyBridge:
    """Cross the currency boundary only through an injected governed catalog."""

    def __init__(self, *, catalog: CreditXMLCurrencyCatalog) -> None:
        self._catalog = catalog

    def map_batch(
        self,
        batch: CreditXMLIRRBBBucketBatchResult,
    ) -> CreditXMLCanonicalBucketBatchResult:
        canonical: list[CreditXMLCanonicalBucketFact] = []
        failures = list(batch.mapping_failures)

        for fact in batch.bucket_facts:
            outcome = self._map_fact(fact)
            if isinstance(outcome, IRRBBSourceMappingFailure):
                failures.append(outcome)
            else:
                canonical.append(outcome)

        return CreditXMLCanonicalBucketBatchResult(
            source_record_count=batch.source_record_count,
            canonical_bucket_facts=tuple(canonical),
            source_exclusions=batch.source_exclusions,
            mapping_failures=tuple(failures),
        )

    def _map_fact(
        self,
        fact: CreditXMLIRRBBBucketFact,
    ) -> CreditXMLCanonicalBucketFact | IRRBBSourceMappingFailure:
        try:
            currency = self._catalog.resolve(fact.currency_source_code)
        except (KeyError, ValueError):
            return IRRBBSourceMappingFailure(
                source_record_id=fact.source_record_id,
                source_reference=fact.source_reference,
                code=IRRBBSourceMappingFailureCode.UNSUPPORTED_SOURCE_VALUE,
                canonical_field="currency",
                message=(
                    "Credit XML currency source code "
                    f"{fact.currency_source_code!r} is not mapped by the governed "
                    f"catalog {self._catalog.code}:{self._catalog.version}."
                ),
            )

        return CreditXMLCanonicalBucketFact(
            source_record_id=fact.source_record_id,
            source_reference=fact.source_reference,
            operation_id=fact.operation_id,
            accounting_account_code=fact.accounting_account_code,
            amount=Money(fact.amount, currency),
            rate_indicator=fact.rate_indicator,
            source_rule_code=fact.source_rule_code,
            risk_date=fact.risk_date,
            bucket=fact.bucket,
            ordinal=fact.ordinal,
            bucket_label=fact.bucket_label,
        )
