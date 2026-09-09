from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.domain.irrbb.models import (
    BankingBookPosition,
    BankingBookSide,
    IRRBBInstrumentClass,
    RateType,
)
from aip.domain.irrbb.services.sugef_gap_row_classifier_service import (
    SugefGapRowClassifierService,
)
from aip.domain.irrbb.sugef_standard_gap import (
    SugefGapCounterpartyFamily,
    SugefGapFundingTermType,
    SugefGapReportLine,
    SugefGapRoutingMetadata,
    SugefGapRowClassificationStatus,
)
from aip.shared.money import Currency, Money


def _position(
    *,
    position_id: str,
    side: BankingBookSide,
    instrument_class: IRRBBInstrumentClass,
    rate_type: RateType,
) -> BankingBookPosition:
    return BankingBookPosition(
        position_id=position_id,
        product_type="TEST",
        side=side,
        currency=Currency.CRC,
        principal=Money(Decimal("1000"), Currency.CRC),
        rate_type=rate_type,
        maturity_date=(None if instrument_class is IRRBBInstrumentClass.NON_MATURITY_DEPOSIT else date(2027, 1, 1)),
        source_reference=f"TEST:{position_id}",
        instrument_class=instrument_class,
    )


@pytest.mark.parametrize(
    ("instrument_class", "rate_type", "expected"),
    (
        (
            IRRBBInstrumentClass.INVESTMENT,
            RateType.FIXED,
            SugefGapReportLine.INVESTMENT_FIXED,
        ),
        (
            IRRBBInstrumentClass.INVESTMENT,
            RateType.FLOATING,
            SugefGapReportLine.INVESTMENT_VARIABLE_SEMIVARIABLE,
        ),
        (
            IRRBBInstrumentClass.CREDIT,
            RateType.FIXED,
            SugefGapReportLine.CREDIT_FIXED,
        ),
        (
            IRRBBInstrumentClass.CREDIT,
            RateType.FLOATING,
            SugefGapReportLine.CREDIT_VARIABLE_SEMIVARIABLE,
        ),
    ),
)
def test_asset_rows_are_classified_by_instrument_and_rate(
    instrument_class: IRRBBInstrumentClass,
    rate_type: RateType,
    expected: SugefGapReportLine,
) -> None:
    position = _position(
        position_id="ASSET",
        side=BankingBookSide.ASSET,
        instrument_class=instrument_class,
        rate_type=rate_type,
    )

    result = SugefGapRowClassifierService.classify(position=position)

    assert result.status is SugefGapRowClassificationStatus.MAPPED
    assert result.report_line is expected


@pytest.mark.parametrize(
    ("family", "has_cost", "expected"),
    (
        (
            SugefGapCounterpartyFamily.PUBLIC,
            True,
            SugefGapReportLine.PUBLIC_SIGHT_WITH_COST,
        ),
        (
            SugefGapCounterpartyFamily.PUBLIC,
            False,
            SugefGapReportLine.PUBLIC_SIGHT_WITHOUT_COST,
        ),
        (
            SugefGapCounterpartyFamily.BCCR,
            True,
            SugefGapReportLine.BCCR_SIGHT_WITH_COST,
        ),
        (
            SugefGapCounterpartyFamily.FINANCIAL_ENTITY,
            False,
            SugefGapReportLine.FINANCIAL_ENTITY_SIGHT_WITHOUT_COST,
        ),
    ),
)
def test_sight_liabilities_use_counterparty_and_financial_cost(
    family: SugefGapCounterpartyFamily,
    has_cost: bool,
    expected: SugefGapReportLine,
) -> None:
    position = _position(
        position_id="SIGHT",
        side=BankingBookSide.LIABILITY,
        instrument_class=IRRBBInstrumentClass.NON_MATURITY_DEPOSIT,
        rate_type=RateType.FLOATING,
    )
    routing = SugefGapRoutingMetadata(
        position_id=position.position_id,
        counterparty_family=family,
        funding_term_type=SugefGapFundingTermType.SIGHT,
        has_financial_cost=has_cost,
    )

    result = SugefGapRowClassifierService.classify(position=position, routing=routing)

    assert result.status is SugefGapRowClassificationStatus.MAPPED
    assert result.report_line is expected


