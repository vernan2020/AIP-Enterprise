from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class DV01Result:
    dv01_crc: Decimal | None
    market_value_crc: Decimal
    modified_duration: Decimal | None
    status: str
    method: str
    source: str
    exclusion_reason: str | None = None
    diagnostic: str | None = None


class PortfolioDV01Service:
    """Institutional DV01 calculation for configured portfolio positions."""

    _ONE_BASIS_POINT = Decimal("0.0001")

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
    def calculate(cls, position: dict[str, Any]) -> DV01Result:
        market_value = cls._decimal(position.get("market_value_crc"))
        duration = cls._decimal(position.get("modified_duration"))
        product_code = cls._text(position.get("product_code"))

        if market_value is None or market_value <= 0:
            return DV01Result(
                dv01_crc=None,
                market_value_crc=market_value or Decimal("0"),
                modified_duration=duration,
                status="DATA_UNAVAILABLE",
                method="UNAVAILABLE",
                source="MARKET_VALUE_CRC",
                diagnostic="Market value CRC is zero or unavailable",
            )

        if product_code in cls._NO_DURATION_PRODUCTS:
            return DV01Result(
                dv01_crc=None,
                market_value_crc=market_value,
                modified_duration=None,
                status="POLICY_EXCLUDED",
                method="NOT_APPLICABLE",
                source="INSTITUTIONAL_DV01_POLICY",
                exclusion_reason="INSTRUMENT_WITHOUT_DURATION",
                diagnostic=(
                    "Instrument excluded from DV01 because no duration "
                    "is applicable under institutional methodology"
                ),
            )

        if duration is None or duration < 0:
            return DV01Result(
                dv01_crc=None,
                market_value_crc=market_value,
                modified_duration=duration,
                status="DATA_UNAVAILABLE",
                method="UNAVAILABLE",
                source="PORTFOLIO_DURATION_SERVICE",
                diagnostic="Modified duration is expected but unavailable",
            )

        dv01_value = market_value * duration * cls._ONE_BASIS_POINT

        return DV01Result(
            dv01_crc=dv01_value,
            market_value_crc=market_value,
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
