from __future__ import annotations

from decimal import Decimal

from aip.domain.liquidity.cashflow.exceptions import ProjectionError


class RolloverProjection:
    """Apply a rollover rate to a cash flow amount."""

    def project(self, amount: Decimal, rate: Decimal) -> Decimal:
        if amount < 0:
            raise ProjectionError("Amount cannot be negative")
        if rate < 0 or rate > 1:
            raise ProjectionError("Rollover rate must be between 0 and 1")
        return amount * rate
