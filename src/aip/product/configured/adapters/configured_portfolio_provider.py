from __future__ import annotations

from typing import Any

from aip.product.configured.configuration.configured_source_config import ConfiguredSourceConfig
from aip.product.configured.protocols import SourceHealthProvider
from aip.product.demo.configuration.demo_config import DemoConfig


class ConfiguredPortfolioProvider:
    def __init__(self, config: DemoConfig, source_config: ConfiguredSourceConfig | None = None, health_provider: SourceHealthProvider | None = None) -> None:
        self._config = config
        self._source_config = source_config or ConfiguredSourceConfig()
        self._health_provider = health_provider

    def get_portfolio(self) -> dict[str, Any]:
        sql_enabled = self._source_config.sql_server.enabled
        folder_enabled = self._source_config.folder_watch.enabled
        source_status = self._health_provider.get_health() if self._health_provider is not None else {}
        return {
            "portfolio_name": f"{self._config.environment_name.title()} Configured Portfolio",
            "valuation_date": self._config.data_cutoff_date.isoformat(),
            "market_value": 0.0 if not sql_enabled else 0.0,
            "book_value": 0.0 if not sql_enabled else 0.0,
            "weighted_yield": 0.0,
            "modified_duration": 0.0,
            "hqla_percent": 0.0,
            "mil_eligible_percent": 0.0,
            "currency_distribution": (),
            "relative_value_opportunity": "Unavailable",
            "positions": [],
            "source_status": source_status,
            "data_quality_status": "HEALTHY" if sql_enabled else "DEGRADED",
            "configuration_message": "Portfolio sources are disabled or unavailable" if not (sql_enabled or folder_enabled) else "Configured sources are active",
        }
