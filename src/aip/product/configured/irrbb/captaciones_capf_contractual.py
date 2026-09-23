from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import PurePath
from typing import Any, TypeAlias

from aip.application.irrbb import (
    IRRBBSourceMappingFailure,
    IRRBBSourceMappingFailureCode,
)
from aip.domain.irrbb.models import RateType


@dataclass(frozen=True, slots=True)
class CaptacionesCAPFProductRule:
    """One evidenced interpretation of a term-deposit product code."""

    product_code: str
    capitalizes_at_interest_payment_frequency: bool
    evidence_reference: str

    def __post_init__(self) -> None:
        if not self.product_code.strip():
            raise ValueError("CAPF product rule product_code is required")
        if self.product_code != self.product_code.strip():
            raise ValueError("CAPF product rule product_code must be canonical text")
        if not self.evidence_reference.strip():
            raise ValueError("CAPF product rule evidence_reference is required")


@dataclass(frozen=True, slots=True)
class CaptacionesCAPFProductPolicy:
    """Versioned, fail-closed product semantics for the contractual complement."""

    code: str
    version: str
    evidence_reference: str
    contractual_rate_type: RateType
    rate_type_evidence_reference: str
    rules: tuple[CaptacionesCAPFProductRule, ...]

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("CAPF product policy code is required")
        if not self.version.strip():
            raise ValueError("CAPF product policy version is required")
        if not self.evidence_reference.strip():
            raise ValueError("CAPF product policy evidence_reference is required")
        if not self.rate_type_evidence_reference.strip():
            raise ValueError("CAPF rate type evidence_reference is required")
        product_codes = tuple(rule.product_code for rule in self.rules)
        if len(product_codes) != len(set(product_codes)):
            raise ValueError("CAPF product policy product codes must be unique")

    @property
    def reference(self) -> str:
        return f"{self.code}@{self.version}|{self.evidence_reference}"

    def resolve(self, product_code: str) -> CaptacionesCAPFProductRule | None:
        canonical = product_code.strip()
        if product_code != canonical:
            raise ValueError("CAPF product code must be canonical text")
        return next((rule for rule in self.rules if rule.product_code == canonical), None)

    def rule_reference(self, rule: CaptacionesCAPFProductRule) -> str:
        return f"{self.reference}|product={rule.product_code}|{rule.evidence_reference}"


