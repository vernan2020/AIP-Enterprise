from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any

from aip.application.irrbb.contracts import (
    IRRBBPositionSourceRecord,
    IRRBBSourceMappingFailure,
    IRRBBSourceMappingFailureCode,
)
from aip.domain.irrbb.models import (
    BankingBookPosition,
    BankingBookSide,
    IRRBBInstrumentClass,
    OptionalityType,
    PaymentStructure,
    RateType,
)
from aip.product.configured.irrbb.investment_source_rules import InvestmentMasterSourceRules
from aip.product.configured.irrbb.source_acl import IRRBBSourceRecordEnvelope
from aip.shared.money import Currency, Money


class InvestmentMasterPrincipalField(str, Enum):
    """Native balance field approved as canonical investment principal."""

    PRINCIPAL_BALANCE = "principal_balance"
    TRADED_BALANCE = "traded_balance"


@dataclass(frozen=True, slots=True)
class InvestmentMasterMappingRule:
    """One explicit source-product decision for the canonical investment boundary."""

    product_code: str
    classification: str | None
    instrument_class: IRRBBInstrumentClass
    side: BankingBookSide
    payment_structure: PaymentStructure
    optionality: OptionalityType
    principal_field: InvestmentMasterPrincipalField

    def __post_init__(self) -> None:
        if not self.product_code.strip():
            raise ValueError("investment mapping rule product_code is required")
        if self.classification is not None and not self.classification.strip():
            raise ValueError("investment mapping rule classification cannot be blank")

    @property
    def selector(self) -> tuple[str, str | None]:
        return (
            self.product_code.strip().casefold(),
            self.classification.strip().casefold() if self.classification is not None else None,
        )


@dataclass(frozen=True, slots=True)
class InvestmentMasterCanonicalMappingPolicy:
    """Versioned, explicit policy required to interpret source product semantics.

    No production default is provided. A rule with ``classification=None`` is an
    explicit product-level fallback; an exact product+classification rule takes
    precedence when both exist.
    """

    code: str
    version: str
    effective_from: date
    source_reference: str
    rules: tuple[InvestmentMasterMappingRule, ...]

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("investment mapping policy code is required")
        if not self.version.strip():
            raise ValueError("investment mapping policy version is required")
        if not self.source_reference.strip():
            raise ValueError("investment mapping policy source_reference is required")
        if not self.rules:
            raise ValueError("investment mapping policy must contain at least one rule")
        selectors = tuple(rule.selector for rule in self.rules)
        if len(set(selectors)) != len(selectors):
            raise ValueError("investment mapping policy selectors must be unique")

    @property
    def reference(self) -> str:
        return f"{self.code}@{self.version}|{self.source_reference}"

    def resolve(
        self,
        *,
        product_code: str,
        classification: str | None,
    ) -> InvestmentMasterMappingRule | None:
        product_key = product_code.strip().casefold()
        classification_key = (
            classification.strip().casefold() if classification and classification.strip() else None
        )
        exact_selector = (product_key, classification_key)
        fallback_selector = (product_key, None)

        exact = next((rule for rule in self.rules if rule.selector == exact_selector), None)
        if exact is not None:
            return exact
        if classification_key is not None:
            return next((rule for rule in self.rules if rule.selector == fallback_selector), None)
        return None

    def rule_reference(self, rule: InvestmentMasterMappingRule) -> str:
        classification = rule.classification if rule.classification is not None else "*"
        return f"{self.reference}|product={rule.product_code}|classification={classification}"


@dataclass(frozen=True, slots=True)
class InvestmentMasterSourcePayload:
    """Direct reader evidence supplied to the physical investment mapper."""

    normalized_position: Mapping[str, Any]
    detected_column_mapping: Mapping[str, str]


