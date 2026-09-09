from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from aip.domain.irrbb.models import BankingBookSide, CashFlowDirection, IRRBBTimeBucket
from aip.shared.money import Money


class SugefGapExposureType(str, Enum):
    """Origin of an amount included in the SUGEF standard repricing-gap report."""

    CONTRACTUAL_PAYMENT = "CONTRACTUAL_PAYMENT"
    REPRICING_PRINCIPAL = "REPRICING_PRINCIPAL"


class SugefGapCounterpartyFamily(str, Enum):
    """Supervisory liability counterparty taxonomy visible in the SUGEF workbook."""

    PUBLIC = "PUBLIC"
    BCCR = "BCCR"
    FINANCIAL_ENTITY = "FINANCIAL_ENTITY"
    NON_FINANCIAL_ENTITY = "NON_FINANCIAL_ENTITY"
    OTHER = "OTHER"


class SugefGapFundingTermType(str, Enum):
    """Sight/term discriminator required by the SUGEF liability rows."""

    SIGHT = "SIGHT"
    TERM = "TERM"
    UNKNOWN = "UNKNOWN"


class SugefGapReportLine(str, Enum):
    """Exact logical row families in the visible MN/ME supervisory templates."""

    INVESTMENT_FIXED = "INVESTMENT_FIXED"
    INVESTMENT_VARIABLE_SEMIVARIABLE = "INVESTMENT_VARIABLE_SEMIVARIABLE"
    CREDIT_FIXED = "CREDIT_FIXED"
    CREDIT_VARIABLE_SEMIVARIABLE = "CREDIT_VARIABLE_SEMIVARIABLE"

    PUBLIC_SIGHT_WITH_COST = "PUBLIC_SIGHT_WITH_COST"
    PUBLIC_SIGHT_WITHOUT_COST = "PUBLIC_SIGHT_WITHOUT_COST"
    PUBLIC_TERM_FIXED = "PUBLIC_TERM_FIXED"
    PUBLIC_TERM_VARIABLE_SEMIVARIABLE = "PUBLIC_TERM_VARIABLE_SEMIVARIABLE"

    BCCR_SIGHT_WITH_COST = "BCCR_SIGHT_WITH_COST"
    BCCR_SIGHT_WITHOUT_COST = "BCCR_SIGHT_WITHOUT_COST"
    BCCR_TERM_FIXED = "BCCR_TERM_FIXED"
    BCCR_TERM_VARIABLE_SEMIVARIABLE = "BCCR_TERM_VARIABLE_SEMIVARIABLE"

    FINANCIAL_ENTITY_SIGHT_WITH_COST = "FINANCIAL_ENTITY_SIGHT_WITH_COST"
    FINANCIAL_ENTITY_SIGHT_WITHOUT_COST = "FINANCIAL_ENTITY_SIGHT_WITHOUT_COST"
    FINANCIAL_ENTITY_TERM_FIXED = "FINANCIAL_ENTITY_TERM_FIXED"
    FINANCIAL_ENTITY_TERM_VARIABLE_SEMIVARIABLE = (
        "FINANCIAL_ENTITY_TERM_VARIABLE_SEMIVARIABLE"
    )


class SugefGapRowClassificationStatus(str, Enum):
    """Outcome of mapping one normalized position into a supervisory report row."""

    MAPPED = "MAPPED"
    INCOMPLETE = "INCOMPLETE"
    MAPPING_PENDING = "MAPPING_PENDING"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class SugefGapRoutingMetadata:
    """SUGEF-specific row-routing metadata kept outside the core banking-book model."""

    position_id: str
    counterparty_family: SugefGapCounterpartyFamily = SugefGapCounterpartyFamily.OTHER
    funding_term_type: SugefGapFundingTermType = SugefGapFundingTermType.UNKNOWN
    has_financial_cost: bool | None = None
    accounting_account_code: str | None = None

    def __post_init__(self) -> None:
        if not self.position_id.strip():
            raise ValueError("routing position_id is required")
        if self.accounting_account_code is not None and not self.accounting_account_code.strip():
            raise ValueError("accounting_account_code cannot be blank")


@dataclass(frozen=True, slots=True)
class SugefGapRowClassification:
    """Auditable result of assigning a position to a visible SUGEF report row."""

    position_id: str
    status: SugefGapRowClassificationStatus
    report_line: SugefGapReportLine | None
    reason: str

    def __post_init__(self) -> None:
        if not self.position_id.strip():
            raise ValueError("classification position_id is required")
        if not self.reason.strip():
            raise ValueError("classification reason is required")
        if self.status is SugefGapRowClassificationStatus.MAPPED and self.report_line is None:
            raise ValueError("mapped classification requires report_line")
        if self.status is not SugefGapRowClassificationStatus.MAPPED and self.report_line is not None:
            raise ValueError("non-mapped classification cannot contain report_line")


@dataclass(frozen=True, slots=True)
class SugefGapScheduleRecord:
    """Normalized contractual schedule record for the SUGEF gap methodology.

    Amortizing floating-rate instruments require enough principal information to
    determine the outstanding principal immediately after the payment occurring
    at, or immediately before, the next contractual repricing date. A source may
    provide that balance directly through ``outstanding_principal_after`` or may
    provide ``principal_component`` for every payment needed to derive it.
    """

    payment_date: date
    amount: Money
    direction: CashFlowDirection
    flow_type: str
    source_reference: str
    principal_component: Money | None = None
    outstanding_principal_after: Money | None = None

    def __post_init__(self) -> None:
        if self.amount.amount < 0:
            raise ValueError("schedule amount must be non-negative")
        if not self.flow_type.strip():
            raise ValueError("schedule flow_type is required")
        if not self.source_reference.strip():
            raise ValueError("schedule source_reference is required")
        for name, value in (
            ("principal_component", self.principal_component),
            ("outstanding_principal_after", self.outstanding_principal_after),
        ):
            if value is None:
                continue
            if value.currency is not self.amount.currency:
                raise ValueError(f"{name} currency must match schedule amount currency")
            if value.amount < 0:
                raise ValueError(f"{name} must be non-negative")


@dataclass(frozen=True, slots=True)
class SugefGapExposure:
    """One auditable amount assigned to a repricing-risk date for SUGEF GAP."""

    position_id: str
    side: BankingBookSide
    direction: CashFlowDirection
    amount: Money
    risk_date: date
    exposure_type: SugefGapExposureType
    source_reference: str

    def __post_init__(self) -> None:
        if not self.position_id.strip():
            raise ValueError("gap exposure position_id is required")
        if self.amount.amount < 0:
            raise ValueError("gap exposure amount must be non-negative")
        if not self.source_reference.strip():
            raise ValueError("gap exposure source_reference is required")


@dataclass(frozen=True, slots=True)
class SugefGapBucketTotal:
    """Aggregated amount for one of the nineteen SUGEF temporal bands."""

    bucket: IRRBBTimeBucket
    ordinal: int
    label: str
    amount: Money
