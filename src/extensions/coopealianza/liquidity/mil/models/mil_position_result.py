from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from src.extensions.coopealianza.liquidity.mil.enums.mil_eligibility_status import MilEligibilityStatus


@dataclass(frozen=True, slots=True)
class MilPositionResult:
    position_id: str
    instrument_id: str
    issuer: str
    issuer_category: str
    classification: str
    eligibility_status: MilEligibilityStatus
    blocking_factors: tuple[str, ...] = field(default_factory=tuple)
    warning_factors: tuple[str, ...] = field(default_factory=tuple)
    haircut: Decimal = Decimal("0")
    adjusted_value: Decimal = Decimal("0")
    market_value: Decimal = Decimal("0")
    configuration_version: str = ""
    policy_references: tuple[str, ...] = field(default_factory=tuple)
    market_data_reference: str | None = None
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    recommended_action: str | None = None
    evidence: tuple[dict[str, Any], ...] = field(default_factory=tuple)
