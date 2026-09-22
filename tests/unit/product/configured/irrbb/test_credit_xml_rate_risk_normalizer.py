from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.application.irrbb import IRRBBSourceExclusion, IRRBBSourceMappingFailure
from aip.product.configured.irrbb.credit_xml_rate_risk_normalizer import (
    CREDIT_XML_RULE_FIXED_MATURITY,
    CREDIT_XML_RULE_FV_CHANGE_DATE,
    CREDIT_XML_RULE_JUDICIAL_EXCLUDE,
    CREDIT_XML_RULE_MORA_EXCLUDE,
    CREDIT_XML_RULE_VARIABLE_R1,
    CreditXMLRateRiskFact,
    CreditXMLRateRiskNormalizer,
)
from aip.product.configured.irrbb.source_acl import IRRBBSourceRecordEnvelope
from aip.product.configured.irrbb.xml_confia_source import XMLConfiaRecord

CUTOFF = date(2026, 8, 31)


def _envelope(**overrides: str) -> IRRBBSourceRecordEnvelope[XMLConfiaRecord]:
    values = {
        "IdOperacionCredito": "OP-1",
        "DiasMaximaMorosidad": "0",
        "TipoMonedaOperacion": "1",
        "CuentaContablePrincipal": "13131101",
        "SaldoPrincipalOperacionCrediticia": "1000.25",
        "CuentaContableProductosPorCobrar": "13831101",
        "SaldoProductosPorCobrar": "10.75",
        "FechaFormalizacion": "10/10/2017",
        "FechaVencimiento": "10/10/2029",
        "TasaInteresNominalVigente": "17.50",
        "IndicadorTipoTasa": "V",
        "FechaProximoPagoIntereses": "10/09/2026",
        "FechaCambioTipoTasa": "",
        "TipoFrecuenciaAjusteTasaInteresVariable": "4",
    }
    values.update(overrides)
    return IRRBBSourceRecordEnvelope(
        source_record_id="1",
        source_reference="XML_CONFIA:NEC2024_Operaciones_5103.xml:1",
        payload=XMLConfiaRecord(record_id="1", action="insertar", values=values),
    )


def test_variable_credit_preserves_raw_currency_and_routes_to_audited_r1_rule() -> None:
    result = CreditXMLRateRiskNormalizer().normalize(_envelope(), cutoff_date=CUTOFF)

    assert isinstance(result, CreditXMLRateRiskFact)
    assert result.operation_id == "OP-1"
    assert result.currency_source_code == "1"
    assert result.rule_code == CREDIT_XML_RULE_VARIABLE_R1
    assert result.sensitive_date is None
    assert result.sicveca_bucket_hint == 1
    assert result.principal_amount == Decimal("1000.25")
    assert result.product_amount == Decimal("10.75")
    assert result.total_gap_amount == Decimal("1011.00")
    assert result.nominal_rate_percent == Decimal("17.50")


def test_fixed_credit_uses_maturity_as_audited_sensitive_date() -> None:
    result = CreditXMLRateRiskNormalizer().normalize(
        _envelope(IndicadorTipoTasa="F", FechaVencimiento="15/12/2026"),
        cutoff_date=CUTOFF,
    )

    assert isinstance(result, CreditXMLRateRiskFact)
    assert result.rule_code == CREDIT_XML_RULE_FIXED_MATURITY
    assert result.sensitive_date == date(2026, 12, 15)
    assert result.sicveca_bucket_hint is None


def test_fv_credit_uses_rate_change_date_as_audited_sensitive_date() -> None:
    result = CreditXMLRateRiskNormalizer().normalize(
        _envelope(IndicadorTipoTasa="FV", FechaCambioTipoTasa="15/11/2026"),
        cutoff_date=CUTOFF,
    )

    assert isinstance(result, CreditXMLRateRiskFact)
    assert result.rule_code == CREDIT_XML_RULE_FV_CHANGE_DATE
    assert result.sensitive_date == date(2026, 11, 15)
    assert result.sicveca_bucket_hint is None


def test_mora_over_30_is_explicit_exclusion_before_rate_mapping() -> None:
    result = CreditXMLRateRiskNormalizer().normalize(
        _envelope(DiasMaximaMorosidad="31", IndicadorTipoTasa=""),
        cutoff_date=CUTOFF,
    )

    assert isinstance(result, IRRBBSourceExclusion)
    assert result.reason_code == CREDIT_XML_RULE_MORA_EXCLUDE
    assert result.source_record_id == "1"


def test_account_133_is_explicit_judicial_exclusion_without_invented_indicator() -> None:
    result = CreditXMLRateRiskNormalizer().normalize(
        _envelope(CuentaContablePrincipal="13331101"),
        cutoff_date=CUTOFF,
    )

    assert isinstance(result, IRRBBSourceExclusion)
    assert result.reason_code == CREDIT_XML_RULE_JUDICIAL_EXCLUDE


def test_fv_without_rate_change_date_is_explicit_mapping_failure() -> None:
    result = CreditXMLRateRiskNormalizer().normalize(
        _envelope(IndicadorTipoTasa="FV", FechaCambioTipoTasa=""),
        cutoff_date=CUTOFF,
    )

    assert isinstance(result, IRRBBSourceMappingFailure)
    assert result.canonical_field == "FechaCambioTipoTasa"
    assert "requires FechaCambioTipoTasa" in result.message


def test_fixed_sensitive_date_before_cutoff_is_error_not_silent_bucket_assignment() -> None:
    result = CreditXMLRateRiskNormalizer().normalize(
        _envelope(IndicadorTipoTasa="F", FechaVencimiento="30/08/2026"),
        cutoff_date=CUTOFF,
    )

    assert isinstance(result, IRRBBSourceMappingFailure)
    assert result.canonical_field == "sensitive_date"
    assert "before cutoff" in result.message


def test_unsupported_rate_indicator_fails_closed() -> None:
    result = CreditXMLRateRiskNormalizer().normalize(
        _envelope(IndicadorTipoTasa="X"),
        cutoff_date=CUTOFF,
    )

    assert isinstance(result, IRRBBSourceMappingFailure)
    assert result.canonical_field == "IndicadorTipoTasa"
    assert "Unsupported credit rate indicator" in result.message


def test_negative_principal_or_product_is_rejected() -> None:
    result = CreditXMLRateRiskNormalizer().normalize(
        _envelope(SaldoPrincipalOperacionCrediticia="-1"),
        cutoff_date=CUTOFF,
    )

    assert isinstance(result, IRRBBSourceMappingFailure)
    assert result.canonical_field == "principal/product"


def test_unsupported_account_family_fails_closed() -> None:
    result = CreditXMLRateRiskNormalizer().normalize(
        _envelope(CuentaContablePrincipal="13531101"),
        cutoff_date=CUTOFF,
    )

    assert isinstance(result, IRRBBSourceMappingFailure)
    assert result.canonical_field == "CuentaContablePrincipal"