@pytest.mark.parametrize(
    ("family", "rate_type", "expected"),
    (
        (
            SugefGapCounterpartyFamily.PUBLIC,
            RateType.FIXED,
            SugefGapReportLine.PUBLIC_TERM_FIXED,
        ),
        (
            SugefGapCounterpartyFamily.BCCR,
            RateType.FLOATING,
            SugefGapReportLine.BCCR_TERM_VARIABLE_SEMIVARIABLE,
        ),
        (
            SugefGapCounterpartyFamily.FINANCIAL_ENTITY,
            RateType.FIXED,
            SugefGapReportLine.FINANCIAL_ENTITY_TERM_FIXED,
        ),
    ),
)
def test_term_liabilities_use_counterparty_and_rate_type(
    family: SugefGapCounterpartyFamily,
    rate_type: RateType,
    expected: SugefGapReportLine,
) -> None:
    position = _position(
        position_id="TERM",
        side=BankingBookSide.LIABILITY,
        instrument_class=IRRBBInstrumentClass.TERM_DEPOSIT,
        rate_type=rate_type,
    )
    routing = SugefGapRoutingMetadata(
        position_id=position.position_id,
        counterparty_family=family,
        funding_term_type=SugefGapFundingTermType.TERM,
    )

    result = SugefGapRowClassifierService.classify(position=position, routing=routing)

    assert result.status is SugefGapRowClassificationStatus.MAPPED
    assert result.report_line is expected


def test_sight_liability_without_cost_flag_is_incomplete() -> None:
    position = _position(
        position_id="NO-COST-FLAG",
        side=BankingBookSide.LIABILITY,
        instrument_class=IRRBBInstrumentClass.NON_MATURITY_DEPOSIT,
        rate_type=RateType.FLOATING,
    )
    routing = SugefGapRoutingMetadata(
        position_id=position.position_id,
        counterparty_family=SugefGapCounterpartyFamily.PUBLIC,
        funding_term_type=SugefGapFundingTermType.SIGHT,
    )

    result = SugefGapRowClassifierService.classify(position=position, routing=routing)

    assert result.status is SugefGapRowClassificationStatus.INCOMPLETE
    assert result.report_line is None


def test_non_financial_entity_is_mapping_pending() -> None:
    position = _position(
        position_id="ACCOUNT-233",
        side=BankingBookSide.LIABILITY,
        instrument_class=IRRBBInstrumentClass.BORROWING,
        rate_type=RateType.FIXED,
    )
    routing = SugefGapRoutingMetadata(
        position_id=position.position_id,
        counterparty_family=SugefGapCounterpartyFamily.NON_FINANCIAL_ENTITY,
        funding_term_type=SugefGapFundingTermType.TERM,
        accounting_account_code="233",
    )

    result = SugefGapRowClassifierService.classify(position=position, routing=routing)

    assert result.status is SugefGapRowClassificationStatus.MAPPING_PENDING
    assert result.report_line is None


def test_off_balance_derivative_is_mapping_pending() -> None:
    position = _position(
        position_id="DERIVATIVE",
        side=BankingBookSide.OFF_BALANCE,
        instrument_class=IRRBBInstrumentClass.OFF_BALANCE,
        rate_type=RateType.FLOATING,
    )

    result = SugefGapRowClassifierService.classify(position=position)

    assert result.status is SugefGapRowClassificationStatus.MAPPING_PENDING
    assert result.report_line is None


def test_routing_must_match_position_id() -> None:
    position = _position(
        position_id="POSITION-A",
        side=BankingBookSide.LIABILITY,
        instrument_class=IRRBBInstrumentClass.TERM_DEPOSIT,
        rate_type=RateType.FIXED,
    )
    routing = SugefGapRoutingMetadata(
        position_id="POSITION-B",
        counterparty_family=SugefGapCounterpartyFamily.PUBLIC,
        funding_term_type=SugefGapFundingTermType.TERM,
    )

    with pytest.raises(ValueError, match="position_id"):
        SugefGapRowClassifierService.classify(position=position, routing=routing)
