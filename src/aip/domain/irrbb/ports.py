from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Protocol

from aip.domain.irrbb.models import (
    BankingBookPosition,
    IRRBBCashFlow,
    IRRBBScenario,
    ScenarioShockCalibration,
)
from aip.shared.money import Currency, Money


class BankingBookPositionRepository(Protocol):
    """Source-agnostic port for canonical banking-book positions."""

    def get_positions(self, *, cutoff_date: date) -> tuple[BankingBookPosition, ...]: ...


class RepricingCashFlowBuilder(Protocol):
    """Build repricing-aware cash flows from one canonical position.

    Instrument-specific implementations own contractual schedules. Investment
    implementations must adapt/reuse the existing PortfolioContractualCashFlowService
    rather than create a second coupon calendar.
    """

    def build(
        self,
        *,
        position: BankingBookPosition,
        valuation_date: date,
    ) -> tuple[IRRBBCashFlow, ...]: ...


class BehavioralCashFlowModel(Protocol):
    """Apply approved optionality assumptions without embedding them in UI code."""

    def apply(
        self,
        *,
        position: BankingBookPosition,
        contractual_cashflows: tuple[IRRBBCashFlow, ...],
        scenario: IRRBBScenario,
        valuation_date: date,
    ) -> tuple[IRRBBCashFlow, ...]: ...


class DiscountFactorProvider(Protocol):
    """Provide discount factors from versioned base or shocked curves."""

    def discount_factor(
        self,
        *,
        currency: Currency,
        scenario: IRRBBScenario,
        valuation_date: date,
        payment_date: date,
    ) -> Decimal: ...


class ExchangeRateProvider(Protocol):
    """Provide an explicit spot conversion into the reporting currency."""

    def rate(
        self,
        *,
        from_currency: Currency,
        to_currency: Currency,
        valuation_date: date,
    ) -> Decimal: ...


class ScenarioCurveShocker(Protocol):
    """Versionable curve-shock policy.

    No steepener/flattener interpolation formula is assumed by the domain core;
    the implementation must be tied to an approved methodology version.
    """

    def shocked_rate(
        self,
        *,
        base_rate: Decimal,
        tenor_years: Decimal,
        scenario: IRRBBScenario,
        calibration: ScenarioShockCalibration,
    ) -> Decimal: ...


class TierOneCapitalProvider(Protocol):
    """Port for Tier 1 capital used as the RTILB exposure denominator."""

    def tier_one_capital(
        self,
        *,
        cutoff_date: date,
        reporting_currency: Currency,
    ) -> Money: ...
