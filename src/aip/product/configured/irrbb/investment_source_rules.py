from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aip.domain.irrbb.models import RateType


@dataclass(frozen=True, slots=True)
class InvestmentMasterSourceRules:
    """Strict adapter-owned derivations permitted during source certification.

    These rules operate on normalized institutional master values. They never
    default missing values and return ``None`` when a source value cannot be
    classified deterministically.
    """

    POSITION_ID_RULE_REFERENCE = "RULE:INVESTMENT-POSITION-ID:2026.09.10"
    RATE_TYPE_RULE_REFERENCE = "RULE:INVESTMENT-RATE-TYPE:2026.09.10"
    PAYMENT_FREQUENCY_RULE_REFERENCE = "RULE:INVESTMENT-PAYMENT-FREQUENCY:2026.09.10"
    CASHFLOW_RULE_REFERENCE = "aip.domain.portfolio.services.PortfolioContractualCashFlowService"

    _FLOATING_FLAGS = frozenset({"s", "si", "sí", "yes", "y", "true", "1"})
    _FIXED_FLAGS = frozenset({"n", "no", "false", "0"})
    _PERIOD_MONTHS = {
        "1": 12,
        "1.0": 12,
        "2": 6,
        "2.0": 6,
        "3": 4,
        "3.0": 4,
        "4": 3,
        "4.0": 3,
        "6": 2,
        "6.0": 2,
        "12": 1,
        "12.0": 1,
        "mensual": 1,
        "monthly": 1,
        "bimestral": 2,
        "cada 2 meses": 2,
        "trimestral": 3,
        "quarterly": 3,
        "cada 3 meses": 3,
        "cuatrimestral": 4,
        "cada 4 meses": 4,
        "semestral": 6,
        "semiannual": 6,
        "cada 6 meses": 6,
        "anual": 12,
        "annual": 12,
        "cada 12 meses": 12,
    }

    @classmethod
    def stable_position_id(
        cls,
        *,
        contract_number: Any,
        isin: Any,
        series: Any,
    ) -> str | None:
        """Build a stable investment ID without using mutable row position."""

        contract = cls._text(contract_number)
        normalized_isin = cls._text(isin)
        normalized_series = cls._text(series)
        if contract and normalized_isin:
            return f"contract:{contract}|isin:{normalized_isin}"
        if contract and normalized_series:
            return f"contract:{contract}|series:{normalized_series}"
        return None

    @classmethod
    def rate_type(cls, value: Any) -> RateType | None:
        """Map only explicit institutional variable-rate flags."""

        normalized = cls._text(value).casefold()
        if normalized in cls._FLOATING_FLAGS:
            return RateType.FLOATING
        if normalized in cls._FIXED_FLAGS:
            return RateType.FIXED
        return None

    @classmethod
    def payment_frequency_months(cls, value: Any) -> int | None:
        """Map an explicit supported coupon periodicity to months."""

        return cls._PERIOD_MONTHS.get(cls._text(value).casefold())

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip()
