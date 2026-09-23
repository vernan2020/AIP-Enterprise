from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import TypeAlias

from aip.application.irrbb import (
    IRRBBSourceMappingFailure,
    IRRBBSourceMappingFailureCode,
)
from aip.product.configured.irrbb.source_acl import IRRBBSourceRecordEnvelope
from aip.product.configured.irrbb.xml_confia_source import XMLConfiaRecord


@dataclass(frozen=True, slots=True)
class BorrowingXMLFact:
    """Source-faithful Obligaciones fact before canonical IRRBB classification."""

    source_record_id: str
    source_reference: str
    creditor_id: str
    operation_id: str
    operation_type_source_code: str
    guarantee_indicator: str | None
    currency_source_code: str
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
    principal_amount: Decimal
    contracted_amount: Decimal | None
    product_account_code: str | None
    product_amount: Decimal | None
    origination_date: date | None
    maturity_date: date | None
    next_principal_payment_date: date | None
    next_interest_payment_date: date | None
    principal_payment_frequency_source_code: str | None
    interest_payment_frequency_source_code: str | None


BorrowingXMLNormalizationResult: TypeAlias = BorrowingXMLFact | IRRBBSourceMappingFailure


class BorrowingXMLNormalizer:
    """Normalize one governed Obligaciones XML record without financial inference.

    Signed balances and optional blanks are preserved. This layer does not decide
    account inclusion, canonical currency/rate semantics, repricing, or 19-band
    assignment.
    """

    def normalize(
        self,
        record: IRRBBSourceRecordEnvelope[XMLConfiaRecord],
    ) -> BorrowingXMLNormalizationResult:
        values = record.payload.values

        creditor_id = self._required_text(record, values, "IdAcreedor")
        if isinstance(creditor_id, IRRBBSourceMappingFailure):
            return creditor_id
        operation_id = self._required_text(record, values, "IdOperacion")
        if isinstance(operation_id, IRRBBSourceMappingFailure):
            return operation_id
        operation_type = self._required_text(record, values, "TipoOperacionObligaciones")
        if isinstance(operation_type, IRRBBSourceMappingFailure):
            return operation_type
        currency = self._required_text(record, values, "TipoMonedaObligacion")
        if isinstance(currency, IRRBBSourceMappingFailure):
            return currency
        rate_type = self._required_text(record, values, "TipoTasa")
        if isinstance(rate_type, IRRBBSourceMappingFailure):
            return rate_type
        account = self._required_text(record, values, "CuentaContablePrincipal")
        if isinstance(account, IRRBBSourceMappingFailure):
            return account
        principal = self._required_decimal(record, values, "SaldoPrincipal")
        if isinstance(principal, IRRBBSourceMappingFailure):
            return principal

        optional_decimals: dict[str, Decimal | None] = {}
        for field in ("Tasa", "MontoContratado", "SaldoProducto"):
            value = self._optional_decimal(record, values, field)
            if isinstance(value, IRRBBSourceMappingFailure):
                return value
            optional_decimals[field] = value

        optional_dates: dict[str, date | None] = {}
        for field in (
            "FechaFormalizacion",
            "FechaVencimiento",
            "FechaProximoPagoPrincipal",
            "FechaProximoPagoInteres",
        ):
            value = self._optional_date(record, values, field)
            if isinstance(value, IRRBBSourceMappingFailure):
                return value
            optional_dates[field] = value

        return BorrowingXMLFact(
            source_record_id=record.source_record_id,
            source_reference=record.source_reference,
            creditor_id=creditor_id,
            operation_id=operation_id,
            operation_type_source_code=operation_type,
            guarantee_indicator=self._optional_text(values, "IndicadorRecibidoGarantia"),
            currency_source_code=currency,
            obligation_indicator=self._optional_text(values, "IndicadorObligacion"),
            revolving_indicator=self._optional_text(values, "IndicadorRevolutiva"),
            credit_line_id=self._optional_text(values, "IdLineaCredito"),
            conditional_indicator=self._optional_text(values, "IndicadorCondicional"),
            country_source_code=self._optional_text(values, "PaisOrigen"),
            contract_currency_source_code=self._optional_text(values, "TipoMonedaContrato"),
            disbursement_currency_source_code=self._optional_text(
                values, "TipoMonedaDesembolso"
            ),
            rate_type_source_code=rate_type,
            variable_rate_source_code=self._optional_text(values, "TipoTasaVariable"),
            nominal_rate_percent=optional_decimals["Tasa"],
            sugef_catalog_source_code=self._optional_text(values, "TipoCatalogoSUGEF"),
            accounting_account_code=account,
            principal_amount=principal,
            contracted_amount=optional_decimals["MontoContratado"],
            product_account_code=self._optional_text(values, "CuentaContableProductos"),
            product_amount=optional_decimals["SaldoProducto"],
            origination_date=optional_dates["FechaFormalizacion"],
            maturity_date=optional_dates["FechaVencimiento"],
            next_principal_payment_date=optional_dates["FechaProximoPagoPrincipal"],
            next_interest_payment_date=optional_dates["FechaProximoPagoInteres"],
            principal_payment_frequency_source_code=self._optional_text(
                values, "FrecuenciaPagoActualPrincipal"
            ),
            interest_payment_frequency_source_code=self._optional_text(
                values, "FrecuenciaPagoActualIntereses"
            ),
        )

    @staticmethod
    def _optional_text(values: dict[str, str], field: str) -> str | None:
        return (values.get(field) or "").strip() or None

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
            message=f"Required Obligaciones XML field {field} is missing.",
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
                message=f"Required Obligaciones XML field {field} is missing.",
            )
        try:
            return Decimal(raw)
        except InvalidOperation:
            return cls._failure(
                record,
                code=IRRBBSourceMappingFailureCode.INVALID_CANONICAL_VALUE,
                field=field,
                message=f"Obligaciones XML field {field} must be decimal text.",
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
                message=f"Obligaciones XML field {field} must be decimal text when present.",
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
                message=f"Obligaciones XML field {field} must use DD/MM/YYYY.",
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
