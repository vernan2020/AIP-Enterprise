from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.extensions.coopealianza.liquidity.mil.models.mil_asset import MilAsset


@dataclass(frozen=True, slots=True)
class MilRequest:
    """Immutable request for MIL eligibility evaluation."""

    portfolio_reference: str
    assets: tuple["MilAsset", ...] = field(default_factory=tuple)
    configuration: object | None = None
    policy_context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
