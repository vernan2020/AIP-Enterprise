from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IndicatorSourceMapping:
    logical_code: str
    source: str
    source_series_code: str


class IndicatorSourceMapper:
    """Maps logical economic indicator codes to physical source series."""

    def __init__(self, mappings: tuple[IndicatorSourceMapping, ...]) -> None:
        self._mappings = mappings

    def resolve(self, logical_code: str, source: str) -> IndicatorSourceMapping | None:
        normalized_code = logical_code.strip().upper()
        normalized_source = source.strip().upper()
        for mapping in self._mappings:
            if (
                mapping.logical_code.upper() == normalized_code
                and mapping.source.upper() == normalized_source
            ):
                return mapping
        return None

    def mappings_for_source(self, source: str) -> tuple[IndicatorSourceMapping, ...]:
        normalized_source = source.strip().upper()
        return tuple(
            mapping for mapping in self._mappings if mapping.source.upper() == normalized_source
        )
