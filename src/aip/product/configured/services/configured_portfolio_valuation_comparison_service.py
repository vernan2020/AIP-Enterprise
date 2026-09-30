from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from aip.domain.portfolio.services.portfolio_valuation_comparison_service import (
    PortfolioValuationComparisonService,
    ValuationComparisonInput,
    ValuationComparisonResult,
)

logger = logging.getLogger(__name__)


class ConfiguredPortfolioValuationComparisonService:
    """Use preserved master amounts; never use the legacy zero/CRC fallbacks."""

    @staticmethod
    def _amount(value: object) -> Decimal | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            result = Decimal(str(value))
        except InvalidOperation:
            return None
        return result if result.is_finite() else None

    @classmethod
    def calculate(cls, portfolio: dict[str, Any]) -> ValuationComparisonResult:
        inputs: list[ValuationComparisonInput] = []
        for position in portfolio.get("positions", ()):
            raw = position.get("valuation_comparison_source")
            source = raw if isinstance(raw, dict) else {}
            inputs.append(
                ValuationComparisonInput(
                    identity=str(position.get("isin") or position.get("series") or "N/D"),
                    issuer=str(position.get("issuer") or "N/D"),
                    currency=str(source.get("currency") or ""),
                    market_value=cls._amount(source.get("market_value")),
                    book_value=cls._amount(source.get("book_value")),
                    source_reference=(
                        f"{position.get('source_file') or 'N/D'} · "
                        f"fila {position.get('source_row') or 'N/D'}"
                    ),
                )
            )
        result = PortfolioValuationComparisonService.calculate(tuple(inputs))
        logger.info(
            "Portfolio valuation comparison: cutoff=%s positions=%d included=%d",
            portfolio.get("valuation_date"),
            len(result.rows),
            sum(item.included_count for item in result.totals),
        )
        return result
