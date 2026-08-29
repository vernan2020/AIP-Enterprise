from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field


class LiquidityPolicyThresholds(BaseModel):
    model_config = ConfigDict(frozen=True)
    hqla_minimum_score: Decimal = Field(default=Decimal("0.75"), ge=Decimal("0"), le=Decimal("1"))
    mil_minimum_ratio: Decimal = Field(default=Decimal("1.25"), ge=Decimal("0"))
    liquidity_limit_ratio: Decimal = Field(
        default=Decimal("0.80"), ge=Decimal("0"), le=Decimal("1")
    )
    issuer_limit_ratio: Decimal = Field(default=Decimal("0.15"), ge=Decimal("0"), le=Decimal("1"))
    concentration_ratio: Decimal = Field(default=Decimal("0.10"), ge=Decimal("0"), le=Decimal("1"))


class CoopealianzaLiquiditySettings(BaseModel):
    model_config = ConfigDict(frozen=True)
    institution_code: str = "COOPEALIANZA"
    environment: str = "development"
    thresholds: LiquidityPolicyThresholds = Field(default_factory=LiquidityPolicyThresholds)
    config_path: Path | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "CoopealianzaLiquiditySettings":
        thresholds_values = values.get("thresholds", {})
        if isinstance(thresholds_values, Mapping):
            thresholds_data = dict(thresholds_values)
        else:
            thresholds_data = {}
        thresholds = LiquidityPolicyThresholds(**thresholds_data)
        payload = dict(values)
        payload["thresholds"] = thresholds
        return cls(**payload)
