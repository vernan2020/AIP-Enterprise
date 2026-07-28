from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PortfolioAssetProvider(ABC):
    """Port for retrieving assets relevant to liquidity policy evaluation."""

    @abstractmethod
    def get_assets(self, portfolio_reference: str) -> tuple[dict[str, Any], ...]:
        raise NotImplementedError
