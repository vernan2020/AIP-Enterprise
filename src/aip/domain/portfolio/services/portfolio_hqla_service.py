from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class HQLAResult:
    eligible: bool
    factor: Decimal
    hqla_value_crc: Decimal
    status: str
    source: str
    diagnostic: str | None = None


class PortfolioHQLAService:
    """Institutional HQLA classification and haircut rules."""

    GOVERNMENT_ISSUER = "g"
    BCCR_ISSUER = "bccr"

    @classmethod
    def calculate(cls, position: dict[str, Any]) -> HQLAResult:
        classification = cls._text(position.get("classification"))
        issuer = cls._text(position.get("issuer"))
        product = cls._text(position.get("product_code"))
        market_value_crc = cls._decimal(position.get("market_value_crc")) or Decimal("0")

        if market_value_crc <= 0:
            return HQLAResult(
                False,
                Decimal("0"),
                Decimal("0"),
                "NOT_ELIGIBLE",
                "MARKET_VALUE",
                "Market value is zero or unavailable",
            )

        if cls._is_restricted(classification):
            return HQLAResult(
                False,
                Decimal("0"),
                Decimal("0"),
                "RESTRICTED",
                "CLASSIFICATION",
            )

        if issuer == cls.BCCR_ISSUER and product == "icp":
            return HQLAResult(True, Decimal("1"), market_value_crc, "HQLA_100", "BCCR_ICP")

        if issuer == cls.GOVERNMENT_ISSUER and classification.startswith("d.v gobierno"):
            value = market_value_crc * Decimal("0.90")
            return HQLAResult(True, Decimal("0.90"), value, "HQLA_90", "GOVERNMENT")

        if issuer == cls.BCCR_ISSUER and classification.startswith("v.r bccr"):
            value = market_value_crc * Decimal("0.90")
            return HQLAResult(True, Decimal("0.90"), value, "HQLA_90", "BCCR")

        return HQLAResult(
            False,
            Decimal("0"),
            Decimal("0"),
            "NOT_ELIGIBLE",
            "INSTITUTIONAL_CLASSIFICATION",
        )

    @staticmethod
    def _is_restricted(classification: str) -> bool:
        normalized = (
            classification.replace("í", "i")
            .replace("á", "a")
            .replace("é", "e")
            .replace("ó", "o")
            .replace("ú", "u")
        )
        return any(
            token in normalized
            for token in (
                "vc-garant",
                "vc garant",
                "garantias",
                "d.v-rl",
                " r.l",
                "r.l ",
                "reserva de liquidez",
            )
        )

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip().casefold()

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value in (None, "") or isinstance(value, bool):
            return None
        try:
            return Decimal(str(value))
        except (ArithmeticError, ValueError, TypeError):
            return None
