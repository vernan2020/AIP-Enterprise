from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.domain.irrbb.models import (
    BankingBookSide,
    CashFlowDirection,
    IRRBBCashFlow,
    IRRBBScenario,
)
from aip.domain.irrbb.services.economic_value_service import EconomicValueService
from aip.shared.money import Currency, Money


class _DiscountFactors:
    def discount_factor(
        self,
        *,
        currency: Currency,
        scenario: IRRBBScenario,
        valuation_date: date,
        payment_date: date,
    ) -> Decimal:
        del currency, scenario, valuation_date, payment_date
        return Decimal("0.90")


class _ExchangeRates:
    def rate(
        self,
        *,
        from_currency: Currency,
        to_currency: Currency,
        valuation_date: date,
    ) -> Decimal:
        del to_currency, valuation_date
        return Decimal("500") if from_currency is Currency.USD else Decimal("1")


def _flow(
    *,
    position_id: str,
    side: BankingBookSide,
    direction: CashFlowDirection,
    amount: Decimal,
    currency: Currency = Currency.CRC,
) -> IRRBBCashFlow:
    return IRRBBCashFlow(
        position_id=position_id,
        side=side,
        direction=direction,
        amount=Money(amount, currency),
        cashflow_date=date(2027, 8, 31),
        risk_date=date(2027, 8, 31),
        flow_type="PRINCIPAL",
        source_reference="TEST",
    )


def test_calculate_eve_preserves_asset_liability_off_balance_identity() -> None:
    result = EconomicValueService.calculate(
        cashflows=(
            _flow(
                position_id="A1",
                side=BankingBookSide.ASSET,
                direction=CashFlowDirection.RECEIVABLE,
                amount=Decimal("100"),
            ),
            _flow(
                position_id="L1",
                side=BankingBookSide.LIABILITY,
                direction=CashFlowDirection.PAYABLE,
                amount=Decimal("40"),
            ),
            _flow(
                position_id="O1",
                side=BankingBookSide.OFF_BALANCE,
                direction=CashFlowDirection.RECEIVABLE,
                amount=Decimal("10"),
            ),
        ),
        valuation_date=date(2026, 8, 31),
        scenario=IRRBBScenario.BASE,
        reporting_currency=Currency.CRC,
        discount_factors=_DiscountFactors(),
    )

    assert result.pv_assets.amount == Decimal("90.00")
    assert result.pv_liabilities.amount == Decimal("36.00")
    assert result.pv_off_balance_net.amount == Decimal("9.00")
    assert result.eve.amount == Decimal("63.00")
    assert tuple(item.signed_eve_contribution.amount for item in result.discounted_cashflows) == (
        Decimal("90.00"),
        Decimal("-36.00"),
        Decimal("9.00"),
    )


def test_calculate_requires_explicit_fx_for_foreign_currency() -> None:
    flow = _flow(
        position_id="USD1",
        side=BankingBookSide.ASSET,
        direction=CashFlowDirection.RECEIVABLE,
        amount=Decimal("2"),
        currency=Currency.USD,
    )

    with pytest.raises(ValueError, match="exchange-rate provider required"):
        EconomicValueService.calculate(
            cashflows=(flow,),
            valuation_date=date(2026, 8, 31),
            scenario=IRRBBScenario.BASE,
            reporting_currency=Currency.CRC,
            discount_factors=_DiscountFactors(),
        )


def test_calculate_converts_foreign_currency_with_explicit_provider() -> None:
    result = EconomicValueService.calculate(
        cashflows=(
            _flow(
                position_id="USD1",
                side=BankingBookSide.ASSET,
                direction=CashFlowDirection.RECEIVABLE,
                amount=Decimal("2"),
                currency=Currency.USD,
            ),
        ),
        valuation_date=date(2026, 8, 31),
        scenario=IRRBBScenario.BASE,
        reporting_currency=Currency.CRC,
        discount_factors=_DiscountFactors(),
        exchange_rates=_ExchangeRates(),
    )

    assert result.eve.amount == Decimal("900.00")
