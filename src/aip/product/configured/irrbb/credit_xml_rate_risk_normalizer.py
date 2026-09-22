from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import TypeAlias

from aip.application.irrbb import (
    IRRBBSourceExclusion,
    IRRBBSourceMappingFailure,
    IRRBBSourceMappingFailureCode,
)
from aip.product.configured.irrbb.source_acl import IRRBBSourceRecordEnvelope
from aip.product.configured.irrbb.xml_confia_source import XMLConfiaRecord

CREDIT_XML_RULE_VARIABLE_R1 = "CREDIT_VARIABLE_R1"
CREDIT_XML_RULE_FIXED_MATURITY = "CREDIT_FIXED_MATURITY"
CREDIT_XML_RULE_FV_CHANGE_DATE = "CREDIT_FV_CHANGE_DATE"
CREDIT_XML_RULE_MORA_EXCLUDE = "CREDIT_MORA_EXCLUDE"
CREDIT_XML_RULE_JUDICIAL_EXCLUDE = "CREDIT_JUDICIAL_EXCLUDE"
CREDIT_XML_RULE_REFERENCE = "SICVECA-205:2026-09-22:v2.0:CREDIT"


@dataclass(frozen=True, slots=True)
class CreditXMLRateRiskFact:
    """Normalized credit fact before currency/canonical IRRBB mapping.

    Source currency codes are deliberately retained verbatim. The source-specific
    rule engine determines the SICVECA sensitive-date rule without inventing a
    19-band RTILB date for variable loans whose approved rule only states R1.
    """

    source_record_id: str
    source_reference: str
    operation_id: str
    currency_source_code: str
    accounting_account_code: str
    principal_amount: Decimal
    product_amount: Decimal
    days_past_due: int
    rate_indicator: str
    nominal_rate_percent: Decimal | None
    origination_date: date | None
    maturity_date: date | None
    next_interest_payment_date: date | None
    rate_change_date: date | None
    repricing_frequency_source_code: str | None
    rule_code: str
    sensitive_date: date | None
    sicveca_bucket_hint: int | None

    @property
    def total_gap_amount(self) -> Decimal:
        return self.principal_amount + self.product_amount


CreditXMLNormalizationResult: TypeAlias = (
    CreditXMLRateRiskFact | IRRBBSourceExclusion | IRRBBSourceMappingFailure
)


