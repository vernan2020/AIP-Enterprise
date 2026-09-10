from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from aip.domain.irrbb.models import IRRBBMethodologyProfile, IRRBBScenario
from aip.shared.money import Currency, Money


class NIIBalanceSheetAssumption(str, Enum):
    """Balance-sheet projection convention disclosed by the NII methodology."""

    RUN_OFF = "RUN_OFF"
    CONSTANT = "CONSTANT"
    DYNAMIC = "DYNAMIC"


class NIIShockTiming(str, Enum):
    """Timing convention used by the supplied stressed NII projection."""

    INSTANTANEOUS = "INSTANTANEOUS"
    GRADUAL = "GRADUAL"
    OTHER = "OTHER"


class NIIAccrualType(str, Enum):
    """Accounting direction of one projected interest accrual."""

    INTEREST_INCOME = "INTEREST_INCOME"
    INTEREST_EXPENSE = "INTEREST_EXPENSE"


class NIIAccrualAmountStatus(str, Enum):
    """Audit status for the amount of an NII accrual."""

    CONTRACTUAL = "CONTRACTUAL"
    SOURCE_PROVIDED = "SOURCE_PROVIDED"
    RATE_PROJECTED = "RATE_PROJECTED"
    BEHAVIORAL = "BEHAVIORAL"


@dataclass(frozen=True, slots=True)
class NIIProjectionBasis:
    """Versioned projection perimeter shared by BASE and stressed NII results."""

    methodology: IRRBBMethodologyProfile
    valuation_date: date
    horizon_end_date: date
    balance_sheet_assumption: NIIBalanceSheetAssumption
    shock_timing: NIIShockTiming
    source_reference: str

    def __post_init__(self) -> None:
        if self.horizon_end_date <= self.valuation_date:
            raise ValueError("NII horizon_end_date must be after valuation_date")
        if not self.source_reference.strip():
            raise ValueError("NII projection source_reference is required")


@dataclass(frozen=True, slots=True)
class NIIRepricingTrace:
    """Explicit rate-pricing trace for a rate-projected NII accrual.

    The trace records which rate source and tenor were used. It does not prescribe
    how a curve, reference index, spread, floor, cap or replacement transaction was
    produced; those responsibilities remain with an approved projection strategy.
    """

    rate_reference: str
    repricing_date: date
    pricing_tenor_months: int
    applied_rate: Decimal
    source_reference: str

    def __post_init__(self) -> None:
        if not self.rate_reference.strip():
            raise ValueError("NII repricing rate_reference is required")
        if self.pricing_tenor_months <= 0:
            raise ValueError("NII pricing_tenor_months must be positive")
        if not self.applied_rate.is_finite():
            raise ValueError("NII applied_rate must be finite")
        if not self.source_reference.strip():
            raise ValueError("NII repricing source_reference is required")


@dataclass(frozen=True, slots=True)
class NIIInterestAccrual:
    """One explicit interest-income or interest-expense amount in an NII projection."""

    accrual_id: str
    position_id: str
    scenario: IRRBBScenario
    accrual_type: NIIAccrualType
    amount: Money
    accrual_start_date: date
    accrual_end_date: date
    source_reference: str
    amount_status: NIIAccrualAmountStatus = NIIAccrualAmountStatus.SOURCE_PROVIDED
    repricing_trace: NIIRepricingTrace | None = None
    projection_basis: str | None = None

    def __post_init__(self) -> None:
        if not self.accrual_id.strip():
            raise ValueError("NII accrual_id is required")
        if not self.position_id.strip():
            raise ValueError("NII position_id is required")
        if not self.amount.amount.is_finite():
            raise ValueError("NII accrual amount must be finite")
        if self.accrual_end_date <= self.accrual_start_date:
            raise ValueError("NII accrual_end_date must be after accrual_start_date")
        if not self.source_reference.strip():
            raise ValueError("NII accrual source_reference is required")
        if self.projection_basis is not None and not self.projection_basis.strip():
            raise ValueError("NII projection_basis cannot be blank")
        if (
            self.repricing_trace is not None
            and self.repricing_trace.repricing_date > self.accrual_start_date
        ):
            raise ValueError(
                "NII repricing_date cannot occur after accrual_start_date; "
                "split the accrual at the repricing boundary"
            )
        if self.amount_status is NIIAccrualAmountStatus.RATE_PROJECTED:
            if self.repricing_trace is None:
                raise ValueError("rate-projected NII accrual requires repricing_trace")
            if self.projection_basis is None:
                raise ValueError("rate-projected NII accrual requires projection_basis")


@dataclass(frozen=True, slots=True)
class ConvertedNIIAccrual:
    """One NII accrual converted into the requested reporting currency."""

    accrual: NIIInterestAccrual
    exchange_rate: Decimal
    amount_reporting: Money
    signed_nii_contribution: Money

    def __post_init__(self) -> None:
        if not self.exchange_rate.is_finite() or self.exchange_rate <= 0:
            raise ValueError("NII exchange_rate must be finite and positive")
        if self.amount_reporting.currency is not self.signed_nii_contribution.currency:
            raise ValueError("converted NII accrual currencies must match")
        if not self.amount_reporting.amount.is_finite():
            raise ValueError("converted NII amount must be finite")
        if not self.signed_nii_contribution.amount.is_finite():
            raise ValueError("signed NII contribution must be finite")

        expected_amount = self.accrual.amount.amount * self.exchange_rate
        if self.amount_reporting.amount != expected_amount:
            raise ValueError(
                "converted NII amount must reconcile to source amount and FX"
            )

        expected_contribution = expected_amount
        if self.accrual.accrual_type is NIIAccrualType.INTEREST_EXPENSE:
            expected_contribution = -expected_amount
        if self.signed_nii_contribution.amount != expected_contribution:
            raise ValueError("signed NII contribution must reconcile to accrual type")


