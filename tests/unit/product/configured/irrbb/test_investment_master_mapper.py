from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.application.irrbb.contracts import (
    IRRBBPositionSourceRecord,
    IRRBBSourceMappingFailure,
    IRRBBSourceMappingFailureCode,
)
from aip.domain.irrbb.models import (
    BankingBookSide,
    IRRBBInstrumentClass,
    OptionalityType,
    PaymentStructure,
    RateType,
)
from aip.product.configured.irrbb.investment_master_mapper import (
    InstitutionalInvestmentMasterCanonicalMapper,
    InvestmentMasterCanonicalMappingPolicy,
    InvestmentMasterMappingRule,
    InvestmentMasterPrincipalField,
    InvestmentMasterSourcePayload,
)
from aip.product.configured.irrbb.source_acl import IRRBBSourceRecordEnvelope
from aip.shared.money import Currency


def _mapping() -> dict[str, str]:
    return {
        "contract_number": "Numero Contrato",
        "currency": "Moneda",
        "maturity_date": "Fecha Vencimiento",
        "product_code": "Codigo Producto",
        "classification": "Clasificacion",
        "series": "Serie",
        "isin": "ISIN",
        "traded_balance": "Saldo Valor Transado",
        "principal_balance": "Saldo Principal",
        "book_value": "Saldo Valor Compra",
        "nominal_rate": "Tasa Nominal",
        "periodicity": "Periodicidad",
        "last_interest_payment_date": "Fecha Ultimo Pago Intereses",
        "variable_rate_flag": "Indicador Tasa Variable",
    }


def _source_values() -> dict[str, str]:
    return {
        "numero contrato": "C-100",
        "moneda": "CRC",
        "fecha vencimiento": "2028-07-31",
        "codigo producto": "TP",
        "clasificacion": "FVOCI",
        "serie": "SER-100",
        "isin": "CR0000000100",
        "saldo valor transado": "900000",
        "saldo principal": "1000000",
        "saldo valor compra": "995000",
        "tasa nominal": "6.25",
        "periodicidad": "semestral",
        "fecha ultimo pago intereses": "2026-07-31",
        "indicador tasa variable": "N",
    }


def _position(**overrides: object) -> dict[str, object]:
    position: dict[str, object] = {
        "contract_number": "C-100",
        "currency": "CRC",
        "maturity_date": date(2028, 7, 31),
        "product_code": "TP",
        "classification": "FVOCI",
        "series": "SER-100",
        "isin": "CR0000000100",
        "traded_balance": 900_000.0,
        "principal_balance": 1_000_000.0,
        "book_value": 995_000.0,
        "nominal_rate": 6.25,
        "periodicity": "semestral",
        "last_interest_payment_date": date(2026, 7, 31),
        "variable_rate_flag": "N",
        "source_values": _source_values(),
    }
    position.update(overrides)
    return position


def _payload(
    *,
    position: dict[str, object] | None = None,
    mapping: dict[str, str] | None = None,
) -> InvestmentMasterSourcePayload:
    return InvestmentMasterSourcePayload(
        normalized_position=position if position is not None else _position(),
        detected_column_mapping=mapping if mapping is not None else _mapping(),
    )


def _envelope(payload: InvestmentMasterSourcePayload | None = None):
    return IRRBBSourceRecordEnvelope(
        source_record_id="row:7",
        source_reference="maestro_2026-07-31.xlsx#Maestro!7",
        payload=payload if payload is not None else _payload(),
    )


def _rule(
    *,
    classification: str | None = "FVOCI",
    principal_field: InvestmentMasterPrincipalField = (
        InvestmentMasterPrincipalField.PRINCIPAL_BALANCE
    ),
) -> InvestmentMasterMappingRule:
    return InvestmentMasterMappingRule(
        product_code="TP",
        classification=classification,
        instrument_class=IRRBBInstrumentClass.INVESTMENT,
        side=BankingBookSide.ASSET,
        payment_structure=PaymentStructure.BULLET,
        optionality=OptionalityType.NONE,
        principal_field=principal_field,
    )


def _policy(*rules: InvestmentMasterMappingRule) -> InvestmentMasterCanonicalMappingPolicy:
    return InvestmentMasterCanonicalMappingPolicy(
        code="RTILB-INV-MAPPING",
        version="2026.09.10",
        effective_from=date(2026, 9, 10),
        source_reference="POLICY:RTILB-INVESTMENT-MAPPING",
        rules=rules or (_rule(),),
    )


def _mapper(*rules: InvestmentMasterMappingRule) -> InstitutionalInvestmentMasterCanonicalMapper:
    return InstitutionalInvestmentMasterCanonicalMapper(_policy(*rules))


def test_fixed_rate_native_record_maps_without_using_domain_semantic_defaults() -> None:
    result = _mapper().map_record(_envelope())

    assert isinstance(result, IRRBBPositionSourceRecord)
    position = result.position
    assert position.position_id == "contract:C-100|isin:CR0000000100"
    assert position.product_type == "TP"
    assert position.side is BankingBookSide.ASSET
    assert position.instrument_class is IRRBBInstrumentClass.INVESTMENT
    assert position.payment_structure is PaymentStructure.BULLET
    assert position.optionality is OptionalityType.NONE
    assert position.currency is Currency.CRC
    assert position.principal.amount == Decimal("1000000.0")
    assert position.carrying_amount is not None
    assert position.carrying_amount.amount == Decimal("995000.0")
    assert position.rate_type is RateType.FIXED
    assert position.contractual_rate == Decimal("6.25")
    assert position.payment_frequency_months == 6
    assert position.next_repricing_date is None
    assert position.repricing_frequency_months is None
    assert result.mapping_rule_reference is not None
    assert "RTILB-INV-MAPPING@2026.09.10" in result.mapping_rule_reference
    assert "classification=FVOCI" in result.mapping_rule_reference


