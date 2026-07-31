from __future__ import annotations

from typing import Any

from aip.product.configured.configuration.configured_source_config import ConfiguredSourceConfig
from aip.product.configured.protocols import SourceHealthProvider
from aip.product.demo.configuration.demo_config import DemoConfig


class ConfiguredMarketProvider:
    def __init__(self, config: DemoConfig, source_config: ConfiguredSourceConfig | None = None, health_provider: SourceHealthProvider | None = None) -> None:
        self._config = config
        self._source_config = source_config or ConfiguredSourceConfig()
        self._health_provider = health_provider

    def get_market(self) -> dict[str, Any]:
        bccr_enabled = self._source_config.bccr.enabled
        curves_enabled = self._source_config.curves.enabled
        source_status = self._health_provider.get_health() if self._health_provider is not None else {}
        return {
            "market_date": self._config.data_cutoff_date.isoformat(),
            "market_status": "Configured" if bccr_enabled or curves_enabled else "Unavailable",
            "curves": [],
            "pricing_results": [],
            "relative_value_opportunities": 0,
            "average_yield": 0.0,
            "average_duration": 0.0,
            "average_spread": 0.0,
            "source_status": source_status,
            "data_quality_status": "HEALTHY" if bccr_enabled else "DEGRADED",
            "configuration_message": "Market sources are disabled or unavailable" if not (bccr_enabled or curves_enabled) else "Configured market sources are active",
        }
