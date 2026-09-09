from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from aip.shared.money import Currency, Money


class BankingBookSide(str, Enum):
    """Balance-sheet side used by the IRRBB economic-value calculation."""

    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    OFF_BALANCE = "OFF_BALANCE"


class CashFlowDirection(str, Enum):
    """Economic direction of a future cash flow."""

    RECEIVABLE = "RECEIVABLE"
    PAYABLE = "PAYABLE"


class RateType(str, Enum):
    """Contractual interest-rate behavior."""

    FIXED = "FIXED"
    FLOATING = "FLOATING"


class OptionalityType(str, Enum):
    """Material behavioral or embedded optionality relevant to IRRBB."""

    NONE = "NONE"
    LOAN_PREPAYMENT = "LOAN_PREPAYMENT"
    TERM_DEPOSIT_EARLY_WITHDRAWAL = "TERM_DEPOSIT_EARLY_WITHDRAWAL"
    NON_MATURITY_DEPOSIT = "NON_MATURITY_DEPOSIT"
    OTHER = "OTHER"


class IRRBBScenario(str, Enum):
    """Base case plus the six standard IRRBB stress scenario families."""

    BASE = "BASE"
    PARALLEL_UP = "PARALLEL_UP"
    PARALLEL_DOWN = "PARALLEL_DOWN"
    STEEPENER = "STEEPENER"
    FLATTENER = "FLATTENER"
    SHORT_UP = "SHORT_UP"
    SHORT_DOWN = "SHORT_DOWN"


STANDARD_STRESS_SCENARIOS: tuple[IRRBBScenario, ...] = (
    IRRBBScenario.PARALLEL_UP,
    IRRBBScenario.PARALLEL_DOWN,
    IRRBBScenario.STEEPENER,
    IRRBBScenario.FLATTENER,
    IRRBBScenario.SHORT_UP,
    IRRBBScenario.SHORT_DOWN,
)


class IRRBBTimeBucket(str, Enum):
    """Nineteen temporal buckets used by the target standardized methodology."""

    DAY_1 = "DAY_1"
    DAY_1_TO_MONTH_1 = "DAY_1_TO_MONTH_1"
    MONTH_1_TO_3 = "MONTH_1_TO_3"
    MONTH_3_TO_6 = "MONTH_3_TO_6"
    MONTH_6_TO_9 = "MONTH_6_TO_9"
    MONTH_9_TO_YEAR_1 = "MONTH_9_TO_YEAR_1"
    YEAR_1_TO_1_5 = "YEAR_1_TO_1_5"
    YEAR_1_5_TO_2 = "YEAR_1_5_TO_2"
    YEAR_2_TO_3 = "YEAR_2_TO_3"
    YEAR_3_TO_4 = "YEAR_3_TO_4"
    YEAR_4_TO_5 = "YEAR_4_TO_5"
    YEAR_5_TO_6 = "YEAR_5_TO_6"
    YEAR_6_TO_7 = "YEAR_6_TO_7"
    YEAR_7_TO_8 = "YEAR_7_TO_8"
    YEAR_8_TO_9 = "YEAR_8_TO_9"
    YEAR_9_TO_10 = "YEAR_9_TO_10"
    YEAR_10_TO_15 = "YEAR_10_TO_15"
    YEAR_15_TO_20 = "YEAR_15_TO_20"
    OVER_YEAR_20 = "OVER_YEAR_20"


class IRRBBMethodologyStatus(str, Enum):
    """Governance status for a versioned IRRBB methodology or parameter set."""

    PROPOSED = "PROPOSED"
    EFFECTIVE = "EFFECTIVE"
    INTERNAL = "INTERNAL"


@dataclass(frozen=True, slots=True)
class IRRBBMethodologyProfile:
    """Versioned methodology metadata kept separate from calculation logic."""

    code: str
    version: str
    status: IRRBBMethodologyStatus
    source_reference: str
    effective_from: date | None = None

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("methodology code is required")
        if not self.version.strip():
            raise ValueError("methodology version is required")
        if not self.source_reference.strip():
            raise ValueError("methodology source_reference is required")


@dataclass(frozen=True, slots=True)
class ScenarioShockCalibration:
    """Versioned shock magnitudes; no tenor transformation is assumed here.

    Values are expressed in basis points. The exact construction of steepener,
    flattener and short-rate curves is intentionally delegated to a curve-shock
    strategy so regulatory formulas can be versioned independently.
    """

    methodology: IRRBBMethodologyProfile
    currency: Currency
    parallel_bp: Decimal
    short_bp: Decimal
    long_bp: Decimal

    def __post_init__(self) -> None:
        for name, value in (
            ("parallel_bp", self.parallel_bp),
            ("short_bp", self.short_bp),
            ("long_bp", self.long_bp),
        ):
            if value < 0:
                raise ValueError(f"{name} cannot be negative")


