from __future__ import annotations

from typing import Any


class PortfolioLiquidityComposer:
    """Compose portfolio-derived liquidity capacities without duplicating business calculations."""

    @staticmethod
    def compose(portfolio: dict[str, Any], liquidity: dict[str, Any]) -> dict[str, Any]:
        result = dict(liquidity)

        if "hqla_value_crc" in portfolio:
            result["hqla_capacity"] = float(portfolio.get("hqla_value_crc") or 0.0)

        if "mil_value_crc" in portfolio:
            result["mil_eligible_capacity"] = float(portfolio.get("mil_value_crc") or 0.0)

        return result
