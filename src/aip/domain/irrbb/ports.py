from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Protocol

from aip.domain.irrbb.behavioral import NonMaturityDepositProfile
from aip.domain.irrbb.models import (
    BankingBookPosition,
    ContractualCashFlowRecord,
    IRRBBCashFlow,
    IRRBBScenario,
    ScenarioShockCalibration,
)
from aip.domain.irrbb.scenario_repricing import FloatingRateCouponBasis
from aip.shared.money import Currency, Money


class BankingBookPositionRepository(Protocol):
    """Source-agnostic port for canonical banking-book positions."""

    def get_positions(self, *, cutoff_date: date) -> tuple[BankingBookPosition, ...]: ...


class ContractualCashFlowScheduleProvider(Protocol):
    """Provide an explicit normalized schedule when terms alone are insufficient.

    Typical uses include amortizing credit, complex deposits, borrowings and
    off-balance contracts. Implementations may read an approved source schedule
    or derive one from sufficiently complete contractual terms outside this port.
    """

    def get_schedule(
        self,
        *,
        position: BankingBookPosition,
        valuation_date: date,
    ) -> tuple[ContractualCashFlowRecord, ...]: ...


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


class ScenarioCashFlowProjector(Protocol):
    """Transform base contractual flows when scenario-sensitive amounts reprice.

    Floating-rate coupons and other scenario-dependent cash flows must pass
    through such a projector before stressed EVE is calculated. The economic-value
    service must not treat a current-rate projection as a stressed contractual flow.
    """

    def project(
        self,
        *,
        position: BankingBookPosition,
        base_cashflows: tuple[IRRBBCashFlow, ...],
        scenario: IRRBBScenario,
        valuation_date: date,
    ) -> tuple[IRRBBCashFlow, ...]: ...


class FloatingRateCouponBasisProvider(Protocol):
    """Provide the approved reset/accrual basis for one projected floating coupon."""

    def basis_for(
        self,
        *,
        position: BankingBookPosition,
        cashflow: IRRBBCashFlow,
        valuation_date: date,
    ) -> FloatingRateCouponBasis | None: ...


class ScenarioReferenceRateProvider(Protocol):
    """Provide a scenario-consistent reference index rate at a contractual reset date."""

    def reference_rate(
        self,
        *,
        reference_rate_code: str,
        currency: Currency,
        scenario: IRRBBScenario,
        reset_date: date,
        valuation_date: date,
    ) -> Decimal: ...


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


class NonMaturityDepositProfileProvider(Protocol):
    """Provide a versioned behavioral maturity profile for one NMD/scenario."""

    def profile_for(
        self,
        *,
        position: BankingBookPosition,
        scenario: IRRBBScenario,
        valuation_date: date,
    ) -> NonMaturityDepositProfile: ...


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


class ScenarioTenorShockProvider(Protocol):
    """Provide the signed tenor shock in basis points for a methodology/scenario."""

    def shock_basis_points(
        self,
        *,
        currency: Currency,
        scenario: IRRBBScenario,
        tenor_years: Decimal,
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
