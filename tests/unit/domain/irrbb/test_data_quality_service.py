from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.irrbb.data_quality import (
    IRRBBDataIssueCode,
    IRRBBDataQualityStatus,
    IRRBBValidationContext,
)
from aip.domain.irrbb.models import (
    BankingBookPosition,
    BankingBookSide,
    IRRBBInstrumentClass,
    OptionalityType,
    PaymentStructure,
    RateType,
)
from aip.domain.irrbb.services.data_quality_service import IRRBBPositionDataQualityService
from aip.shared.money import Currency, Money

_VALUATION_DATE = date(2026, 8, 31)


def _investment(*, rate_type: RateType = RateType.FIXED) -> BankingBookPosition:
    return BankingBookPosition(
        position_id="INV-1",
        product_type="BOND",
        side=BankingBookSide.ASSET,
        currency=Currency.CRC,
        principal=Money(Decimal("1000"), Currency.CRC),
        rate_type=rate_type,
        maturity_date=date(2028, 8, 31),
        source_reference="TEST_PORTFOLIO",
        contractual_rate=Decimal("0.05"),
        next_repricing_date=(date(2026, 11, 30) if rate_type is RateType.FLOATING else None),
        repricing_frequency_months=(3 if rate_type is RateType.FLOATING else None),
        payment_frequency_months=3,
        instrument_class=IRRBBInstrumentClass.INVESTMENT,
        payment_structure=PaymentStructure.BULLET,
    )


def test_fixed_investment_is_ready_with_canonical_schedule_terms() -> None:
    assessment = IRRBBPositionDataQualityService.assess(
        position=_investment(),
        valuation_date=_VALUATION_DATE,
    )

    assert assessment.status is IRRBBDataQualityStatus.READY
    assert assessment.issues == ()


def test_floating_investment_requires_scenario_repricing_capability() -> None:
    assessment = IRRBBPositionDataQualityService.assess(
        position=_investment(rate_type=RateType.FLOATING),
        valuation_date=_VALUATION_DATE,
    )

    assert assessment.status is IRRBBDataQualityStatus.INCOMPLETE
    assert IRRBBDataIssueCode.SCENARIO_REPRICING_MODEL_REQUIRED in {
        issue.code for issue in assessment.issues
    }

    ready = IRRBBPositionDataQualityService.assess(
        position=_investment(rate_type=RateType.FLOATING),
        valuation_date=_VALUATION_DATE,
        context=IRRBBValidationContext(scenario_repricing_model_available=True),
    )
    assert ready.status is IRRBBDataQualityStatus.READY


def test_amortizing_credit_requires_explicit_normalized_schedule() -> None:
    position = BankingBookPosition(
        position_id="LOAN-1",
        product_type="CREDIT",
        side=BankingBookSide.ASSET,
        currency=Currency.CRC,
        principal=Money(Decimal("50000"), Currency.CRC),
        rate_type=RateType.FIXED,
        maturity_date=date(2030, 8, 31),
        source_reference="TEST_CREDIT",
        contractual_rate=Decimal("0.12"),
        payment_frequency_months=1,
        instrument_class=IRRBBInstrumentClass.CREDIT,
        payment_structure=PaymentStructure.AMORTIZING,
    )

    incomplete = IRRBBPositionDataQualityService.assess(
        position=position,
        valuation_date=_VALUATION_DATE,
    )
    assert incomplete.status is IRRBBDataQualityStatus.INCOMPLETE
    assert IRRBBDataIssueCode.EXPLICIT_SCHEDULE_REQUIRED in {
        issue.code for issue in incomplete.issues
    }

    ready = IRRBBPositionDataQualityService.assess(
        position=position,
        valuation_date=_VALUATION_DATE,
        context=IRRBBValidationContext(explicit_schedule_available=True),
    )
    assert ready.status is IRRBBDataQualityStatus.READY


def test_non_maturity_deposit_requires_behavioral_model() -> None:
    position = BankingBookPosition(
        position_id="NMD-1",
        product_type="SAVINGS",
        side=BankingBookSide.LIABILITY,
        currency=Currency.CRC,
        principal=Money(Decimal("100000"), Currency.CRC),
        rate_type=RateType.FLOATING,
        maturity_date=None,
        source_reference="TEST_DEPOSITS",
        optionality=OptionalityType.NON_MATURITY_DEPOSIT,
        instrument_class=IRRBBInstrumentClass.NON_MATURITY_DEPOSIT,
        payment_structure=PaymentStructure.NON_MATURITY,
    )

    incomplete = IRRBBPositionDataQualityService.assess(
        position=position,
        valuation_date=_VALUATION_DATE,
    )
    assert incomplete.status is IRRBBDataQualityStatus.INCOMPLETE
    assert IRRBBDataIssueCode.BEHAVIORAL_MODEL_REQUIRED in {
        issue.code for issue in incomplete.issues
    }

    ready = IRRBBPositionDataQualityService.assess(
        position=position,
        valuation_date=_VALUATION_DATE,
        context=IRRBBValidationContext(behavioral_model_available=True),
    )
    assert ready.status is IRRBBDataQualityStatus.READY


def test_zero_principal_position_is_explicitly_excluded() -> None:
    position = BankingBookPosition(
        position_id="ZERO-1",
        product_type="BOND",
        side=BankingBookSide.ASSET,
        currency=Currency.CRC,
        principal=Money(Decimal("0"), Currency.CRC),
        rate_type=RateType.FIXED,
        maturity_date=date(2028, 8, 31),
        source_reference="TEST",
        instrument_class=IRRBBInstrumentClass.INVESTMENT,
    )

    assessment = IRRBBPositionDataQualityService.assess(
        position=position,
        valuation_date=_VALUATION_DATE,
    )

    assert assessment.status is IRRBBDataQualityStatus.EXCLUDED
    assert assessment.issues[0].code is IRRBBDataIssueCode.ZERO_PRINCIPAL
