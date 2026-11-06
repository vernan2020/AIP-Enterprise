"""Shared request and export contracts without web-server initialization."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ticotrader_web.forecast_policy import FORECAST_INDICATORS


def clean(value):
    if is_dataclass(value):
        return clean(asdict(value))
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value) if value.is_finite() else None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def safe_cell(value):
    value = (
        json.dumps(clean(value), ensure_ascii=False)
        if isinstance(value, (dict, list))
        else str(value if value is not None else "")
    )
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


class Query(BaseModel):
    kind: Literal["financial", "compare", "macro", "projection", "forecast"]
    entity_id: str | None = Field(default=None, max_length=80)
    cutoff: date | None = None
    refresh: bool = False
    entity_ids: list[str] = Field(default_factory=list, max_length=5)
    series_code: str = Field(default="ASSETS", max_length=160)
    horizon: Literal["12M", "24M", "36M", "5Y", "ALL", "CUSTOM"] = "36M"
    custom_from: date | None = None
    custom_to: date | None = None
    indicator: str = "TBP"

    @model_validator(mode="after")
    def validate_query(self):
        if self.indicator not in FORECAST_INDICATORS:
            raise ValueError("Indicador no admitido")
        if self.kind == "compare":
            if not self.entity_ids:
                raise ValueError("Seleccione de una a cinco entidades")
            if self.horizon == "CUSTOM" and (not self.custom_from or not self.custom_to):
                raise ValueError("Seleccione ambas fechas")
            if self.custom_from and self.custom_to and self.custom_from > self.custom_to:
                raise ValueError("Desde no puede ser posterior a Hasta")
        return self
