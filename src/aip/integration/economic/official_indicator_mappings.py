from __future__ import annotations

from aip.integration.economic.indicator_source_mapper import IndicatorSourceMapper, IndicatorSourceMapping

OFFICIAL_INDICATOR_MAPPINGS: tuple[IndicatorSourceMapping, ...] = ()


def build_official_indicator_mapper() -> IndicatorSourceMapper:
    return IndicatorSourceMapper(OFFICIAL_INDICATOR_MAPPINGS)