@dataclass(frozen=True, slots=True)
class NetInterestIncomeResult:
    """Projected net interest income for one scenario and one common basis."""

    basis: NIIProjectionBasis
    scenario: IRRBBScenario
    reporting_currency: Currency
    interest_income: Money
    interest_expense: Money
    net_interest_income: Money
    accruals: tuple[ConvertedNIIAccrual, ...]

    def __post_init__(self) -> None:
        for value in (
            self.interest_income,
            self.interest_expense,
            self.net_interest_income,
        ):
            if value.currency is not self.reporting_currency:
                raise ValueError("NII result money must use reporting_currency")
            if not value.amount.is_finite():
                raise ValueError("NII result amounts must be finite")

        if not self.accruals:
            raise ValueError("NII result requires at least one converted accrual")

        seen_ids: set[str] = set()
        expected_income = Decimal("0")
        expected_expense = Decimal("0")
        for converted in self.accruals:
            if converted.accrual.accrual_id in seen_ids:
                raise ValueError(
                    f"duplicate NII result accrual_id: {converted.accrual.accrual_id}"
                )
            seen_ids.add(converted.accrual.accrual_id)
            if converted.accrual.scenario is not self.scenario:
                raise ValueError(
                    "NII result accrual scenario must match result scenario"
                )
            if converted.amount_reporting.currency is not self.reporting_currency:
                raise ValueError("converted NII accrual must use reporting_currency")
            if converted.signed_nii_contribution.currency is not self.reporting_currency:
                raise ValueError("signed NII contribution must use reporting_currency")

            if converted.accrual.accrual_type is NIIAccrualType.INTEREST_INCOME:
                expected_income += converted.amount_reporting.amount
            else:
                expected_expense += converted.amount_reporting.amount

        if self.interest_income.amount != expected_income:
            raise ValueError("NII interest_income must reconcile to accrual detail")
        if self.interest_expense.amount != expected_expense:
            raise ValueError("NII interest_expense must reconcile to accrual detail")
        if self.net_interest_income.amount != expected_income - expected_expense:
            raise ValueError(
                "net_interest_income must equal interest income minus expense"
            )


@dataclass(frozen=True, slots=True)
class NIIScenarioAssessment:
    """Delta NII for one stressed scenario relative to BASE."""

    scenario: IRRBBScenario
    nii: Money
    delta_nii: Money
    fall_from_base: Money

    def __post_init__(self) -> None:
        if self.scenario is IRRBBScenario.BASE:
            raise ValueError("NII stress assessment cannot use BASE")
        currencies = {
            self.nii.currency,
            self.delta_nii.currency,
            self.fall_from_base.currency,
        }
        if len(currencies) != 1:
            raise ValueError("NII assessment currencies must match")
        for value in (self.nii, self.delta_nii, self.fall_from_base):
            if not value.amount.is_finite():
                raise ValueError("NII assessment amounts must be finite")
        if self.fall_from_base.amount < 0:
            raise ValueError("NII fall_from_base cannot be negative")


@dataclass(frozen=True, slots=True)
class DeltaNIIResult:
    """Worst projected NII fall across an explicitly requested stress set."""

    basis: NIIProjectionBasis
    reporting_currency: Currency
    base_nii: Money
    worst_scenario: IRRBBScenario
    worst_loss: Money
    assessments: tuple[NIIScenarioAssessment, ...]

    def __post_init__(self) -> None:
        if self.base_nii.currency is not self.reporting_currency:
            raise ValueError("Delta NII base currency must match reporting_currency")
        if self.worst_loss.currency is not self.reporting_currency:
            raise ValueError(
                "Delta NII worst-loss currency must match reporting_currency"
            )
        if (
            not self.base_nii.amount.is_finite()
            or not self.worst_loss.amount.is_finite()
        ):
            raise ValueError("Delta NII base and worst-loss amounts must be finite")
        if self.worst_loss.amount < 0:
            raise ValueError("Delta NII worst_loss cannot be negative")
        if not self.assessments:
            raise ValueError("Delta NII requires at least one stress assessment")

        seen_scenarios: set[IRRBBScenario] = set()
        for assessment in self.assessments:
            if assessment.scenario in seen_scenarios:
                raise ValueError(
                    f"duplicate Delta NII assessment scenario: {assessment.scenario.value}"
                )
            seen_scenarios.add(assessment.scenario)
            if assessment.nii.currency is not self.reporting_currency:
                raise ValueError(
                    "Delta NII assessment currency must match reporting_currency"
                )

            expected_delta = assessment.nii.amount - self.base_nii.amount
            expected_fall = max(-expected_delta, Decimal("0"))
            if assessment.delta_nii.amount != expected_delta:
                raise ValueError("Delta NII assessment must reconcile to base NII")
            if assessment.fall_from_base.amount != expected_fall:
                raise ValueError("Delta NII fall must reconcile to assessment delta")

        matching_worst = next(
            (
                assessment
                for assessment in self.assessments
                if assessment.scenario is self.worst_scenario
            ),
            None,
        )
        if matching_worst is None:
            raise ValueError("Delta NII worst_scenario must be present in assessments")

        maximum_loss = max(
            assessment.fall_from_base.amount for assessment in self.assessments
        )
        if self.worst_loss.amount != maximum_loss:
            raise ValueError("Delta NII worst_loss must equal maximum assessment fall")
        if matching_worst.fall_from_base.amount != self.worst_loss.amount:
            raise ValueError(
                "Delta NII worst_scenario must identify a maximum-loss scenario"
            )