@dataclass(frozen=True, slots=True)
class BankingBookPosition:
    """Source-independent canonical contract for a rate-sensitive position.

    Optional fields deliberately permit incomplete source records to enter a
    data-quality workflow. Missing data must be diagnosed before a calculation
    that requires it; it must never be silently imputed.
    """

    position_id: str
    product_type: str
    side: BankingBookSide
    currency: Currency
    principal: Money
    rate_type: RateType
    maturity_date: date | None
    source_reference: str
    carrying_amount: Money | None = None
    contractual_rate: Decimal | None = None
    reference_rate: str | None = None
    spread: Decimal | None = None
    origination_date: date | None = None
    next_repricing_date: date | None = None
    repricing_frequency_months: int | None = None
    payment_frequency_months: int | None = None
    optionality: OptionalityType = OptionalityType.NONE

    def __post_init__(self) -> None:
        if not self.position_id.strip():
            raise ValueError("position_id is required")
        if not self.product_type.strip():
            raise ValueError("product_type is required")
        if not self.source_reference.strip():
            raise ValueError("source_reference is required")
        if self.principal.currency is not self.currency:
            raise ValueError("principal currency must match position currency")
        if self.carrying_amount is not None and self.carrying_amount.currency is not self.currency:
            raise ValueError("carrying_amount currency must match position currency")
        if self.principal.amount < 0:
            raise ValueError("principal cannot be negative")
        if self.repricing_frequency_months is not None and self.repricing_frequency_months <= 0:
            raise ValueError("repricing_frequency_months must be positive")
        if self.payment_frequency_months is not None and self.payment_frequency_months <= 0:
            raise ValueError("payment_frequency_months must be positive")


@dataclass(frozen=True, slots=True)
class IRRBBCashFlow:
    """Canonical future cash flow after contractual/behavioral transformation.

    ``cashflow_date`` is the payment date. ``risk_date`` is the date used by the
    repricing/bucketing strategy; it may differ from payment date for positions
    that reprice before contractual maturity.
    """

    position_id: str
    side: BankingBookSide
    direction: CashFlowDirection
    amount: Money
    cashflow_date: date
    risk_date: date
    flow_type: str
    source_reference: str

    def __post_init__(self) -> None:
        if not self.position_id.strip():
            raise ValueError("cash-flow position_id is required")
        if not self.flow_type.strip():
            raise ValueError("flow_type is required")
        if not self.source_reference.strip():
            raise ValueError("cash-flow source_reference is required")
        if self.amount.amount < 0:
            raise ValueError("cash-flow amount must be non-negative; use direction for sign")


@dataclass(frozen=True, slots=True)
class TimeBucketAssignment:
    """Auditable mapping of one risk date into one standardized time bucket."""

    bucket: IRRBBTimeBucket
    ordinal: int
    label: str
    valuation_date: date
    risk_date: date


@dataclass(frozen=True, slots=True)
class DiscountedCashFlow:
    """Per-flow valuation trace in the reporting currency."""

    cashflow: IRRBBCashFlow
    scenario: IRRBBScenario
    discount_factor: Decimal
    exchange_rate: Decimal
    present_value_reporting: Money
    signed_eve_contribution: Money


@dataclass(frozen=True, slots=True)
class EconomicValueResult:
    """Economic value of equity for one scenario and reporting currency."""

    scenario: IRRBBScenario
    reporting_currency: Currency
    pv_assets: Money
    pv_liabilities: Money
    pv_off_balance_net: Money
    eve: Money
    discounted_cashflows: tuple[DiscountedCashFlow, ...]


@dataclass(frozen=True, slots=True)
class ScenarioAssessment:
    """Change in EVE for one stressed scenario relative to base."""

    scenario: IRRBBScenario
    eve: Money
    delta_eve: Money
    fall_from_base: Money


@dataclass(frozen=True, slots=True)
class DeltaEVEResult:
    """Worst EVE loss and exposure relative to Tier 1 capital."""

    reporting_currency: Currency
    base_eve: Money
    tier_one_capital: Money
    worst_scenario: IRRBBScenario
    worst_loss: Money
    exposure_ratio_to_tier1: Decimal
    assessments: tuple[ScenarioAssessment, ...]


@dataclass(frozen=True, slots=True)
class CapitalBufferTier:
    """One inclusive upper-bound tier in a versioned capital-buffer schedule."""

    label: str
    upper_bound_ratio: Decimal | None
    buffer_rate: Decimal

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("capital-buffer tier label is required")
        if self.upper_bound_ratio is not None and self.upper_bound_ratio < 0:
            raise ValueError("upper_bound_ratio cannot be negative")
        if self.buffer_rate < 0:
            raise ValueError("buffer_rate cannot be negative")


@dataclass(frozen=True, slots=True)
class CapitalBufferSchedule:
    """Versioned tier schedule; regulatory values are injected, never hardcoded."""

    methodology: IRRBBMethodologyProfile
    tiers: tuple[CapitalBufferTier, ...]


@dataclass(frozen=True, slots=True)
class CapitalBufferResult:
    """Capital-buffer lookup result with methodology traceability."""

    methodology: IRRBBMethodologyProfile
    exposure_ratio: Decimal
    buffer_rate: Decimal
    matched_tier_label: str