def test_policy_principal_field_is_authoritative_and_does_not_fallback() -> None:
    traded_rule = _rule(principal_field=InvestmentMasterPrincipalField.TRADED_BALANCE)
    result = _mapper(traded_rule).map_record(_envelope())

    assert isinstance(result, IRRBBPositionSourceRecord)
    assert result.position.principal.amount == Decimal("900000.0")

    position = _position(traded_balance=None)
    source_values = dict(position["source_values"])
    source_values["saldo valor transado"] = ""
    position["source_values"] = source_values
    failure = _mapper(traded_rule).map_record(_envelope(_payload(position=position)))

    assert isinstance(failure, IRRBBSourceMappingFailure)
    assert failure.canonical_field == "principal"
    assert failure.code is IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD


def test_normalized_crc_default_is_rejected_without_native_currency_evidence() -> None:
    position = _position(currency="CRC")
    source_values = dict(position["source_values"])
    source_values["moneda"] = ""
    position["source_values"] = source_values

    result = _mapper().map_record(_envelope(_payload(position=position)))

    assert isinstance(result, IRRBBSourceMappingFailure)
    assert result.canonical_field == "currency"
    assert result.code is IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD
    assert result.source_record_id == "row:7"
    assert result.source_reference == "maestro_2026-07-31.xlsx#Maestro!7"
    assert "CRC defaults are not accepted" in result.message


def test_unapproved_product_semantics_are_rejected_instead_of_defaulted() -> None:
    position = _position(product_code="UNKNOWN")
    source_values = dict(position["source_values"])
    source_values["codigo producto"] = "UNKNOWN"
    position["source_values"] = source_values

    result = _mapper().map_record(_envelope(_payload(position=position)))

    assert isinstance(result, IRRBBSourceMappingFailure)
    assert result.code is IRRBBSourceMappingFailureCode.UNSUPPORTED_SOURCE_VALUE
    assert result.canonical_field == "product_type"
    assert "No approved investment mapping rule" in result.message


def test_exact_classification_rule_precedes_explicit_product_fallback() -> None:
    fallback = _rule(classification=None)
    exact = InvestmentMasterMappingRule(
        product_code="TP",
        classification="FVOCI",
        instrument_class=IRRBBInstrumentClass.INVESTMENT,
        side=BankingBookSide.ASSET,
        payment_structure=PaymentStructure.EXPLICIT_SCHEDULE,
        optionality=OptionalityType.OTHER,
        principal_field=InvestmentMasterPrincipalField.PRINCIPAL_BALANCE,
    )

    result = _mapper(fallback, exact).map_record(_envelope())

    assert isinstance(result, IRRBBPositionSourceRecord)
    assert result.position.payment_structure is PaymentStructure.EXPLICIT_SCHEDULE
    assert result.position.optionality is OptionalityType.OTHER
    assert result.mapping_rule_reference is not None
    assert "classification=FVOCI" in result.mapping_rule_reference


def test_floating_coupon_proxy_fields_do_not_satisfy_contractual_reset_requirements() -> None:
    position = _position(variable_rate_flag="S", next_repricing_date=date(2026, 10, 31))
    source_values = dict(position["source_values"])
    source_values["indicador tasa variable"] = "S"
    position["source_values"] = source_values

    result = _mapper().map_record(_envelope(_payload(position=position)))

    assert isinstance(result, IRRBBSourceMappingFailure)
    assert result.code is IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD
    assert result.canonical_field == "next_repricing_date"
    assert "coupon-date proxies are not accepted" in result.message


def test_unknown_coupon_periodicity_is_not_interpreted() -> None:
    position = _position(periodicity="cada 5 meses")
    source_values = dict(position["source_values"])
    source_values["periodicidad"] = "cada 5 meses"
    position["source_values"] = source_values

    result = _mapper().map_record(_envelope(_payload(position=position)))

    assert isinstance(result, IRRBBSourceMappingFailure)
    assert result.code is IRRBBSourceMappingFailureCode.UNSUPPORTED_SOURCE_VALUE
    assert result.canonical_field == "payment_frequency_months"


def test_row_identity_fallback_is_never_accepted() -> None:
    position = _position(contract_number="", isin="", series="")
    source_values = dict(position["source_values"])
    source_values["numero contrato"] = ""
    source_values["isin"] = ""
    source_values["serie"] = ""
    position["source_values"] = source_values

    result = _mapper().map_record(_envelope(_payload(position=position)))

    assert isinstance(result, IRRBBSourceMappingFailure)
    assert result.canonical_field == "position_id"
    assert result.code is IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD


def test_policy_rejects_duplicate_selectors() -> None:
    with pytest.raises(ValueError, match="selectors must be unique"):
        _policy(_rule(), _rule())


def test_mapping_rule_provenance_cannot_be_blank() -> None:
    mapped = _mapper().map_record(_envelope())
    assert isinstance(mapped, IRRBBPositionSourceRecord)

    with pytest.raises(ValueError, match="mapping_rule_reference cannot be blank"):
        IRRBBPositionSourceRecord(position=mapped.position, mapping_rule_reference=" ")
