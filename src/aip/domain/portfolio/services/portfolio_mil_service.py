from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class MILResult:
    eligible: bool
    factor: Decimal
    mil_value_crc: Decimal
    status: str
    source: str
    diagnostic: str | None = None


class PortfolioMILService:
    """Institutional MIL collateral eligibility rules."""

    HAIRCUT = Decimal("0.90")
    GOVERNMENT_ISSUER = "g"
    BCCR_ISSUER = "bccr"

    @classmethod
    def calculate(cls, position: dict[str, Any]) -> MILResult:
        classification = cls._text(position.get("classification"))
        issuer = cls._text(position.get("issuer"))
        product = cls._text(position.get("product_code"))
        market_value_crc = cls._decimal(position.get("market_value_crc")) or Decimal("0")

        if market_value_crc <= 0:
            return MILResult(
                eligible=False,
                factor=Decimal("0"),
                mil_value_crc=Decimal("0"),
                status="NOT_ELIGIBLE",
                source="MARKET_VALUE",
                diagnostic="Market value is zero or unavailable",
            )

        if cls._is_restricted(classification):
            return MILResult(
                eligible=False,
                factor=Decimal("0"),
                mil_value_crc=Decimal("0"),
                status="RESTRICTED",
                source="CLASSIFICATION",
                diagnostic="Position is restricted or already committed",
            )

        if issuer == cls.GOVERNMENT_ISSUER and classification.startswith("d.v gobierno"):
            mil_value = market_value_crc * cls.HAIRCUT
            return MILResult(
                eligible=True,
                factor=cls.HAIRCUT,
                mil_value_crc=mil_value,
                status="MIL_ELIGIBLE",
                source="GOVERNMENT_COLLATERAL",
            )

        if issuer == cls.BCCR_ISSUER:
            if cls._is_icp(product=product, classification=classification):
                return MILResult(
                    eligible=False,
                    factor=Decimal("0"),
                    mil_value_crc=Decimal("0"),
                    status="NOT_ELIGIBLE",
                    source="BCCR_ICP",
                    diagnostic="ICP is not eligible as MIL collateral",
                )

            if cls._is_eligible_bccr(classification):
                mil_value = market_value_crc * cls.HAIRCUT
                return MILResult(
                    eligible=True,
                    factor=cls.HAIRCUT,
                    mil_value_crc=mil_value,
                    status="MIL_ELIGIBLE",
                    source="BCCR_COLLATERAL",
                )

        return MILResult(
            eligible=False,
            factor=Decimal("0"),
            mil_value_crc=Decimal("0"),
            status="NOT_ELIGIBLE",
            source="INSTITUTIONAL_CLASSIFICATION",
        )

    @classmethod
    def _is_restricted(cls, classification: str) -> bool:
        normalized = cls._normalize_text(classification)
        restricted_tokens = (
            "vc-garant",
            "vc garant",
            "garantias",
            "garantia",
            "d.v-rl",
            "d.v rl",
            " r.l",
            "r.l ",
            "reserva de liquidez",
        )
        return any(token in normalized for token in restricted_tokens)

    @classmethod
    def _is_eligible_bccr(cls, classification: str) -> bool:
        """Return whether an available BCCR security is eligible for MIL."""
        return cls._normalize_text(classification).startswith("v.r bccr")

    @classmethod
    def _is_icp(cls, *, product: str, classification: str) -> bool:
        normalized_product = cls._normalize_text(product)
        normalized_classification = cls._normalize_text(classification)
        return "icp" in normalized_product or "icp" in normalized_classification

    @staticmethod
    def _normalize_text(value: Any) -> str:
        normalized = str(value or "").strip().casefold()
        replacements = {
            "\u251c\u00a1": "i",
            "\u251c\u00ed": "a",
            "\u251c\u00ae": "e",
            "\u251c\u2502": "o",
            "\u251c\u2551": "u",
            "\u251c\u2592": "n",
            "á": "a",
            "é": "e",
            "í": "i",
            "ó": "o",
            "ú": "u",
            "ñ": "n",
        }
        for source, target in replacements.items():
            normalized = normalized.replace(source, target)
        return normalized

    @classmethod
    def _text(cls, value: Any) -> str:
        return cls._normalize_text(value)

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value in (None, "") or isinstance(value, bool):
            return None
        try:
            return Decimal(str(value))
        except (ArithmeticError, ValueError, TypeError):
            return None
