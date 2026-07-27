from enum import Enum


class AmortizationType(Enum):
    """Amortization pattern for the notional."""

    BULLET = "bullet"
    AMORTIZING = "amortizing"
