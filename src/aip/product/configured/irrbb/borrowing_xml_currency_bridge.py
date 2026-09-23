from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from aip.application.irrbb import (
    IRRBBSourceMappingFailure,
    IRRBBSourceMappingFailureCode,
)
from aip.product.configured.irrbb.borrowing_xml_batch_bridge import (
    BorrowingXMLNormalizationBatchResult,
)
from aip.product.configured.irrbb.borrowing_xml_currency_catalog import (
    BorrowingXMLCurrencyCatalog,
)
from aip.product.configured.irrbb.borrowing_xml_normalizer import BorrowingXMLFact
from aip.shared.money import Currency, Money


@dataclass(frozen=True, slots=True)
class BorrowingXMLCanonicalCurrencyFact:
    """Obligaciones fact after governed source-currency translation only.

    Signed balances and optional amounts remain source-faithful. Account policy,
    repricing, 19-band assignment and contractual cash-flow interpretation belong
    to later governed boundaries.
    """

    source_record_id: str
    source_reference: str
    creditor_id: str
    operation_id: str
    operation_type_source_code: str
    guarantee_indicator: str | None
    obligation_indicator: str | None
    revolving_indicator: str | None
    credit_line_id: str | None
    conditional_indicator: str | None
    country_source_code: str | None
    contract_currency_source_code: str | None
    disbursement_currency_source_code: str | None
    rate_type_source_code: str
    variable_rate_source_code: str | None
    nominal_rate_percent: Decimal | None
    sugef_catalog_source_code: str | None
    accounting_account_code: str
    principal: Money
    contracted_amount: Money | None
    product_account_code: str | None
    product: Money | None
    origination_date: date | None
    maturity_date: date | None
    next_principal_payment_date: date | None
    next_interest_payment_date: date | None
    principal_payment_frequency_source_code: str | None
    interest_payment_frequency_source_code: str | None

    def __post_init__(self) -> None:
        if not self.source_record_id.strip():
            raise ValueError("canonical Obligaciones source_record_id is required")
        if not self.source_reference.strip():
            raise ValueError("canonical Obligaciones source_reference is required")
        if not self.creditor_id.strip():
            raise ValueError("canonical Obligaciones creditor_id is required")
        if not self.operation_id.strip():
            raise ValueError("canonical Obligaciones operation_id is required")
        if not self.operation_type_source_code.strip():
            raise ValueError("canonical Obligaciones operation_type_source_code is required")
        if not self.rate_type_source_code.strip():
            raise ValueError("canonical Obligaciones rate_type_source_code is required")
        if not self.accounting_account_code.strip():
            raise ValueError("canonical Obligaciones accounting_account_code is required")
        if (
            self.contracted_amount is not None
            and self.contracted_amount.currency is not self.principal.currency
        ):
            raise ValueError(
                "canonical Obligaciones contracted amount currency must match principal currency"
            )
        if self.product is not None and self.product.currency is not self.principal.currency:
            raise ValueError(
                "canonical Obligaciones product currency must match principal currency"
            )

    @property
    def currency(self) -> Currency:
        return self.principal.currency


@dataclass(frozen=True, slots=True)
class BorrowingXMLCurrencyBatchResult:
    """Obligaciones outcomes after the governed currency boundary."""

    source_record_count: int
    canonical_facts: tuple[BorrowingXMLCanonicalCurrencyFact, ...]
    mapping_failures: tuple[IRRBBSourceMappingFailure, ...]

    def __post_init__(self) -> None:
        if self.source_record_count < 0:
            raise ValueError("Obligaciones XML source_record_count cannot be negative")
        if len(self.canonical_facts) + len(self.mapping_failures) != self.source_record_count:
            raise ValueError(
                "every Obligaciones XML source record must have one currency-boundary outcome"
            )

        ids = tuple(item.source_record_id for item in self.canonical_facts) + tuple(
            item.source_record_id for item in self.mapping_failures
        )
        if len(ids) != len(set(ids)):
            raise ValueError("Obligaciones currency outcomes must have unique source_record_id")


class BorrowingXMLCurrencyBridge:
    """Cross the Obligaciones currency boundary only through a governed catalog."""

    def __init__(self, *, catalog: BorrowingXMLCurrencyCatalog) -> None:
        self._catalog = catalog

    def map_batch(
        self,
        batch: BorrowingXMLNormalizationBatchResult,
    ) -> BorrowingXMLCurrencyBatchResult:
        canonical: list[BorrowingXMLCanonicalCurrencyFact] = []
        failures = list(batch.mapping_failures)

        for fact in batch.normalized_facts:
            outcome = self._map_fact(fact)
            if isinstance(outcome, IRRBBSourceMappingFailure):
                failures.append(outcome)
            else:
                canonical.append(outcome)

        return BorrowingXMLCurrencyBatchResult(
            source_record_count=batch.source_record_count,
            canonical_facts=tuple(canonical),
            mapping_failures=tuple(failures),
        )

    def _map_fact(
        self,
        fact: BorrowingXMLFact,
    ) -> BorrowingXMLCanonicalCurrencyFact | IRRBBSourceMappingFailure:
        try:
            currency = self._catalog.resolve(fact.currency_source_code)
        except (KeyError, ValueError):
            return IRRBBSourceMappingFailure(
                source_record_id=fact.source_record_id,
                source_reference=fact.source_reference,
                code=IRRBBSourceMappingFailureCode.UNSUPPORTED_SOURCE_VALUE,
                canonical_field="currency",
                message=(
                    "Obligaciones XML currency source code "
                    f"{fact.currency_source_code!r} is not mapped by the governed "
                    f"catalog {self._catalog.code}:{self._catalog.version}."
                ),
            )

        return BorrowingXMLCanonicalCurrencyFact(
            source_record_id=fact.source_record_id,
            source_reference=fact.source_reference,
            creditor_id=fact.creditor_id,
            operation_id=fact.operation_id,
            operation_type_source_code=fact.operation_type_source_code,
            guarantee_indicator=fact.guarantee_indicator,
            obligation_indicator=fact.obligation_indicator,
            revolving_indicator=fact.revolving_indicator,
            credit_line_id=fact.credit_line_id,
            conditional_indicator=fact.conditional_indicator,
            country_source_code=fact.country_source_code,
            contract_currency_source_code=fact.contract_currency_source_code,
            disbursement_currency_source_code=fact.disbursement_currency_source_code,
            rate_type_source_code=fact.rate_type_source_code,
            variable_rate_source_code=fact.variable_rate_source_code,
            nominal_rate_percent=fact.nominal_rate_percent,
            sugef_catalog_source_code=fact.sugef_catalog_source_code,
            accounting_account_code=fact.accounting_account_code,
            principal=Money(fact.principal_amount, currency),
            contracted_amount=self._money_or_none(fact.contracted_amount, currency),
            product_account_code=fact.product_account_code,
            product=self._money_or_none(fact.product_amount, currency),
            origination_date=fact.origination_date,
            maturity_date=fact.maturity_date,
            next_principal_payment_date=fact.next_principal_payment_date,
            next_interest_payment_date=fact.next_interest_payment_date,
            principal_payment_frequency_source_code=(fact.principal_payment_frequency_source_code),
            interest_payment_frequency_source_code=(fact.interest_payment_frequency_source_code),
        )

    @staticmethod
    def _money_or_none(amount: Decimal | None, currency: Currency) -> Money | None:
        if amount is None:
            return None
        return Money(amount, currency)
