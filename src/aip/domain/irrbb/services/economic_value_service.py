from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.irrbb.models import (
    BankingBookSide,
    CashFlowAmountStatus,
    CashFlowDirection,
    DiscountedCashFlow,
    EconomicValueResult,
    IRRBBCashFlow,
    IRRBBScenario,
)
from aip.domain.irrbb.ports import DiscountFactorProvider, ExchangeRateProvider
from aip.shared.money import Currency, Money


class EconomicValueService:
    """Calculate scenario EVE from auditable future cash flows.

    Discounting and FX conversion are ports so neither market-data sourcing nor
    curve construction is embedded in the domain calculation. Current-rate
    projections are accepted for the base case but must be scenario-projected
    before they can enter a stressed EVE calculation.
    """

    @classmethod
    def calculate(
        cls,
        *,
        cashflows: tuple[IRRBBCashFlow, ...],
        valuation_date: date,
        scenario: IRRBBScenario,
        reporting_currency: Currency,
        discount_factors: DiscountFactorProvider,
        exchange_rates: ExchangeRateProvider | None = None,
    ) -> EconomicValueResult:
        asset_pv = Decimal("0")
        liability_pv = Decimal("0")
        off_balance_pv = Decimal("0")
        discounted: list[DiscountedCashFlow] = []

        for flow in cashflows:
            if flow.cashflow_date < valuation_date:
                raise ValueError(f"cash flow {flow.position_id} occurs before valuation_date")
            if (
                scenario is not IRRBBScenario.BASE
                and flow.amount_status is CashFlowAmountStatus.PROJECTED_CURRENT_RATE
            ):
                raise ValueError(
                    "stressed EVE cannot use a PROJECTED_CURRENT_RATE cash flow; "
                    "apply an approved scenario repricing projector first"
                )

            factor = discount_factors.discount_factor(
                currency=flow.amount.currency,
                scenario=scenario,
                valuation_date=valuation_date,
                payment_date=flow.cashflow_date,
            )
            if factor <= 0:
                raise ValueError("discount factor must be positive")

            fx = cls._exchange_rate(
                flow.amount.currency,
                reporting_currency,
                valuation_date,
                exchange_rates,
            )
            pv = flow.amount.amount * factor * fx
            sign = Decimal("1") if flow.direction is CashFlowDirection.RECEIVABLE else Decimal("-1")
            signed_eve = pv * sign

            if flow.side is BankingBookSide.ASSET:
                asset_pv += signed_eve
            elif flow.side is BankingBookSide.LIABILITY:
                # Liability PV is stored as a positive obligation so EVE remains
                # Assets - Liabilities + OffBalance. A receivable liability flow
                # reduces that obligation.
                liability_pv -= signed_eve
            else:
                off_balance_pv += signed_eve

            discounted.append(
                DiscountedCashFlow(
                    cashflow=flow,
                    scenario=scenario,
                    discount_factor=factor,
                    exchange_rate=fx,
                    present_value_reporting=Money(pv, reporting_currency),
                    signed_eve_contribution=Money(signed_eve, reporting_currency),
                )
            )

        eve = asset_pv - liability_pv + off_balance_pv
        return EconomicValueResult(
            scenario=scenario,
            reporting_currency=reporting_currency,
            pv_assets=Money(asset_pv, reporting_currency),
            pv_liabilities=Money(liability_pv, reporting_currency),
            pv_off_balance_net=Money(off_balance_pv, reporting_currency),
            eve=Money(eve, reporting_currency),
            discounted_cashflows=tuple(discounted),
        )

    @staticmethod
    def _exchange_rate(
        from_currency: Currency,
        reporting_currency: Currency,
        valuation_date: date,
        provider: ExchangeRateProvider | None,
    ) -> Decimal:
        if from_currency is reporting_currency:
            return Decimal("1")
        if provider is None:
            raise ValueError(
                f"exchange-rate provider required for {from_currency}->{reporting_currency}"
            )
        rate = provider.rate(
            from_currency=from_currency,
            to_currency=reporting_currency,
            valuation_date=valuation_date,
        )
        if rate <= 0:
            raise ValueError("exchange rate must be positive")
        return rate
