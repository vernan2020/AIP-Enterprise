from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.application.irrbb import IRRBBSourceMappingFailure
from aip.product.configured.irrbb.captaciones_irrbb_account_classifier import (
    CaptacionesIRRBBAccountClassifier,
)
from aip.product.configured.irrbb.captaciones_irrbb_readiness import (
    CaptacionesIRRBBReadinessService,
    CaptacionesIRRBBReadinessStatus,
)
from aip.product.configured.irrbb.captaciones_xml_currency_bridge import (
    CaptacionesXMLCanonicalCurrencyFact,
    CaptacionesXMLCurrencyBatchResult,
)
from aip.shared.money import Currency, Money


def _fact(
    account: str,
    *,
    rate_type: str = "V",
    maturity: date | None = date(2027, 1, 1),
) -> CaptacionesXMLCanonicalCurrencyFact:
    return CaptacionesXMLCanonicalCurrencyFact(
        source_record_id=f"ROW:{account}",
        source_reference=f"XML_CONFIA:Pasivos_Cuentas_Contables_210.xml|account={account}",
        creditor_id="ACR-1",
        operation_id=f"OP-{account}",
        operation_type_source_code="1",
        guarantee_indicator="N",
        account_type_source_code="4",
        rate_type_source_code=rate_type,
        variable_rate_source_code="7" if rate_type != "F" else None,
        nominal_rate_percent=Decimal("3.25"),
        sugef_catalog_source_code="14",
        accounting_account_code=account,
        principal=Money(Decimal("990"), Currency.CRC),
        product_account_code="21900100",
        product=Money(Decimal("10"), Currency.CRC),
        amount=Money(Decimal("1000"), Currency.CRC),
        origination_date=date(2025, 1, 1),
        maturity_date=maturity,
        reserve_requirement_indicator="S",
        deposit_fgd_source_code="FGD-1",
    )


def test_sight_nmd_requires_behavioral_profile_and_ignores_xml_maturity_as_bucket_shortcut() -> None:
    fact = _fact("21103100", maturity=date(2035, 12, 31))
    classification = CaptacionesIRRBBAccountClassifier.classify(fact)

    assert not isinstance(classification, IRRBBSourceMappingFailure)
    result = CaptacionesIRRBBReadinessService.assess_fact(fact, classification)

    assert result.status is CaptacionesIRRBBReadinessStatus.BLOCKED_NMD_BEHAVIORAL_PROFILE
    assert result.missing_capabilities == ("APPROVED_NMD_BEHAVIORAL_PROFILE",)
    assert "must not be used as synthetic IRRBB risk dates" in result.message


def test_fixed_term_requires_contractual_schedule_and_classification_not_account_shortcut() -> None:
    fact = _fact("21312100", rate_type="F")
    classification = CaptacionesIRRBBAccountClassifier.classify(fact)

    assert not isinstance(classification, IRRBBSourceMappingFailure)
    result = CaptacionesIRRBBReadinessService.assess_fact(fact, classification)

    assert result.status is CaptacionesIRRBBReadinessStatus.BLOCKED_CONTRACTUAL_SCHEDULE
    assert result.missing_capabilities == (
        "CONTRACTUAL_PAYMENT_SCHEDULE",
        "TERM_DEPOSIT_CONTRACTUAL_CLASSIFICATION",
    )
    assert "must not infer CAPF modality" in result.message


def test_variable_term_also_requires_exact_repricing_and_residual_principal_evidence() -> None:
    fact = _fact("21314100", rate_type="V")
    classification = CaptacionesIRRBBAccountClassifier.classify(fact)

    assert not isinstance(classification, IRRBBSourceMappingFailure)
    result = CaptacionesIRRBBReadinessService.assess_fact(fact, classification)

    assert result.status is CaptacionesIRRBBReadinessStatus.BLOCKED_CONTRACTUAL_SCHEDULE
    assert "NEXT_REPRICING_DATE" in result.missing_capabilities
    assert "RESIDUAL_PRINCIPAL_AT_REPRICING_OR_PRINCIPAL_COMPONENTS" in (
        result.missing_capabilities
    )


def test_matured_term_requires_explicit_irrbb_policy() -> None:
    fact = _fact("21104100", rate_type="F", maturity=date(2020, 1, 1))
    classification = CaptacionesIRRBBAccountClassifier.classify(fact)

    assert not isinstance(classification, IRRBBSourceMappingFailure)
    result = CaptacionesIRRBBReadinessService.assess_fact(fact, classification)

    assert result.status is CaptacionesIRRBBReadinessStatus.BLOCKED_MATURED_TERM_POLICY
    assert result.missing_capabilities == ("APPROVED_MATURED_TERM_IRRBB_TREATMENT",)


def test_batch_preserves_unsupported_account_as_mapping_failure() -> None:
    batch = CaptacionesXMLCurrencyBatchResult(
        source_record_count=2,
        canonical_facts=(_fact("21103100"), _fact("21400100")),
        mapping_failures=(),
    )

    result = CaptacionesIRRBBReadinessService.assess_batch(batch)

    assert result.source_record_count == 2
    assert len(result.assessments) == 1
    assert len(result.mapping_failures) == 1
    assert result.mapping_failures[0].canonical_field == "accounting_account_code"


def test_readiness_rejects_lineage_substitution() -> None:
    fact = _fact("21103100")
    classification = CaptacionesIRRBBAccountClassifier.classify(fact)
    assert not isinstance(classification, IRRBBSourceMappingFailure)

    altered = type(classification)(
        source_record_id="OTHER",
        source_reference=classification.source_reference,
        operation_id=classification.operation_id,
        accounting_account_code=classification.accounting_account_code,
        funding_class=classification.funding_class,
        instrument_class=classification.instrument_class,
        rule_reference=classification.rule_reference,
    )

    try:
        CaptacionesIRRBBReadinessService.assess_fact(fact, altered)
    except ValueError as exc:
        assert "changed source_record_id" in str(exc)
    else:
        raise AssertionError("lineage substitution must fail")
