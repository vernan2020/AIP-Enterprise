"""Portfolio calculation domain service."""

from decimal import Decimal
from typing import Sequence

from src.aip.domain.portfolio.exceptions import PortfolioError
from src.aip.shared.money import Currency, Money


class PortfolioCalculationService:
    """Stateless service for reproducible portfolio calculations."""

    @staticmethod
    def portfolio_market_value(positions: Sequence[object], base_currency: Currency) -> Money:
        """Calculate total market value in base currency.

        Args:
            positions: Sequence of position-like objects with market_value and currency.
            base_currency: Expected reporting currency.

        Returns:
            Total market value.

        Raises:
            PortfolioError: If any position currency differs from base currency.
        """
        total = Decimal("0")
        for position in positions:
            if position.currency != base_currency:
                raise PortfolioError("Cannot aggregate market value across different currencies.")
            total += position.market_value.amount
        return Money(total, base_currency)

    @staticmethod
    def portfolio_book_value(positions: Sequence[object], base_currency: Currency) -> Money:
        """Calculate total book value in base currency."""
        total = Decimal("0")
        for position in positions:
            if position.currency != base_currency:
                raise PortfolioError("Cannot aggregate book value across different currencies.")
            total += position.book_value.amount
        return Money(total, base_currency)

    @staticmethod
    def portfolio_nominal_value(positions: Sequence[object], base_currency: Currency) -> Money:
        """Calculate total nominal value in base currency."""
        total = Decimal("0")
        for position in positions:
            if position.currency != base_currency:
                raise PortfolioError("Cannot aggregate nominal value across different currencies.")
            total += position.nominal_value.amount
        return Money(total, base_currency)

    @staticmethod
    def unrealized_gain_or_loss(positions: Sequence[object], base_currency: Currency) -> Money:
        """Calculate unrealized gain/loss as market value minus book value."""
        market = PortfolioCalculationService.portfolio_market_value(positions, base_currency)
        book = PortfolioCalculationService.portfolio_book_value(positions, base_currency)
        return market - book

    @staticmethod
    def weighted_average_yield(positions: Sequence[object], base_currency: Currency) -> Decimal:
        """Calculate weighted average yield using market value as weight base."""
        weighted_sum, total_weight = PortfolioCalculationService._weighted_sum(
            positions=positions,
            base_currency=base_currency,
            metric_getter=lambda pos: pos.yield_rate.value.value,
        )
        if total_weight == Decimal("0"):
            return Decimal("0")
        return weighted_sum / total_weight

    @staticmethod
    def weighted_average_duration(positions: Sequence[object], base_currency: Currency) -> Decimal:
        """Calculate weighted average duration using market value as weight base."""
        weighted_sum, total_weight = PortfolioCalculationService._weighted_sum(
            positions=positions,
            base_currency=base_currency,
            metric_getter=lambda pos: pos.duration.value,
        )
        if total_weight == Decimal("0"):
            return Decimal("0")
        return weighted_sum / total_weight

    @staticmethod
    def weighted_average_convexity(positions: Sequence[object], base_currency: Currency) -> Decimal:
        """Calculate weighted average convexity using market value as weight base."""
        weighted_sum, total_weight = PortfolioCalculationService._weighted_sum(
            positions=positions,
            base_currency=base_currency,
            metric_getter=lambda pos: pos.convexity.value,
        )
        if total_weight == Decimal("0"):
            return Decimal("0")
        return weighted_sum / total_weight

    @staticmethod
    def currency_exposure(positions: Sequence[object]) -> dict[Currency, Money]:
        """Calculate currency exposure from market values.

        Returns exposure map where each amount is reproducible from position market values.
        """
        totals: dict[Currency, Decimal] = {}
        for position in positions:
            totals[position.currency] = totals.get(position.currency, Decimal("0")) + position.market_value.amount

        return {currency: Money(amount, currency) for currency, amount in totals.items()}

    @staticmethod
    def _weighted_sum(
        positions: Sequence[object],
        base_currency: Currency,
        metric_getter,
    ) -> tuple[Decimal, Decimal]:
        """Internal weighted sum helper used by analytics calculations."""
        weighted_sum = Decimal("0")
        total_weight = Decimal("0")

        for position in positions:
            if position.currency != base_currency:
                raise PortfolioError("Cannot compute weighted metrics across different currencies.")

            weight = position.market_value.amount
            total_weight += weight
            weighted_sum += metric_getter(position) * weight

        return weighted_sum, total_weight
