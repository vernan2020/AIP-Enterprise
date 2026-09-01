from __future__ import annotations

from aip.integration.economic.indicator_source_mapper import (
    IndicatorSourceMapper,
    IndicatorSourceMapping,
)

OFFICIAL_INDICATOR_MAPPINGS: tuple[IndicatorSourceMapping, ...] = (
    IndicatorSourceMapping(logical_code="FX_BUY", source="BCCR", source_series_code="317"),
    IndicatorSourceMapping(logical_code="FX_SELL", source="BCCR", source_series_code="318"),
    IndicatorSourceMapping(logical_code="TPM", source="BCCR", source_series_code="3541"),
    IndicatorSourceMapping(logical_code="TBP", source="BCCR", source_series_code="423"),
    IndicatorSourceMapping(logical_code="TRI_CRC_1W", source="BCCR", source_series_code="41203"),
    IndicatorSourceMapping(logical_code="TRI_CRC_1M", source="BCCR", source_series_code="41204"),
    IndicatorSourceMapping(logical_code="TRI_CRC_3M", source="BCCR", source_series_code="41205"),
    IndicatorSourceMapping(logical_code="TRI_CRC_6M", source="BCCR", source_series_code="41206"),
    IndicatorSourceMapping(logical_code="TRI_CRC_9M", source="BCCR", source_series_code="41207"),
    IndicatorSourceMapping(logical_code="TRI_CRC_12M", source="BCCR", source_series_code="41208"),
    IndicatorSourceMapping(logical_code="TRI_CRC_24M", source="BCCR", source_series_code="41209"),
    IndicatorSourceMapping(logical_code="TRI_CRC_36M", source="BCCR", source_series_code="41210"),
    IndicatorSourceMapping(logical_code="TRI_CRC_60M", source="BCCR", source_series_code="41211"),
    IndicatorSourceMapping(logical_code="TRI_USD_1W", source="BCCR", source_series_code="41213"),
    IndicatorSourceMapping(logical_code="TRI_USD_1M", source="BCCR", source_series_code="41214"),
    IndicatorSourceMapping(logical_code="TRI_USD_3M", source="BCCR", source_series_code="41215"),
    IndicatorSourceMapping(logical_code="TRI_USD_6M", source="BCCR", source_series_code="41216"),
    IndicatorSourceMapping(logical_code="TRI_USD_9M", source="BCCR", source_series_code="41217"),
    IndicatorSourceMapping(logical_code="TRI_USD_12M", source="BCCR", source_series_code="41218"),
    IndicatorSourceMapping(logical_code="TRI_USD_24M", source="BCCR", source_series_code="41219"),
    IndicatorSourceMapping(logical_code="TRI_USD_36M", source="BCCR", source_series_code="41220"),
    IndicatorSourceMapping(logical_code="TRI_USD_60M", source="BCCR", source_series_code="41221"),
    IndicatorSourceMapping(logical_code="INFLATION", source="BCCR", source_series_code="98407"),
    IndicatorSourceMapping(logical_code="IMAE", source="BCCR", source_series_code="95262"),
    IndicatorSourceMapping(logical_code="GDP", source="BCCR", source_series_code="97489"),
    IndicatorSourceMapping(logical_code="LABOR_FORCE", source="BCCR", source_series_code="22786"),
    IndicatorSourceMapping(logical_code="EMPLOYED", source="BCCR", source_series_code="22787"),
)


def build_official_indicator_mapper() -> IndicatorSourceMapper:
    return IndicatorSourceMapper(OFFICIAL_INDICATOR_MAPPINGS)
