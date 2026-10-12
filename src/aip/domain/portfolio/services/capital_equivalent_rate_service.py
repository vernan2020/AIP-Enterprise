from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.portfolio.services.portfolio_capital_consumption_service import (
    REGULATORY_WEIGHTS,
    ExposureClass,
)


@dataclass(frozen=True, slots=True)
class CapitalEquivalentRateInput:
    """Annual decimal rates (0.08 = 8%), not percentage-point inputs."""

    invested_amount_crc: Decimal
    regulatory_exposure_crc: Decimal
    annual_net_yield: Decimal
    exposure_class: ExposureClass
    annual_cost_of_equity: Decimal
    reference_exposure_class: ExposureClass = ExposureClass.GOVERNMENT_CRC
    target_capital_adequacy: Decimal = Decimal("0.16")


@dataclass(frozen=True, slots=True)
class CapitalEquivalentRateResult:
    risk_weight: Decimal
    reference_risk_weight: Decimal
    target_capital_adequacy: Decimal
    required_capital_crc: Decimal
    annual_equity_charge_crc: Decimal
    annual_equity_charge_rate: Decimal
    original_annual_net_yield: Decimal
    yield_net_of_equity_charge: Decimal
    equivalent_yield_at_reference_risk_weight: Decimal
    yield_required_for_reference_parity: Decimal


class CapitalEquivalentRateService:
    """Economic capital comparison, not an official SUGEF capital charge.

    Capital allocated = regulatory exposure * risk weight * SP target.
    Annual cost of equity = allocated capital * annual equity hurdle.
    Rates are expressed relative to amount invested, which need not equal
    regulatory credit exposure. Funding and tax costs must be incorporated
    in annual_net_yield by the caller if relevant.

    The charge is an allocation proxy: actual incremental institution-wide
    capital depends on the full solvency denominator and regulatory buffers.
    """

    @staticmethod
    def calculate(item: CapitalEquivalentRateInput) -> CapitalEquivalentRateResult:
        money = (item.invested_amount_crc, item.regulatory_exposure_crc)
        if any(not value.is_finite() for value in money) or money[0] <= 0 or money[1] < 0:
            raise ValueError(
                "Invested amount must be positive and regulatory exposure non-negative"
            )
        rates = (
            item.annual_net_yield,
            item.annual_cost_of_equity,
            item.target_capital_adequacy,
        )
        if any(not rate.is_finite() for rate in rates):
            raise ValueError("Yield, cost of equity and capital target must be finite")
        if item.annual_cost_of_equity < 0 or not Decimal("0") < item.target_capital_adequacy <= 1:
            raise ValueError("Invalid equity cost or capital adequacy target")
        try:
            weight = REGULATORY_WEIGHTS[item.exposure_class]
            reference_weight = REGULATORY_WEIGHTS[item.reference_exposure_class]
        except KeyError as exc:
            raise ValueError("Unverified risk-weight classification") from exc

        capital = item.regulatory_exposure_crc * weight * item.target_capital_adequacy
        charge = capital * item.annual_cost_of_equity
        charge_rate = charge / item.invested_amount_crc
        reference_charge_rate = (
            item.regulatory_exposure_crc
            * reference_weight
            * item.target_capital_adequacy
            * item.annual_cost_of_equity
            / item.invested_amount_crc
        )
        # Equivalence: a reference-weight investment earning this yield has
        # the same after-equity-charge yield as the original investment.
        equivalent = item.annual_net_yield - charge_rate + reference_charge_rate
        # Required yield for an investment with the selected weight to be
        # equivalent to a reference-weight investment paying original yield.
        parity = item.annual_net_yield + charge_rate - reference_charge_rate
        return CapitalEquivalentRateResult(
            risk_weight=weight,
            reference_risk_weight=reference_weight,
            target_capital_adequacy=item.target_capital_adequacy,
            required_capital_crc=capital,
            annual_equity_charge_crc=charge,
            annual_equity_charge_rate=charge_rate,
            original_annual_net_yield=item.annual_net_yield,
            yield_net_of_equity_charge=item.annual_net_yield - charge_rate,
            equivalent_yield_at_reference_risk_weight=equivalent,
            yield_required_for_reference_parity=parity,
        )
