from __future__ import annotations

from dataclasses import dataclass

from aip.application.irrbb import (
    IRRBBSourceMappingFailure,
    IRRBBSourceMappingFailureCode,
)
from aip.product.configured.irrbb.captaciones_xml_batch_bridge import (
    CaptacionesXMLNormalizationBatchResult,
)
from aip.product.configured.irrbb.captaciones_xml_currency_catalog import (
    CaptacionesXMLCurrencyCatalog,
)
from aip.product.configured.irrbb.captaciones_xml_normalizer import CaptacionesXMLFact
from aip.shared.money import Currency, Money


@dataclass(frozen=True, slots=True)
class CaptacionesXMLCanonicalCurrencyFact:
    """Captaciones fact after governed source-currency translation only."""

    source_record_id: str
    source_reference: str
    creditor_id: str
    operation_id: str
    operation_type_source_code: str
    account_type_source_code: str
    rate_type_source_code: str
    accounting_account_code: str
    amount: Money

    def __post_init__(self) -> None:
        if not self.source_record_id.strip():
            raise ValueError("canonical Captaciones source_record_id is required")
        if not self.source_reference.strip():
            raise ValueError("canonical Captaciones source_reference is required")
        if not self.creditor_id.strip():
            raise ValueError("canonical Captaciones creditor_id is required")
        if not self.operation_id.strip():
            raise ValueError("canonical Captaciones operation_id is required")
        if not self.operation_type_source_code.strip():
            raise ValueError("canonical Captaciones operation_type_source_code is required")
        if not self.account_type_source_code.strip():
            raise ValueError("canonical Captaciones account_type_source_code is required")
        if not self.rate_type_source_code.strip():
            raise ValueError("canonical Captaciones rate_type_source_code is required")
        if not self.accounting_account_code.strip():
            raise ValueError("canonical Captaciones accounting_account_code is required")
        if self.amount.amount < 0:
            raise ValueError("canonical Captaciones amount cannot be negative")

    @property
    def currency(self) -> Currency:
        return self.amount.currency


@dataclass(frozen=True, slots=True)
class CaptacionesXMLCurrencyBatchResult:
    """Captaciones outcomes after the governed currency boundary."""

    source_record_count: int
    canonical_facts: tuple[CaptacionesXMLCanonicalCurrencyFact, ...]
    mapping_failures: tuple[IRRBBSourceMappingFailure, ...]

    def __post_init__(self) -> None:
        represented = len(self.canonical_facts) + len(self.mapping_failures)
        if represented != self.source_record_count:
            raise ValueError(
                "every Captaciones XML source record must have one currency-boundary outcome"
            )

        ids = tuple(item.source_record_id for item in self.canonical_facts) + tuple(
            item.source_record_id for item in self.mapping_failures
        )
        if len(ids) != len(set(ids)):
            raise ValueError("Captaciones currency outcomes must have unique source_record_id")


class CaptacionesXMLCurrencyBridge:
    """Cross the Captaciones currency boundary only through a governed catalog."""

    def __init__(self, *, catalog: CaptacionesXMLCurrencyCatalog) -> None:
        self._catalog = catalog

    def map_batch(
        self,
        batch: CaptacionesXMLNormalizationBatchResult,
    ) -> CaptacionesXMLCurrencyBatchResult:
        canonical: list[CaptacionesXMLCanonicalCurrencyFact] = []
        failures = list(batch.mapping_failures)

        for fact in batch.normalized_facts:
            outcome = self._map_fact(fact)
            if isinstance(outcome, IRRBBSourceMappingFailure):
                failures.append(outcome)
            else:
                canonical.append(outcome)

        return CaptacionesXMLCurrencyBatchResult(
            source_record_count=batch.source_record_count,
            canonical_facts=tuple(canonical),
            mapping_failures=tuple(failures),
        )

    def _map_fact(
        self,
        fact: CaptacionesXMLFact,
    ) -> CaptacionesXMLCanonicalCurrencyFact | IRRBBSourceMappingFailure:
        try:
            currency = self._catalog.resolve(fact.currency_source_code)
        except (KeyError, ValueError):
            return IRRBBSourceMappingFailure(
                source_record_id=fact.source_record_id,
                source_reference=fact.source_reference,
                code=IRRBBSourceMappingFailureCode.UNSUPPORTED_SOURCE_VALUE,
                canonical_field="currency",
                message=(
                    "Captaciones XML currency source code "
                    f"{fact.currency_source_code!r} is not mapped by the governed "
                    f"catalog {self._catalog.code}:{self._catalog.version}."
                ),
            )

        return CaptacionesXMLCanonicalCurrencyFact(
            source_record_id=fact.source_record_id,
            source_reference=fact.source_reference,
            creditor_id=fact.creditor_id,
            operation_id=fact.operation_id,
            operation_type_source_code=fact.operation_type_source_code,
            account_type_source_code=fact.account_type_source_code,
            rate_type_source_code=fact.rate_type_source_code,
            accounting_account_code=fact.accounting_account_code,
            amount=Money(fact.total_balance, currency),
        )
