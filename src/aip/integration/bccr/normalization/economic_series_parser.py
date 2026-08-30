from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from aip.domain.economic.economic_indicator_observation import EconomicIndicatorObservation
from aip.integration.economic.indicator_source_mapper import (
    IndicatorSourceMapper,
    IndicatorSourceMapping,
)


class BCCREconomicSeriesParser:
    """Normalize SDDE BCCR JSON payloads into AIP economic observations."""

    def __init__(self, mapper: IndicatorSourceMapper) -> None:
        self._mapper = mapper

    def parse(self, payload: dict[str, Any]) -> tuple[EconomicIndicatorObservation, ...]:
        if not isinstance(payload, dict):
            raise ValueError("BCCR payload must be a mapping")
        if payload.get("estado") is not True:
            raise ValueError(str(payload.get("mensaje", "BCCR response is not successful")))

        raw_data = payload.get("datos")
        if not isinstance(raw_data, list):
            raise ValueError("BCCR payload does not contain datos list")

        observations: list[EconomicIndicatorObservation] = []
        for indicator_payload in raw_data:
            if not isinstance(indicator_payload, dict):
                continue
            source_code = str(indicator_payload.get("codigoIndicador", "")).strip()
            if not source_code:
                continue
            logical_mapping = self._resolve_mapping(source_code)
            if logical_mapping is None:
                continue
            raw_series = indicator_payload.get("series", [])
            if not isinstance(raw_series, list):
                continue
            for raw_observation in raw_series:
                observation = self._parse_observation(
                    logical_code=logical_mapping.logical_code,
                    source_code=source_code,
                    raw_observation=raw_observation,
                )
                if observation is not None:
                    observations.append(observation)

        observations.sort(key=lambda item: (item.indicator_code, item.observation_date))
        return tuple(observations)

    def _resolve_mapping(self, source_code: str) -> IndicatorSourceMapping | None:
        normalized = str(source_code).strip()
        for mapping in self._mapper.mappings_for_source("BCCR"):
            if mapping.source_series_code == normalized:
                return mapping
        return None

    @staticmethod
    def _parse_observation(
        *,
        logical_code: str,
        source_code: str,
        raw_observation: object,
    ) -> EconomicIndicatorObservation | None:
        if not isinstance(raw_observation, dict):
            return None
        raw_date = raw_observation.get("fecha")
        raw_value = raw_observation.get("valorDatoPorPeriodo")
        if raw_date in (None, "") or raw_value in (None, ""):
            return None
        try:
            observation_date = date.fromisoformat(str(raw_date)[:10])
            value = Decimal(str(raw_value))
        except (ValueError, InvalidOperation):
            return None

        return EconomicIndicatorObservation(
            indicator_code=logical_code,
            observation_date=observation_date,
            value=value,
            source="BCCR",
            unit=("CRC/USD" if logical_code in {"FX", "FX_BUY", "FX_SELL"} else "%"),
            source_series_code=source_code,
            quality_status="VALID",
            is_preliminary=False,
        )
