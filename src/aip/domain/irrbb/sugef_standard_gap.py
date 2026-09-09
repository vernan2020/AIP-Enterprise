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
