"""Portfolio calculation domain service."""

import re
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
    def weighted_average_effective_yield(
        positions: Sequence[object], base_currency: Currency | None = None
    ) -> Decimal:
        """Calculate portfolio weighted yield using the validated effective-rate rule."""
        weighted_sum = Decimal("0")
        total_weight = Decimal("0")

        for position in positions:
            if PortfolioCalculationService._is_closed_position(position):
                continue

            currency = PortfolioCalculationService._resolve_currency(position)
            if base_currency is not None and currency is not None and currency != base_currency:
                continue

            weight = PortfolioCalculationService._resolve_weight(position)
            effective_rate = PortfolioCalculationService._resolve_effective_rate(position)
            if weight is None or effective_rate is None or effective_rate <= Decimal("0"):
                continue

            weighted_sum += effective_rate * weight
            total_weight += weight

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
            totals[position.currency] = (
                totals.get(position.currency, Decimal("0")) + position.market_value.amount
            )

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

    @staticmethod
    def _resolve_currency(position: object) -> Currency | None:
        if isinstance(position, dict):
            raw_currency = position.get("currency")
        else:
            raw_currency = getattr(position, "currency", None)

        if isinstance(raw_currency, Currency):
            return raw_currency
        if isinstance(raw_currency, str) and raw_currency:
            normalized_currency = PortfolioCalculationService._normalize_institutional_currency(
                raw_currency
            )
            if normalized_currency is None:
                return None
            if isinstance(normalized_currency, Currency):
                return normalized_currency
            try:
                return Currency[normalized_currency.upper()]
            except KeyError:
                try:
                    return Currency.from_code(normalized_currency)
                except ValueError:
                    return None
        return None

    @staticmethod
    def _normalize_institutional_currency(value: object) -> str | Currency | None:
        if value is None:
            return None
        if isinstance(value, Currency):
            return value
        text = str(value).strip()
        if not text:
            return None

        normalized_text = re.sub(r"\s+", " ", text).strip().casefold()
        normalized_text = (
            normalized_text.replace("ó", "o")
            .replace("ú", "u")
            .replace("á", "a")
            .replace("é", "e")
            .replace("í", "i")
        )
        normalized_text = normalized_text.replace("$", "").strip()
        normalized_text = re.sub(r"[^a-z]+", "", normalized_text)
        normalized_text = normalized_text.replace("costarricense", "").replace("costarricenses", "")

        if normalized_text in {"crc", "usd"}:
            return normalized_text.upper()
        if normalized_text in {"us", "usd", "dolar", "dolares"}:
            return "USD"
        if normalized_text in {
            "crc",
            "colon",
            "colones",
            "coloncostarricense",
            "colonescostarricenses",
        }:
            return "CRC"
        try:
            return Currency.from_code(text).value
        except Exception:
            return None

    @staticmethod
    def _resolve_weight(position: object) -> Decimal | None:
        if isinstance(position, dict):
            raw_weight = position.get("market_value_crc")
            if raw_weight in (None, ""):
                raw_weight = position.get("market_value")
            if raw_weight in (None, ""):
                raw_weight = position.get("market_value_local")
        else:
            raw_weight = getattr(position, "market_value_crc", None)
            if raw_weight in (None, ""):
                raw_weight = getattr(position, "market_value", None)
            if raw_weight in (None, ""):
                raw_weight = getattr(position, "market_value_local", None)

        if raw_weight is None:
            return None
        return PortfolioCalculationService._coerce_decimal(raw_weight)

    @staticmethod
    def _resolve_effective_rate(position: object) -> Decimal | None:
        master_tir = PortfolioCalculationService._resolve_position_value(
            position, "master_tir", "portfolio_yield", "yield_value", "tir"
        )
        facial_rate = PortfolioCalculationService._resolve_position_value(
            position, "facial_rate", "nominal_rate", "rate", "tasa nominal"
        )

        master_tir_value = PortfolioCalculationService._coerce_decimal(master_tir)
        facial_rate_value = PortfolioCalculationService._coerce_decimal(facial_rate)

        if (
            master_tir_value is not None
            and master_tir_value > Decimal("0")
            and master_tir_value.is_finite()
        ):
            return master_tir_value
        if (
            facial_rate_value is not None
            and facial_rate_value > Decimal("0")
            and facial_rate_value.is_finite()
        ):
            return facial_rate_value
        return None

    @staticmethod
    def _resolve_position_value(position: object, *keys: str) -> object | None:
        if isinstance(position, dict):
            for key in keys:
                if key in position and position.get(key) not in (None, ""):
                    return position.get(key)

            source_values = position.get("source_values") or {}
            if isinstance(source_values, dict):
                normalized_source_values = {
                    PortfolioCalculationService._normalize_lookup_key(key): value
                    for key, value in source_values.items()
                }
                for key in keys:
                    normalized_key = PortfolioCalculationService._normalize_lookup_key(key)
                    if normalized_key in normalized_source_values and normalized_source_values[
                        normalized_key
                    ] not in (None, ""):
                        return normalized_source_values[normalized_key]
            return None

        for key in keys:
            value = getattr(position, key, None)
            if value not in (None, ""):
                return value
        return None

    @staticmethod
    def _normalize_lookup_key(value: str) -> str:
        return re.sub(r"\s+", "", str(value)).casefold()

    @staticmethod
    def _coerce_decimal(value: object) -> Decimal | None:
        if value is None or value == "":
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, bool):
            return None
        try:
            decimal_value = Decimal(str(value))
        except (ArithmeticError, ValueError, TypeError):
            return None
        return decimal_value

    @staticmethod
    def _is_closed_position(position: object) -> bool:
        if isinstance(position, dict):
            classification = position.get("classification")
        else:
            classification = getattr(position, "classification", None)

        if classification is None:
            return False
        normalized = str(classification).strip().casefold()
        return "cerrado" in normalized or "closed" in normalized or "closed_position" in normalized
