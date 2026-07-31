from __future__ import annotations

from typing import Any

from aip.product.configured.configuration.configured_source_config import ConfiguredSourceConfig
from aip.product.configured.protocols import SourceHealthProvider
from aip.product.demo.configuration.demo_config import DemoConfig


class ConfiguredLiquidityProvider:
    def __init__(self, config: DemoConfig, source_config: ConfiguredSourceConfig | None = None, health_provider: SourceHealthProvider | None = None) -> None:
        self._config = config
        self._source_config = source_config or ConfiguredSourceConfig()
        self._health_provider = health_provider

    def get_liquidity(self) -> dict[str, Any]:
        folder_enabled = self._source_config.folder_watch.enabled
        sql_enabled = self._source_config.sql_server.enabled
        source_status = self._health_provider.get_health() if self._health_provider is not None else {}
        return {
            "liquidity_date": self._config.data_cutoff_date.isoformat(),
            "cash_position": 0.0,
            "net_cash_flow": 0.0,
            "liquidity_gap": 0.0,
            "hqla_capacity": 0.0,
            "mil_eligible_capacity": 0.0,
            "stress_result": "Unavailable",
            "policy_status": "Unavailable",
            "cashflows": [],
            "gaps": [],
            "hqla_rows": [],
            "mil_rows": [],
            "stress_rows": [],
            "source_status": source_status,
            "data_quality_status": "HEALTHY" if sql_enabled or folder_enabled else "DEGRADED",
            "configuration_message": "Liquidity sources are disabled or unavailable" if not (sql_enabled or folder_enabled) else "Configured liquidity sources are active",
        }
