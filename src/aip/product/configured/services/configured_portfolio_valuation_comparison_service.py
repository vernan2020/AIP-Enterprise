from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from aip.domain.portfolio.services.portfolio_valuation_comparison_service import (
    PortfolioValuationComparisonInput,
    PortfolioValuationComparisonResult,
    PortfolioValuationComparisonService,
)


class ConfiguredPortfolioValuationComparisonService:
    """Build governed valuation comparison inputs from the monthly Investment Master."""

    @classmethod
    def calculate(cls, portfolio: dict[str, Any]) -> PortfolioValuationComparisonResult:
        inputs = tuple(
            cls._input_from_position(position)
            for position in portfolio.get("positions", ())
            if isinstance(position, dict)
        )
        return PortfolioValuationComparisonService.calculate(inputs)

    @classmethod
    def _input_from_position(
        cls,
        position: dict[str, Any],
    ) -> PortfolioValuationComparisonInput:
        raw = position.get("valuation_comparison_source")
        source = raw if isinstance(raw, dict) else {}
        source_file = str(source.get("source_file") or position.get("source_file") or "").strip()
        source_row = source.get("source_row") or position.get("source_row")
        source_reference = source_file or "Maestro de Inversiones"
        if source_row not in (None, ""):
            source_reference = f"{source_reference} · fila {source_row}"

        identity = (
            str(position.get("isin") or "").strip()
            or str(position.get("series") or "").strip()
            or source_reference
        )
        return PortfolioValuationComparisonInput(
            identity=identity,
            issuer=str(position.get("issuer") or "").strip(),
            currency=str(source.get("currency") or "").strip().upper(),
            market_value=cls._decimal_or_none(source.get("market_value")),
            book_value=cls._decimal_or_none(source.get("book_value")),
            source_reference=source_reference,
        )

    @staticmethod
    def _decimal_or_none(value: Any) -> Decimal | None:
        if value in (None, ""):
            return None
        try:
            number = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None
        return number if number.is_finite() else None