INSTITUTIONAL_CAPF_PRODUCT_POLICY = CaptacionesCAPFProductPolicy(
    code="IRRBB-CAPF-PRODUCT-SEMANTICS",
    version="1",
    evidence_reference="AIP-Enterprise#66:comment-5790723728",
    contractual_rate_type=RateType.FIXED,
    rate_type_evidence_reference="INSTITUTIONAL-RULE:ALL-CAP-FIXED-RATE",
    rules=(
        CaptacionesCAPFProductRule(
            product_code="346",
            capitalizes_at_interest_payment_frequency=True,
            evidence_reference="INSTITUTIONAL-RULE:CAPF-346-CAPITALIZATION-FREQUENCY",
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class CaptacionesCAPFContractualFact:
    """Source-faithful CAPF evidence before any XML operation join or scheduling."""

    source_record_id: str
    source_reference: str
    certificate_number: str
    source_status_code: str
    product_code: str
    product_name: str
    currency_source_label: str
    certificate_amount_colonized: Decimal
    interest_rate_percent: Decimal
    contractual_rate_type: RateType
    rate_type_rule_reference: str
    preferential_rate_percent: Decimal | None
    term_months: int
    issue_date: date
    maturity_date: date
    explicit_payment_date: date | None
    interest_payment_frequency_source_label: str
    renewal_indicator_source_code: str
    renewal_amount_source_value: Decimal | None
    capitalizes_at_interest_payment_frequency: bool
    capitalization_frequency_source_label: str | None
    product_rule_reference: str | None

    def __post_init__(self) -> None:
        for field_name, value in (
            ("source_record_id", self.source_record_id),
            ("source_reference", self.source_reference),
            ("certificate_number", self.certificate_number),
            ("source_status_code", self.source_status_code),
            ("product_code", self.product_code),
            ("product_name", self.product_name),
            ("currency_source_label", self.currency_source_label),
            (
                "interest_payment_frequency_source_label",
                self.interest_payment_frequency_source_label,
            ),
            ("renewal_indicator_source_code", self.renewal_indicator_source_code),
            ("rate_type_rule_reference", self.rate_type_rule_reference),
        ):
            if not value.strip():
                raise ValueError(f"CAPF contractual {field_name} is required")
        if self.certificate_amount_colonized < 0:
            raise ValueError("CAPF colonized certificate amount cannot be negative")
        if self.interest_rate_percent < 0:
            raise ValueError("CAPF interest rate cannot be negative")
        if self.preferential_rate_percent is not None and self.preferential_rate_percent < 0:
            raise ValueError("CAPF preferential rate cannot be negative")
        if self.term_months <= 0:
            raise ValueError("CAPF term_months must be positive")
        if self.maturity_date < self.issue_date:
            raise ValueError("CAPF maturity_date cannot precede issue_date")
        if self.capitalizes_at_interest_payment_frequency:
            if not self.capitalization_frequency_source_label:
                raise ValueError("capitalizable CAPF requires its source frequency")
            if not self.product_rule_reference:
                raise ValueError("capitalizable CAPF requires its product rule reference")
        elif self.capitalization_frequency_source_label is not None:
            raise ValueError("non-capitalizable CAPF cannot expose capitalization frequency")


CaptacionesCAPFNormalizationResult: TypeAlias = (
    CaptacionesCAPFContractualFact | IRRBBSourceMappingFailure
)


@dataclass(frozen=True, slots=True)
class CaptacionesCAPFContractualBatchResult:
    cutoff_date: date
    source_file_name: str
    source_sha256: str
    source_record_count: int
    normalized_facts: tuple[CaptacionesCAPFContractualFact, ...]
    mapping_failures: tuple[IRRBBSourceMappingFailure, ...]

    def __post_init__(self) -> None:
        if PurePath(self.source_file_name).suffix.casefold() != ".xlsx":
            raise ValueError("CAPF contractual production source must be an XLSX workbook")
        if len(self.source_sha256) != 64:
            raise ValueError("CAPF contractual source_sha256 must be a SHA-256 hex digest")
        try:
            int(self.source_sha256, 16)
        except ValueError as exc:
            raise ValueError("CAPF contractual source_sha256 must be hexadecimal") from exc
        if len(self.normalized_facts) + len(self.mapping_failures) != self.source_record_count:
            raise ValueError("every CAPF workbook row must have one normalization outcome")
        ids = tuple(item.source_record_id for item in self.normalized_facts) + tuple(
            item.source_record_id for item in self.mapping_failures
        )
        if len(ids) != len(set(ids)):
            raise ValueError("CAPF contractual outcomes must have unique source_record_id")


class CaptacionesCAPFContractualNormalizer:
    """Normalize workbook row evidence without inventing joins, dates or cash flows."""

    def __init__(self, *, product_policy: CaptacionesCAPFProductPolicy) -> None:
        self._product_policy = product_policy

    def normalize(
        self,
        *,
        source_record_id: str,
        source_reference: str,
        values: Mapping[str, Any],
    ) -> CaptacionesCAPFNormalizationResult:
        try:
            certificate_number = self._required_text(values, "Número Certificado")
            status = self._required_text(values, "Estado")
            product_code, product_name = self._product(
                self._required_text(values, "Tipo de Certificado")
            )
            currency_label = self._required_text(values, "Moneda")
            amount = self._required_decimal(values, "Monto Certificado Colonizado")
            interest_rate = self._required_decimal(values, "Tasa Interés")
            preferential_rate = self._optional_decimal(values, "Tasa Preferencial")
            term_months = self._required_positive_int(values, "Plazo Meses")
            issue_date = self._required_date(values, "Fecha Emisión")
            maturity_date = self._required_date(values, "Fecha Vencimiento")
            payment_date = self._optional_date(values, "Fecha Pago")
            frequency = self._required_text(values, "Frecuencia Pago Intereses")
            renewal_indicator = self._required_text(values, "Indica Renovación")
            renewal_amount = (
                self._optional_decimal(values, "Monto Renovación")
                if renewal_indicator.casefold() == "s"
                else None
            )
        except _CAPFFieldError as exc:
            return self._failure(
                source_record_id,
                source_reference,
                code=exc.code,
                canonical_field=exc.field,
                message=exc.message,
            )

        rule = self._product_policy.resolve(product_code)
        capitalizes = bool(rule and rule.capitalizes_at_interest_payment_frequency)
        rule_reference = self._product_policy.rule_reference(rule) if rule else None

        try:
            return CaptacionesCAPFContractualFact(
                source_record_id=source_record_id,
                source_reference=source_reference,
                certificate_number=certificate_number,
                source_status_code=status,
                product_code=product_code,
                product_name=product_name,
                currency_source_label=currency_label,
                certificate_amount_colonized=amount,
                interest_rate_percent=interest_rate,
                contractual_rate_type=self._product_policy.contractual_rate_type,
                rate_type_rule_reference=(
                    f"{self._product_policy.reference}|"
                    f"{self._product_policy.rate_type_evidence_reference}"
                ),
                preferential_rate_percent=preferential_rate,
                term_months=term_months,
                issue_date=issue_date,
                maturity_date=maturity_date,
                explicit_payment_date=payment_date,
                interest_payment_frequency_source_label=frequency,
                renewal_indicator_source_code=renewal_indicator,
                renewal_amount_source_value=renewal_amount,
                capitalizes_at_interest_payment_frequency=capitalizes,
                capitalization_frequency_source_label=frequency if capitalizes else None,
                product_rule_reference=rule_reference,
            )
        except ValueError as exc:
            return self._failure(
                source_record_id,
                source_reference,
                code=IRRBBSourceMappingFailureCode.INVALID_CANONICAL_VALUE,
                canonical_field="contractual_fact",
                message=str(exc),
            )

    @classmethod
    def normalize_batch(
        cls,
        *,
        cutoff_date: date,
        source_file_name: str,
        source_sha256: str,
        rows: Iterable[Mapping[str, Any]],
        product_policy: CaptacionesCAPFProductPolicy,
    ) -> CaptacionesCAPFContractualBatchResult:
        if PurePath(source_file_name).suffix.casefold() != ".xlsx":
            raise ValueError("CAPF contractual production source must be an XLSX workbook")

        normalizer = cls(product_policy=product_policy)
        outcomes: list[CaptacionesCAPFNormalizationResult] = []
        for row_number, values in enumerate(rows, start=2):
            source_record_id = f"CAPF_XLSX:{source_file_name}:row:{row_number}"
            source_reference = (
                f"CAPF_XLSX:{source_file_name}|sha256={source_sha256}|row={row_number}"
            )
            outcomes.append(
                normalizer.normalize(
                    source_record_id=source_record_id,
                    source_reference=source_reference,
                    values=values,
                )
            )

        certificate_counts = Counter(
            outcome.certificate_number
            for outcome in outcomes
            if isinstance(outcome, CaptacionesCAPFContractualFact)
        )
        duplicate_certificates = {
            certificate for certificate, count in certificate_counts.items() if count > 1
        }
        facts: list[CaptacionesCAPFContractualFact] = []
        failures: list[IRRBBSourceMappingFailure] = []
        for outcome in outcomes:
            if isinstance(outcome, IRRBBSourceMappingFailure):
                failures.append(outcome)
            elif outcome.certificate_number in duplicate_certificates:
                failures.append(
                    cls._failure(
                        outcome.source_record_id,
                        outcome.source_reference,
                        code=IRRBBSourceMappingFailureCode.SOURCE_RECORD_REJECTED,
                        canonical_field="certificate_number",
                        message=(
                            "Duplicate Número Certificado in the contractual workbook; "
                            "no XML join or cash-flow scheduling is permitted."
                        ),
                    )
                )
            else:
                facts.append(outcome)

        return CaptacionesCAPFContractualBatchResult(
            cutoff_date=cutoff_date,
            source_file_name=source_file_name,
            source_sha256=source_sha256,
            source_record_count=len(outcomes),
            normalized_facts=tuple(facts),
            mapping_failures=tuple(failures),
        )

    @classmethod
    def _required_text(cls, values: Mapping[str, Any], field: str) -> str:
        value = cls._source_value(values, field)
        text = str(value).strip() if value is not None else ""
        if text:
            return text
        raise _CAPFFieldError(
            IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD,
            field,
            f"Required CAPF workbook field {field} is missing.",
        )

    @classmethod
    def _required_decimal(cls, values: Mapping[str, Any], field: str) -> Decimal:
        value = cls._source_value(values, field)
        parsed = cls._decimal(value)
        if parsed is not None:
            return parsed
        code = (
            IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD
            if value is None or not str(value).strip()
            else IRRBBSourceMappingFailureCode.INVALID_CANONICAL_VALUE
        )
        raise _CAPFFieldError(code, field, f"CAPF workbook field {field} must be numeric.")

    @classmethod
    def _optional_decimal(cls, values: Mapping[str, Any], field: str) -> Decimal | None:
        value = cls._source_value(values, field)
        if value is None or not str(value).strip():
            return None
        parsed = cls._decimal(value)
        if parsed is None:
            raise _CAPFFieldError(
                IRRBBSourceMappingFailureCode.INVALID_CANONICAL_VALUE,
                field,
                f"CAPF workbook field {field} must be numeric when present.",
            )
        return parsed

    @classmethod
    def _required_positive_int(cls, values: Mapping[str, Any], field: str) -> int:
        value = cls._required_decimal(values, field)
        if value <= 0 or value != value.to_integral_value():
            raise _CAPFFieldError(
                IRRBBSourceMappingFailureCode.INVALID_CANONICAL_VALUE,
                field,
                f"CAPF workbook field {field} must be a positive whole number.",
            )
        return int(value)

    @classmethod
    def _required_date(cls, values: Mapping[str, Any], field: str) -> date:
        value = cls._source_value(values, field)
        parsed = cls._date(value)
        if parsed is not None:
            return parsed
        code = (
            IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD
            if value is None or not str(value).strip()
            else IRRBBSourceMappingFailureCode.INVALID_CANONICAL_VALUE
        )
        raise _CAPFFieldError(code, field, f"CAPF workbook field {field} must be a date.")

    @classmethod
    def _optional_date(cls, values: Mapping[str, Any], field: str) -> date | None:
        value = cls._source_value(values, field)
        if value is None or not str(value).strip():
            return None
        parsed = cls._date(value)
        if parsed is None:
            raise _CAPFFieldError(
                IRRBBSourceMappingFailureCode.INVALID_CANONICAL_VALUE,
                field,
                f"CAPF workbook field {field} must be a date when present.",
            )
        return parsed

    @staticmethod
    def _source_value(values: Mapping[str, Any], field: str) -> Any:
        matches = [value for header, value in values.items() if str(header).strip() == field]
        if not matches:
            return None
        if len(matches) > 1 and len({str(value) for value in matches}) > 1:
            raise _CAPFFieldError(
                IRRBBSourceMappingFailureCode.SOURCE_RECORD_REJECTED,
                field,
                f"Conflicting CAPF workbook headers normalize to {field}.",
            )
        return matches[0]

    @staticmethod
    def _product(value: str) -> tuple[str, str]:
        code, separator, name = value.partition("-")
        if separator and code.strip().isdigit() and name.strip():
            return code.strip(), name.strip()
        raise _CAPFFieldError(
            IRRBBSourceMappingFailureCode.INVALID_CANONICAL_VALUE,
            "Tipo de Certificado",
            "CAPF Tipo de Certificado must contain an explicit numeric code and name.",
        )

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            return Decimal(str(value).strip())
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _date(value: Any) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if not isinstance(value, str) or not value.strip():
            return None
        raw = value.strip()
        for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(raw, pattern).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _failure(
        source_record_id: str,
        source_reference: str,
        *,
        code: IRRBBSourceMappingFailureCode,
        canonical_field: str,
        message: str,
    ) -> IRRBBSourceMappingFailure:
        return IRRBBSourceMappingFailure(
            source_record_id=source_record_id,
            source_reference=source_reference,
            code=code,
            canonical_field=canonical_field,
            message=message,
        )


class _CAPFFieldError(ValueError):
    def __init__(
        self,
        code: IRRBBSourceMappingFailureCode,
        field: str,
        message: str,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.field = field
        self.message = message
