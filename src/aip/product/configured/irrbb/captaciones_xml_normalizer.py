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
class CaptacionesXMLFact:
    """Source-faithful Captaciones fact before canonical IRRBB classification."""

    source_record_id: str
    source_reference: str
    creditor_id: str
    operation_id: str
    operation_type_source_code: str
    guarantee_indicator: str | None
    currency_source_code: str
    rate_type_source_code: str
    variable_rate_source_code: str | None
    nominal_rate_percent: Decimal | None
    sugef_catalog_source_code: str | None
    accounting_account_code: str
    principal_amount: Decimal
    product_account_code: str | None
    product_amount: Decimal
    origination_date: date | None
    maturity_date: date | None
    reserve_requirement_indicator: str | None
    account_type_source_code: str
    deposit_fgd_source_code: str | None

    @property
    def total_balance(self) -> Decimal:
        return self.principal_amount + self.product_amount


CaptacionesXMLNormalizationResult: TypeAlias = CaptacionesXMLFact | IRRBBSourceMappingFailure


class CaptacionesXMLNormalizer:
    """Normalize one Pasivos 210 row without inventing product semantics."""

    def normalize(
        self,
        record: IRRBBSourceRecordEnvelope[XMLConfiaRecord],
    ) -> CaptacionesXMLNormalizationResult:
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
        account_type = self._required_text(record, values, "TipoCuenta")
        if isinstance(account_type, IRRBBSourceMappingFailure):
            return account_type

        principal = self._required_decimal(record, values, "SaldoPrincipal")
        if isinstance(principal, IRRBBSourceMappingFailure):
            return principal
        product = self._required_decimal(record, values, "SaldoProducto")
        if isinstance(product, IRRBBSourceMappingFailure):
            return product
        if principal < 0 or product < 0:
            return self._failure(
                record,
                code=IRRBBSourceMappingFailureCode.INVALID_CANONICAL_VALUE,
                field="principal/product",
                message="Captaciones principal and product balances must be non-negative.",
            )

        nominal_rate = self._optional_decimal(record, values, "Tasa")
        if isinstance(nominal_rate, IRRBBSourceMappingFailure):
            return nominal_rate
        origination = self._optional_date(record, values, "FechaFormalizacion")
        if isinstance(origination, IRRBBSourceMappingFailure):
            return origination
        maturity = self._optional_date(record, values, "FechaVencimiento")
        if isinstance(maturity, IRRBBSourceMappingFailure):
            return maturity

        return CaptacionesXMLFact(
            source_record_id=record.source_record_id,
            source_reference=record.source_reference,
            creditor_id=creditor_id,
            operation_id=operation_id,
            operation_type_source_code=operation_type,
            guarantee_indicator=self._optional_text(values, "IndicadorRecibidoGarantia"),
            currency_source_code=currency,
            rate_type_source_code=rate_type,
            variable_rate_source_code=self._optional_text(values, "TipoTasaVariable"),
            nominal_rate_percent=nominal_rate,
            sugef_catalog_source_code=self._optional_text(values, "TipoCatalogoSUGEF"),
            accounting_account_code=account,
            principal_amount=principal,
            product_account_code=self._optional_text(values, "CuentaContableProductos"),
            product_amount=product,
            origination_date=origination,
            maturity_date=maturity,
            reserve_requirement_indicator=self._optional_text(values, "IndicadorSujetoEncaje"),
            account_type_source_code=account_type,
            deposit_fgd_source_code=self._optional_text(values, "TipoDepositoFGDLEY9816"),
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
            message=f"Required Captaciones XML field {field} is missing.",
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
                message=f"Required Captaciones XML field {field} is missing.",
            )
        try:
            return Decimal(raw)
        except InvalidOperation:
            return cls._failure(
                record,
                code=IRRBBSourceMappingFailureCode.INVALID_CANONICAL_VALUE,
                field=field,
                message=f"Captaciones XML field {field} must be decimal text.",
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
                message=f"Captaciones XML field {field} must be decimal text when present.",
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
                message=f"Captaciones XML field {field} must use DD/MM/YYYY.",
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
