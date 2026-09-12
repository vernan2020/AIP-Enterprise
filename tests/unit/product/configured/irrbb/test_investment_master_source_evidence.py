from __future__ import annotations

from datetime import date

from aip.application.irrbb.investment_source_requirements import (
    INVESTMENT_SOURCE_REQUIREMENT_PROFILE_CODE,
    INVESTMENT_SOURCE_REQUIREMENT_PROFILE_VERSION,
    investment_source_requirement_profile,
)
from aip.application.irrbb.source_certification import (
    IRRBBSourceAvailabilityStatus,
    IRRBBSourceCertificationStatus,
)
from aip.domain.irrbb.models import RateType
from aip.product.configured.irrbb.investment_source_evidence import (
    InvestmentMasterSourceEvidenceAssessor,
)
from aip.product.configured.irrbb.investment_source_rules import (
    InvestmentMasterSourceRules,
)
from aip.product.configured.readers.institutional_portfolio_master_reader import (
    InstitutionalPortfolioMasterReadResult,
)


def _column_mapping() -> dict[str, str]:
    return {
        "source_row": "#",
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


def _position(*, variable_rate_flag: str = "N") -> dict[str, object]:
    return {
        "source_row": 7,
        "source_file": "maestro_2026-07-31.xlsx",
        "contract_number": "C-100",
        "currency": "CRC",
        "maturity_date": date(2028, 7, 31),
        "product_code": "TP",
        "classification": "FVOCI",
        "series": "SER-100",
        "isin": "CR0000000100",
        "traded_balance": 1_000_000.0,
        "principal_balance": 1_000_000.0,
        "book_value": 995_000.0,
        "nominal_rate": 6.25,
        "periodicity": "semestral",
        "last_interest_payment_date": date(2026, 7, 31),
        "variable_rate_flag": variable_rate_flag,
    }


def _result(
    *,
    mapping: dict[str, str] | None = None,
    positions: list[dict[str, object]] | None = None,
    source_file: str = "maestro_2026-07-31.xlsx",
) -> InstitutionalPortfolioMasterReadResult:
    return InstitutionalPortfolioMasterReadResult(
        source_file=source_file,
        valuation_date=date(2026, 7, 31),
        sheet_selected="Maestro",
        normalized_positions=positions if positions is not None else [_position()],
        warnings=(),
        rejected_row_count=0,
        source_status="HEALTHY",
        detected_column_mapping=mapping if mapping is not None else _column_mapping(),
    )


def _by_id(result: InstitutionalPortfolioMasterReadResult):
    report = InvestmentMasterSourceEvidenceAssessor.assess(result)
    return report, {item.requirement_id: item for item in report.assessments}


def test_profile_is_investment_specific_versioned_and_complete() -> None:
    profile = investment_source_requirement_profile()

    assert profile.code == INVESTMENT_SOURCE_REQUIREMENT_PROFILE_CODE
    assert profile.version == INVESTMENT_SOURCE_REQUIREMENT_PROFILE_VERSION
    assert profile.effective_from == date(2026, 9, 10)
    assert profile.requirements
    assert {item.perimeter.value for item in profile.requirements} == {"INVESTMENT"}
    assert len({item.requirement_id for item in profile.requirements}) == len(profile.requirements)


def test_fixed_rate_snapshot_preserves_evidence_without_claiming_full_readiness() -> None:
    report, by_id = _by_id(_result())

    assert report.status is IRRBBSourceCertificationStatus.INCOMPLETE
    assert not report.blocking_requirement_ids

    assert by_id["INV-CURRENCY"].status is IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE
    assert by_id["INV-PRINCIPAL"].status is IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE
    assert by_id["INV-MATURITY-DATE"].status is IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE
    assert by_id["INV-CONTRACTUAL-RATE"].status is (IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE)
    assert by_id["INV-RATE-TYPE"].status is (
        IRRBBSourceAvailabilityStatus.DERIVABLE_WITH_DOCUMENTED_RULE
    )
    assert by_id["INV-PAYMENT-FREQUENCY"].status is (
        IRRBBSourceAvailabilityStatus.DERIVABLE_WITH_DOCUMENTED_RULE
    )
    assert by_id["INV-CONTRACTUAL-SCHEDULE"].status is (
        IRRBBSourceAvailabilityStatus.DERIVABLE_WITH_DOCUMENTED_RULE
    )
    assert by_id["INV-NEXT-REPRICING-DATE"].status is (IRRBBSourceAvailabilityStatus.NOT_APPLICABLE)
    assert by_id["INV-REPRICING-FREQUENCY"].status is (IRRBBSourceAvailabilityStatus.NOT_APPLICABLE)

    assert "INV-CUTOFF-DATE" in report.not_assessed_requirement_ids
    assert "INV-INSTRUMENT-CLASS" in report.not_assessed_requirement_ids
    assert "INV-SIDE" in report.not_assessed_requirement_ids
    assert "INV-PAYMENT-STRUCTURE" in report.not_assessed_requirement_ids
    assert "INV-OPTIONALITY" in report.not_assessed_requirement_ids


def test_floating_rate_snapshot_is_blocked_without_contractual_reset_evidence() -> None:
    report, by_id = _by_id(_result(positions=[_position(variable_rate_flag="S")]))

    assert report.status is IRRBBSourceCertificationStatus.BLOCKED
    assert "INV-NEXT-REPRICING-DATE" in report.blocking_requirement_ids
    assert "INV-REPRICING-FREQUENCY" in report.blocking_requirement_ids
    assert by_id["INV-NEXT-REPRICING-DATE"].status is (
        IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE
    )
    assert by_id["INV-REPRICING-FREQUENCY"].status is (
        IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE
    )


def test_position_id_requires_stable_contract_plus_security_identity() -> None:
    mapping = _column_mapping()
    mapping.pop("isin")
    mapping.pop("series")

    report, by_id = _by_id(_result(mapping=mapping))

    assert report.status is IRRBBSourceCertificationStatus.BLOCKED
    assert by_id["INV-POSITION-ID"].status is IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE
    assert "row-number fallback" in (by_id["INV-POSITION-ID"].notes or "")


def test_missing_currency_column_is_blocking_and_not_defaulted_to_crc() -> None:
    mapping = _column_mapping()
    mapping.pop("currency")

    report, by_id = _by_id(_result(mapping=mapping))

    assert report.status is IRRBBSourceCertificationStatus.BLOCKED
    assert by_id["INV-CURRENCY"].status is IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE
    assert "default to CRC" in (by_id["INV-CURRENCY"].notes or "")


def test_unknown_variable_rate_flag_blocks_rate_type_and_repricing_applicability() -> None:
    report, by_id = _by_id(_result(positions=[_position(variable_rate_flag="?")]))

    assert report.status is IRRBBSourceCertificationStatus.BLOCKED
    assert by_id["INV-RATE-TYPE"].status is IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE
    assert by_id["INV-NEXT-REPRICING-DATE"].status is IRRBBSourceAvailabilityStatus.NOT_ASSESSED
    assert by_id["INV-REPRICING-FREQUENCY"].status is IRRBBSourceAvailabilityStatus.NOT_ASSESSED


def test_blank_source_file_does_not_create_false_lineage_evidence() -> None:
    report, by_id = _by_id(_result(source_file=""))

    assert report.status is IRRBBSourceCertificationStatus.INCOMPLETE
    assert by_id["INV-SOURCE-REFERENCE"].status is IRRBBSourceAvailabilityStatus.NOT_ASSESSED


def test_strict_source_rules_never_use_row_position_or_unknown_values() -> None:
    assert (
        InvestmentMasterSourceRules.stable_position_id(
            contract_number="C-1", isin="CR1", series=None
        )
        == "contract:C-1|isin:CR1"
    )
    assert (
        InvestmentMasterSourceRules.stable_position_id(
            contract_number="C-1", isin=None, series="SER1"
        )
        == "contract:C-1|series:SER1"
    )
    assert (
        InvestmentMasterSourceRules.stable_position_id(
            contract_number=None, isin="CR1", series="SER1"
        )
        is None
    )
    assert InvestmentMasterSourceRules.rate_type("S") is RateType.FLOATING
    assert InvestmentMasterSourceRules.rate_type("N") is RateType.FIXED
    assert InvestmentMasterSourceRules.rate_type("") is None
    assert InvestmentMasterSourceRules.rate_type("UNKNOWN") is None
    assert InvestmentMasterSourceRules.payment_frequency_months("semestral") == 6
    assert InvestmentMasterSourceRules.payment_frequency_months("cada 5 meses") is None
