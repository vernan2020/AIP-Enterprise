from __future__ import annotations

from decimal import Decimal


class NominalSpreadCalculator:
    """Calculate nominal spread as the difference between observed yield and benchmark yield."""

    def calculate(self, observed_yield: Decimal, benchmark_yield: Decimal | None) -> Decimal:
        if benchmark_yield is None:
            return observed_yield - observed_yield
        return observed_yield - benchmark_yield