class CreditXMLRateRiskNormalizer:
    """Apply the audited SICVECA credit rules to one XML CONFÍA source record."""

    _ELIGIBLE_ACCOUNT_PREFIXES = ("131", "132", "134", "137")
    _JUDICIAL_ACCOUNT_PREFIX = "133"

    def normalize(
        self,
        record: IRRBBSourceRecordEnvelope[XMLConfiaRecord],
        *,
        cutoff_date: date,
    ) -> CreditXMLNormalizationResult:
        values = record.payload.values

        operation_id = self._required_text(record, values, "IdOperacionCredito")
        if isinstance(operation_id, IRRBBSourceMappingFailure):
            return operation_id

        account = self._required_text(record, values, "CuentaContablePrincipal")
        if isinstance(account, IRRBBSourceMappingFailure):
            return account

        days_past_due = self._required_int(record, values, "DiasMaximaMorosidad")
        if isinstance(days_past_due, IRRBBSourceMappingFailure):
            return days_past_due

        if days_past_due > 30:
            return IRRBBSourceExclusion(
                source_record_id=record.source_record_id,
                source_reference=record.source_reference,
                reason_code=CREDIT_XML_RULE_MORA_EXCLUDE,
                message="Credit operation excluded because maximum delinquency exceeds 30 days.",
                rule_reference=CREDIT_XML_RULE_REFERENCE,
            )

        if account.startswith(self._JUDICIAL_ACCOUNT_PREFIX):
            return IRRBBSourceExclusion(
                source_record_id=record.source_record_id,
                source_reference=record.source_reference,
                reason_code=CREDIT_XML_RULE_JUDICIAL_EXCLUDE,
                message="Credit operation excluded because accounting account 133 is judicial.",
                rule_reference=CREDIT_XML_RULE_REFERENCE,
            )

        if not account.startswith(self._ELIGIBLE_ACCOUNT_PREFIXES):
            return self._failure(
                record,
                code=IRRBBSourceMappingFailureCode.UNSUPPORTED_SOURCE_VALUE,
                field="CuentaContablePrincipal",
                message=f"Unsupported eligible credit account: {account}.",
            )

        currency_code = self._required_text(record, values, "TipoMonedaOperacion")
        if isinstance(currency_code, IRRBBSourceMappingFailure):
            return currency_code

        principal = self._required_decimal(record, values, "SaldoPrincipalOperacionCrediticia")
        if isinstance(principal, IRRBBSourceMappingFailure):
            return principal
        product = self._required_decimal(record, values, "SaldoProductosPorCobrar")
        if isinstance(product, IRRBBSourceMappingFailure):
            return product
        if principal < 0 or product < 0:
            return self._failure(
                record,
                code=IRRBBSourceMappingFailureCode.INVALID_CANONICAL_VALUE,
                field="principal/product",
                message="Credit principal and product balances must be non-negative.",
            )

        rate_indicator = self._required_text(record, values, "IndicadorTipoTasa")
        if isinstance(rate_indicator, IRRBBSourceMappingFailure):
            return rate_indicator
        rate_indicator = rate_indicator.upper()
        if rate_indicator not in {"V", "F", "FV"}:
            return self._failure(
                record,
                code=IRRBBSourceMappingFailureCode.UNSUPPORTED_SOURCE_VALUE,
                field="IndicadorTipoTasa",
                message=f"Unsupported credit rate indicator: {rate_indicator}.",
            )

        nominal_rate = self._optional_decimal(record, values, "TasaInteresNominalVigente")
        if isinstance(nominal_rate, IRRBBSourceMappingFailure):
            return nominal_rate

        origination = self._optional_date(record, values, "FechaFormalizacion")
        if isinstance(origination, IRRBBSourceMappingFailure):
            return origination
        maturity = self._optional_date(record, values, "FechaVencimiento")
        if isinstance(maturity, IRRBBSourceMappingFailure):
            return maturity
        next_interest = self._optional_date(record, values, "FechaProximoPagoIntereses")
        if isinstance(next_interest, IRRBBSourceMappingFailure):
            return next_interest
        rate_change = self._optional_date(record, values, "FechaCambioTipoTasa")
        if isinstance(rate_change, IRRBBSourceMappingFailure):
            return rate_change

        frequency = (values.get("TipoFrecuenciaAjusteTasaInteresVariable") or "").strip() or None

        rule_code: str
        sensitive_date: date | None
        bucket_hint: int | None
        if rate_indicator == "V":
            rule_code = CREDIT_XML_RULE_VARIABLE_R1
            sensitive_date = None
            bucket_hint = 1
        elif rate_indicator == "F":
            if maturity is None:
                return self._missing_sensitive_date(record, "FechaVencimiento", rate_indicator)
            rule_code = CREDIT_XML_RULE_FIXED_MATURITY
            sensitive_date = maturity
            bucket_hint = None
        else:
            if rate_change is None:
                return self._missing_sensitive_date(record, "FechaCambioTipoTasa", rate_indicator)
            rule_code = CREDIT_XML_RULE_FV_CHANGE_DATE
            sensitive_date = rate_change
            bucket_hint = None

        if sensitive_date is not None and sensitive_date < cutoff_date:
            return self._failure(
                record,
                code=IRRBBSourceMappingFailureCode.INVALID_CANONICAL_VALUE,
                field="sensitive_date",
                message=(
                    f"Audited credit sensitive date {sensitive_date.isoformat()} "
                    f"is before cutoff {cutoff_date.isoformat()}."
                ),
            )

        return CreditXMLRateRiskFact(
            source_record_id=record.source_record_id,
            source_reference=record.source_reference,
            operation_id=operation_id,
            currency_source_code=currency_code,
            accounting_account_code=account,
            principal_amount=principal,
            product_amount=product,
            days_past_due=days_past_due,
            rate_indicator=rate_indicator,
            nominal_rate_percent=nominal_rate,
            origination_date=origination,
            maturity_date=maturity,
            next_interest_payment_date=next_interest,
            rate_change_date=rate_change,
            repricing_frequency_source_code=frequency,
            rule_code=rule_code,
            sensitive_date=sensitive_date,
            sicveca_bucket_hint=bucket_hint,
        )

    @classmethod
    def _required_text(
        cls,
        record: IRRBBSourceRecordEnvelope[XMLConfiaRecord],
        values: dict[str, str],
        field: str,
    ) -> str | IRRBBSourceMappingFailure:
        value = (values.get(field) or "").strip()
        if value:
            return value
        return cls._failure(
            record,
            code=IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD,
            field=field,
            message=f"Required credit XML field {field} is missing.",
        )

    @classmethod
    def _required_int(
        cls,
        record: IRRBBSourceRecordEnvelope[XMLConfiaRecord],
        values: dict[str, str],
        field: str,
    ) -> int | IRRBBSourceMappingFailure:
        raw = (values.get(field) or "").strip()
        if not raw:
            return cls._failure(
                record,
                code=IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD,
                field=field,
                message=f"Required credit XML field {field} is missing.",
            )
        try:
            return int(raw)
        except ValueError:
            return cls._failure(
                record,
                code=IRRBBSourceMappingFailureCode.INVALID_CANONICAL_VALUE,
                field=field,
                message=f"Credit XML field {field} must be an integer.",
            )

    @classmethod
    def _required_decimal(
        cls,
        record: IRRBBSourceRecordEnvelope[XMLConfiaRecord],
        values: dict[str, str],
        field: str,
    ) -> Decimal | IRRBBSourceMappingFailure:
        raw = (values.get(field) or "").strip()
        if not raw:
            return cls._failure(
                record,
                code=IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD,
                field=field,
                message=f"Required credit XML field {field} is missing.",
            )
        try:
            return Decimal(raw)
        except InvalidOperation:
            return cls._failure(
                record,
                code=IRRBBSourceMappingFailureCode.INVALID_CANONICAL_VALUE,
                field=field,
                message=f"Credit XML field {field} must be decimal text.",
            )

    @classmethod
    def _optional_decimal(
        cls,
        record: IRRBBSourceRecordEnvelope[XMLConfiaRecord],
        values: dict[str, str],
        field: str,
    ) -> Decimal | None | IRRBBSourceMappingFailure:
        raw = (values.get(field) or "").strip()
        if not raw:
            return None
        try:
            return Decimal(raw)
        except InvalidOperation:
            return cls._failure(
                record,
                code=IRRBBSourceMappingFailureCode.INVALID_CANONICAL_VALUE,
                field=field,
                message=f"Credit XML field {field} must be decimal text when present.",
            )

    @classmethod
    def _optional_date(
        cls,
        record: IRRBBSourceRecordEnvelope[XMLConfiaRecord],
        values: dict[str, str],
        field: str,
    ) -> date | None | IRRBBSourceMappingFailure:
        raw = (values.get(field) or "").strip()
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%d/%m/%Y").date()
        except ValueError:
            return cls._failure(
                record,
                code=IRRBBSourceMappingFailureCode.INVALID_CANONICAL_VALUE,
                field=field,
                message=f"Credit XML field {field} must use DD/MM/YYYY.",
            )

    @classmethod
    def _missing_sensitive_date(
        cls,
        record: IRRBBSourceRecordEnvelope[XMLConfiaRecord],
        field: str,
        rate_indicator: str,
    ) -> IRRBBSourceMappingFailure:
        return cls._failure(
            record,
            code=IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD,
            field=field,
            message=(
                f"Credit rate indicator {rate_indicator} requires {field} "
                "to determine the audited sensitive date."
            ),
        )

    @staticmethod
    def _failure(
        record: IRRBBSourceRecordEnvelope[XMLConfiaRecord],
        *,
        code: IRRBBSourceMappingFailureCode,
        field: str | None,
        message: str,
    ) -> IRRBBSourceMappingFailure:
        return IRRBBSourceMappingFailure(
            source_record_id=record.source_record_id,
            source_reference=record.source_reference,
            code=code,
            canonical_field=field,
            message=message,
        )
