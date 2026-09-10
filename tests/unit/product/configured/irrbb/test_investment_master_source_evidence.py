from __future__ import annotations

from aip.application.irrbb import (
    IRRBBSourceAvailabilityStatus,
    IRRBBSourceCertificationStatus,
)
from aip.product.configured.irrbb.investment_master_source_evidence import (
    InvestmentMasterSourceEvidenceAssessor,
    investment_master_requirement_profile,
)


def _column_mapping() -> dict[str, str]:
    return {
        "source_row": "#",
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


def test_profile_is_investment_specific_and_versioned() -> None:
    profile = investment_master_requirement_profile()

    assert profile.source_candidate_id == "institutional-investment-master"
    assert profile.version == "2026-09-10"
    assert profile.requirements
    assert all(requirement.requirement_id for requirement in profile.requirements)


def test_assessor_is_fail_closed_for_unproven_eve_requirements() -> None:
    report = InvestmentMasterSourceEvidenceAssessor().assess(
        detected_column_mapping=_column_mapping(),
        source_reference="maestro_2026-07-31.xlsx",
    )

    assert report.status is IRRBBSourceCertificationStatus.BLOCKED

    by_id = {assessment.requirement_id: assessment for assessment in report.assessments}
    assert by_id["currency"].status is IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE
    assert by_id["principal"].status is IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE
    assert by_id["maturity_date"].status is IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE
    assert by_id["contractual_rate"].status is IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE
    assert by_id["payment_frequency_months"].status is (
        IRRBBSourceAvailabilityStatus.DERIVABLE_WITH_DOCUMENTED_RULE
    )
    assert by_id["rate_type"].status is (
        IRRBBSourceAvailabilityStatus.DERIVABLE_WITH_DOCUMENTED_RULE
    )

    assert by_id["next_repricing_date"].status is IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE
    assert by_id["yield_curve_points"].status is IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE
    assert by_id["fx_reporting_rate"].status is IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE
    assert by_id["tier_one_capital"].status is IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE


def test_position_id_is_only_derivable_with_stable_identity_columns() -> None:
    mapping = _column_mapping()
    mapping.pop("isin")
    mapping.pop("series")

    report = InvestmentMasterSourceEvidenceAssessor().assess(
        detected_column_mapping=mapping,
        source_reference="maestro.xlsx",
    )

    by_id = {assessment.requirement_id: assessment for assessment in report.assessments}
    assert by_id["position_id"].status is IRRBBSourceAvailabilityStatus.NOT_ASSESSED


def test_missing_native_field_is_not_silently_promoted() -> None:
    mapping = _column_mapping()
    mapping.pop("currency")

    report = InvestmentMasterSourceEvidenceAssessor().assess(
        detected_column_mapping=mapping,
        source_reference="maestro.xlsx",
    )

    by_id = {assessment.requirement_id: assessment for assessment in report.assessments}
    assert by_id["currency"].status is IRRBBSourceAvailabilityStatus.NOT_ASSESSED


def test_empty_source_reference_is_rejected() -> None:
    try:
        InvestmentMasterSourceEvidenceAssessor().assess(
            detected_column_mapping=_column_mapping(),
            source_reference="",
        )
    except ValueError as exc:
        assert "source_reference" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("blank source_reference must fail")
