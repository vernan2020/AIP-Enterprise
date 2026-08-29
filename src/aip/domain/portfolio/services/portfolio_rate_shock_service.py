from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class RateShockResult:
    """Resultado de sensibilidad de una posición ante un shock paralelo."""

    shock_bp: int
    delta_eve_crc: Decimal | None
    shocked_market_value_crc: Decimal | None
    base_market_value_crc: Decimal
    modified_duration: Decimal | None
    status: str
    method: str
    source: str
    diagnostic: str | None = None


class PortfolioRateShockService:
    """Sensibilidad institucional mediante aproximación por duración modificada."""

    SUPPORTED_SHOCKS_BP = (-200, -100, 100, 200)

    _NO_DURATION_PRODUCTS = {
        "fiprc",
        "finpo",
        "ilm1$",
        "inm1$",
        "inm2$",
        "inm3",
        "insm$",
    }

    @classmethod
    def calculate(cls, position: dict[str, Any], shock_bp: int) -> RateShockResult:
        if shock_bp not in cls.SUPPORTED_SHOCKS_BP:
            raise ValueError(f"Unsupported rate shock: {shock_bp} bp")

        market_value = cls._decimal(position.get("market_value_crc"))
        duration = cls._decimal(position.get("modified_duration"))
        product_code = cls._text(position.get("product_code"))

        if market_value is None or market_value <= 0:
            return RateShockResult(
                shock_bp=shock_bp,
                delta_eve_crc=None,
                shocked_market_value_crc=None,
                base_market_value_crc=market_value or Decimal("0"),
                modified_duration=duration,
                status="DATA_UNAVAILABLE",
                method="UNAVAILABLE",
                source="MARKET_VALUE_CRC",
                diagnostic="Market value CRC is zero or unavailable",
            )

        if product_code in cls._NO_DURATION_PRODUCTS:
            return RateShockResult(
                shock_bp=shock_bp,
                delta_eve_crc=None,
                shocked_market_value_crc=None,
                base_market_value_crc=market_value,
                modified_duration=None,
                status="POLICY_EXCLUDED",
                method="NOT_APPLICABLE",
                source="INSTITUTIONAL_RATE_RISK_POLICY",
                diagnostic=(
                    "Instrument excluded because no duration is applicable "
                    "under institutional methodology"
                ),
            )

        if duration is None or duration < 0:
            return RateShockResult(
                shock_bp=shock_bp,
                delta_eve_crc=None,
                shocked_market_value_crc=None,
                base_market_value_crc=market_value,
                modified_duration=duration,
                status="DATA_UNAVAILABLE",
                method="UNAVAILABLE",
                source="PORTFOLIO_DURATION_SERVICE",
                diagnostic="Modified duration is expected but unavailable",
            )

        shock_decimal = Decimal(shock_bp) / Decimal("10000")
        delta_eve = -market_value * duration * shock_decimal
        shocked_market_value = market_value + delta_eve

        return RateShockResult(
            shock_bp=shock_bp,
            delta_eve_crc=delta_eve,
            shocked_market_value_crc=shocked_market_value,
            base_market_value_crc=market_value,
            modified_duration=duration,
            status="CALCULATED",
            method="MODIFIED_DURATION_APPROXIMATION",
            source="PORTFOLIO_DURATION_SERVICE",
        )

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value in (None, "") or isinstance(value, bool):
            return None
        try:
            return Decimal(str(value))
        except (ArithmeticError, ValueError, TypeError):
            return None

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip().casefold()
