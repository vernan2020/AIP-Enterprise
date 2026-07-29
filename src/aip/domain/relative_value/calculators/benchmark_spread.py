from __future__ import annotations

from decimal import Decimal

from aip.domain.relative_value.exceptions import BenchmarkNotAvailableError, SpreadCalculationError


class BenchmarkSpreadCalculator:
    """Calculate benchmark spread relative to a supplied benchmark yield."""

    def calculate(self, observed_yield: Decimal, benchmark_yield: Decimal | None) -> Decimal:
        if benchmark_yield is None:
            raise BenchmarkNotAvailableError("Benchmark yield is unavailable")
        if benchmark_yield < 0:
            raise SpreadCalculationError("Benchmark yield cannot be negative")
        return observed_yield - benchmark_yield
