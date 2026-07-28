from __future__ import annotations

from decimal import Decimal

from aip.domain.liquidity.cashflow.exceptions import ProjectionError


class AmortizationProjection:
    """Compute an amortization amount from a balance and amortization rate."""

    def project(self, outstanding_balance: Decimal, amortization_rate: Decimal) -> Decimal:
        if outstanding_balance < 0:
            raise ProjectionError("Outstanding balance cannot be negative")
        if amortization_rate < 0:
            raise ProjectionError("Amortization rate cannot be negative")
        if amortization_rate > 1:
            raise ProjectionError("Amortization rate cannot exceed 100%")
        return outstanding_balance * amortization_rate
