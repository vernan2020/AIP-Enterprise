from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LiquidityRow:
    section: str
    label: str
    value: str
    bucket: str = ""
    status: str = ""
    policy_reference: str = ""
    calculation_id: str | None = None
    correlation_id: str | None = None
