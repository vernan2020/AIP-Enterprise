from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.relative_value.enums.valuation_status import ValuationStatus


@dataclass(frozen=True, slots=True)
class RichCheapScore:
    """Classify an opportunity as rich, fair, or cheap from a spread measure."""

    spread: Decimal

    def __post_init__(self) -> None:
        if not self.spread.is_finite():
            raise ValueError("Spread must be a finite decimal")

    @property
    def status(self) -> ValuationStatus:
        if self.spread < Decimal("0"):
            return ValuationStatus.RICH
        if self.spread > Decimal("0"):
            return ValuationStatus.CHEAP
        return ValuationStatus.FAIR
