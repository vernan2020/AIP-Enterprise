from __future__ import annotations

from typing import Any

from aip.product.demo.data.demo_liquidity_data import DemoLiquidityData


class DemoLiquidityProvider:
    """Adapts demo liquidity data to application-facing output."""

    def get_liquidity(self) -> dict[str, Any]:
        return DemoLiquidityData.build()
