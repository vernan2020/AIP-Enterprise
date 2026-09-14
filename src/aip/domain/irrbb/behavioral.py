from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.irrbb.models import IRRBBMethodologyProfile, IRRBBScenario


@dataclass(frozen=True, slots=True)
class NonMaturityDepositAllocation:
    """One approved NMD maturity-allocation point relative to the valuation date."""

    tenor_months: int
    weight: Decimal

    def __post_init__(self) -> None:
        if self.tenor_months < 0:
            raise ValueError("NMD tenor_months cannot be negative")
        if self.weight < 0 or self.weight > 1:
            raise ValueError("NMD allocation weight must be between zero and one")


@dataclass(frozen=True, slots=True)
class NonMaturityDepositProfile:
    """Versioned, scenario-specific NMD behavioral maturity profile.

    The profile is an injected assumption. The domain never derives these weights
    from the mere fact that a deposit is withdrawable on demand.
    """

    methodology: IRRBBMethodologyProfile
    scenario: IRRBBScenario
    source_reference: str
    allocations: tuple[NonMaturityDepositAllocation, ...]

    def __post_init__(self) -> None:
        if not self.source_reference.strip():
            raise ValueError("NMD profile source_reference is required")
        if not self.allocations:
            raise ValueError("NMD profile requires at least one allocation")
        if sum((item.weight for item in self.allocations), Decimal("0")) != Decimal("1"):
            raise ValueError("NMD allocation weights must sum exactly to one")
        tenors = tuple(item.tenor_months for item in self.allocations)
        if len(set(tenors)) != len(tenors):
            raise ValueError("NMD allocation tenors must be unique")
