from __future__ import annotations

from abc import ABC, abstractmethod

from aip.domain.financial_math.curves.yield_curve import YieldCurve


class MarketCurveProvider(ABC):
    """Protocol-like port for obtaining a reference curve."""

    @abstractmethod
    def get_curve(self, identifier: str) -> YieldCurve:
        """Return a curve for the supplied identifier."""