class InstitutionalInvestmentMasterCanonicalMapper:
    """Map direct institutional-master evidence into the canonical RTILB model.

    The mapper is intentionally fail-closed. It does not trust convenience fields
    enriched by dashboard providers, does not use domain defaults for semantic
    classifications and does not derive floating reset terms from coupon dates.
    """

    def __init__(self, policy: InvestmentMasterCanonicalMappingPolicy) -> None:
        self._policy = policy

    def map_record(
        self,
        record: IRRBBSourceRecordEnvelope[InvestmentMasterSourcePayload],
    ) -> IRRBBPositionSourceRecord | IRRBBSourceMappingFailure:
        payload = record.payload
        position = payload.normalized_position

        position_id = InvestmentMasterSourceRules.stable_position_id(
            contract_number=position.get("contract_number"),
            isin=position.get("isin"),
            series=position.get("series"),
        )
        if position_id is None or not self._identity_is_native(payload):
            return self._failure(
                record,
                code=IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD,
                canonical_field="position_id",
                message="Stable position identity is not proven by native contract plus ISIN/series evidence.",
            )

        product_code = self._text(position.get("product_code"))
        if not product_code or not self._has_native_value(payload, "product_code"):
            return self._failure(
                record,
                code=IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD,
                canonical_field="product_type",
                message="Native product_code evidence is required for canonical product_type.",
            )

        classification = self._text(position.get("classification")) or None
        rule = self._policy.resolve(product_code=product_code, classification=classification)
        if rule is None:
            return self._failure(
                record,
                code=IRRBBSourceMappingFailureCode.UNSUPPORTED_SOURCE_VALUE,
                canonical_field="product_type",
                message=(
                    "No approved investment mapping rule exists for "
                    f"product_code={product_code!r}, classification={classification!r} under "
                    f"{self._policy.reference}."
                ),
            )
        if rule.classification is not None and not self._has_native_value(payload, "classification"):
            return self._failure(
                record,
                code=IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD,
                canonical_field="product_type",
                message="The selected mapping rule requires native classification evidence.",
            )

        currency = self._currency(payload)
        if isinstance(currency, IRRBBSourceMappingFailureCode):
            return self._failure(
                record,
                code=currency,
                canonical_field="currency",
                message="Native contractual currency is missing or unsupported; normalized CRC defaults are not accepted.",
            )

        principal = self._native_decimal(payload, rule.principal_field.value)
        if principal is None:
            return self._failure(
                record,
                code=IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD,
                canonical_field="principal",
                message=(
                    f"Policy {self._policy.reference} requires native "
                    f"{rule.principal_field.value} for canonical principal; no fallback balance is permitted."
                ),
            )
        if principal < 0:
            return self._failure(
                record,
                code=IRRBBSourceMappingFailureCode.INVALID_CANONICAL_VALUE,
                canonical_field="principal",
                message="Canonical investment principal cannot be negative.",
            )

        rate_type = self._rate_type(payload)
        if rate_type is None:
            return self._failure(
                record,
                code=IRRBBSourceMappingFailureCode.UNSUPPORTED_SOURCE_VALUE,
                canonical_field="rate_type",
                message="Native variable-rate flag is missing or outside the approved strict mapping.",
            )

        maturity_date = self._native_date(payload, "maturity_date")
        if maturity_date is None:
            return self._failure(
                record,
                code=IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD,
                canonical_field="maturity_date",
                message="Native contractual maturity_date is required.",
            )

        contractual_rate = self._native_decimal(payload, "nominal_rate")
        if contractual_rate is None:
            return self._failure(
                record,
                code=IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD,
                canonical_field="contractual_rate",
                message="Native nominal_rate is required, including an explicit zero for zero-coupon positions.",
            )

        payment_frequency_months: int | None = None
        if contractual_rate != Decimal("0"):
            if not self._has_native_value(payload, "periodicity"):
                return self._failure(
                    record,
                    code=IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD,
                    canonical_field="payment_frequency_months",
                    message="Coupon-bearing investment requires native periodicity evidence.",
                )
            payment_frequency_months = InvestmentMasterSourceRules.payment_frequency_months(
                position.get("periodicity")
            )
            if payment_frequency_months is None:
                return self._failure(
                    record,
                    code=IRRBBSourceMappingFailureCode.UNSUPPORTED_SOURCE_VALUE,
                    canonical_field="payment_frequency_months",
                    message="Investment periodicity is outside the approved strict mapping.",
                )

        next_repricing_date: date | None = None
        repricing_frequency_months: int | None = None
        if rate_type is RateType.FLOATING:
            next_repricing_date = self._native_date(payload, "next_repricing_date")
            if next_repricing_date is None:
                return self._failure(
                    record,
                    code=IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD,
                    canonical_field="next_repricing_date",
                    message=(
                        "Floating investment requires native contractual next_repricing_date; "
                        "coupon-date proxies are not accepted."
                    ),
                )
            repricing_frequency_months = self._native_positive_int(
                payload, "repricing_frequency_months"
            )
            if repricing_frequency_months is None:
                return self._failure(
                    record,
                    code=IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD,
                    canonical_field="repricing_frequency_months",
                    message=(
                        "Floating investment requires native contractual repricing_frequency_months; "
                        "coupon periodicity is not treated as reset frequency."
                    ),
                )

        carrying_amount = self._optional_native_decimal(payload, "book_value")
        if isinstance(carrying_amount, IRRBBSourceMappingFailureCode):
            return self._failure(
                record,
                code=carrying_amount,
                canonical_field="carrying_amount",
                message="Native book_value is present but cannot be represented as a monetary amount.",
            )

        last_interest_payment_date = self._optional_native_date(
            payload, "last_interest_payment_date"
        )
        if isinstance(last_interest_payment_date, IRRBBSourceMappingFailureCode):
            return self._failure(
                record,
                code=last_interest_payment_date,
                canonical_field="last_interest_payment_date",
                message="Native last_interest_payment_date is present but invalid.",
            )

        return IRRBBPositionSourceRecord(
            position=BankingBookPosition(
                position_id=position_id,
                product_type=product_code,
                side=rule.side,
                currency=currency,
                principal=Money(principal, currency),
                rate_type=rate_type,
                maturity_date=maturity_date,
                source_reference=record.source_reference,
                carrying_amount=(
                    Money(carrying_amount, currency) if carrying_amount is not None else None
                ),
                contractual_rate=contractual_rate,
                next_repricing_date=next_repricing_date,
                repricing_frequency_months=repricing_frequency_months,
                payment_frequency_months=payment_frequency_months,
                optionality=rule.optionality,
                instrument_class=rule.instrument_class,
                payment_structure=rule.payment_structure,
                last_interest_payment_date=last_interest_payment_date,
            ),
            mapping_rule_reference=self._policy.rule_reference(rule),
        )

    def _currency(
        self,
        payload: InvestmentMasterSourcePayload,
    ) -> Currency | IRRBBSourceMappingFailureCode:
        if not self._has_native_value(payload, "currency"):
            return IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD
        code = self._text(payload.normalized_position.get("currency"))
        if not code:
            return IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD
        try:
            return Currency.from_code(code)
        except ValueError:
            return IRRBBSourceMappingFailureCode.UNSUPPORTED_SOURCE_VALUE

    def _rate_type(self, payload: InvestmentMasterSourcePayload) -> RateType | None:
        if not self._has_native_value(payload, "variable_rate_flag"):
            return None
        return InvestmentMasterSourceRules.rate_type(
            payload.normalized_position.get("variable_rate_flag")
        )

    @classmethod
    def _identity_is_native(cls, payload: InvestmentMasterSourcePayload) -> bool:
        return cls._has_native_value(payload, "contract_number") and (
            cls._has_native_value(payload, "isin") or cls._has_native_value(payload, "series")
        )

    @classmethod
    def _native_decimal(
        cls,
        payload: InvestmentMasterSourcePayload,
        canonical_field: str,
    ) -> Decimal | None:
        if not cls._has_native_value(payload, canonical_field):
            return None
        return cls._decimal(payload.normalized_position.get(canonical_field))

    @classmethod
    def _optional_native_decimal(
        cls,
        payload: InvestmentMasterSourcePayload,
        canonical_field: str,
    ) -> Decimal | None | IRRBBSourceMappingFailureCode:
        if not cls._has_native_value(payload, canonical_field):
            return None
        value = cls._decimal(payload.normalized_position.get(canonical_field))
        return value if value is not None else IRRBBSourceMappingFailureCode.INVALID_CANONICAL_VALUE

    @classmethod
    def _native_date(
        cls,
        payload: InvestmentMasterSourcePayload,
        canonical_field: str,
    ) -> date | None:
        if not cls._has_native_value(payload, canonical_field):
            return None
        value = payload.normalized_position.get(canonical_field)
        if isinstance(value, date):
            return value
        if isinstance(value, str) and value.strip():
            try:
                return date.fromisoformat(value.strip())
            except ValueError:
                return None
        return None

    @classmethod
    def _optional_native_date(
        cls,
        payload: InvestmentMasterSourcePayload,
        canonical_field: str,
    ) -> date | None | IRRBBSourceMappingFailureCode:
        if not cls._has_native_value(payload, canonical_field):
            return None
        value = cls._native_date(payload, canonical_field)
        return value if value is not None else IRRBBSourceMappingFailureCode.INVALID_CANONICAL_VALUE

    @classmethod
    def _native_positive_int(
        cls,
        payload: InvestmentMasterSourcePayload,
        canonical_field: str,
    ) -> int | None:
        value = cls._native_decimal(payload, canonical_field)
        if value is None or value <= 0 or value != value.to_integral_value():
            return None
        return int(value)

    @classmethod
    def _has_native_value(
        cls,
        payload: InvestmentMasterSourcePayload,
        canonical_field: str,
    ) -> bool:
        header = payload.detected_column_mapping.get(canonical_field)
        if header is None or not str(header).strip():
            return False
        source_values = payload.normalized_position.get("source_values")
        if not isinstance(source_values, Mapping):
            return False
        raw_value = source_values.get(cls._normalize_header(str(header)))
        return bool(cls._text(raw_value))

    @staticmethod
    def _normalize_header(value: str) -> str:
        text = value.replace("\ufeff", "").replace("\u00a0", " ").replace("_", " ")
        text = re.sub(r"[\u200b\u200c\u200d\ufeff\u2060]", "", text)
        normalized = unicodedata.normalize("NFKD", text.strip().lower())
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
        ascii_text = re.sub(r"\s+", " ", ascii_text)
        ascii_text = re.sub(r"[^a-z0-9]+", " ", ascii_text)
        return re.sub(r"\s+", " ", ascii_text).strip()

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value in (None, "") or isinstance(value, bool):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _failure(
        record: IRRBBSourceRecordEnvelope[InvestmentMasterSourcePayload],
        *,
        code: IRRBBSourceMappingFailureCode,
        canonical_field: str,
        message: str,
    ) -> IRRBBSourceMappingFailure:
        return IRRBBSourceMappingFailure(
            source_record_id=record.source_record_id,
            source_reference=record.source_reference,
            code=code,
            canonical_field=canonical_field,
            message=message,
        )
