from __future__ import annotations

from typing import Any

from aip.product.configured.configuration.configured_source_config import ConfiguredSourceConfig
from aip.product.configured.protocols import SourceHealthProvider
from aip.product.demo.configuration.demo_config import DemoConfig
from aip.product.demo.data.demo_liquidity_data import DemoLiquidityData


class ConfiguredLiquidityProvider:
    def __init__(self, config: DemoConfig, source_config: ConfiguredSourceConfig | None = None, health_provider: SourceHealthProvider | None = None) -> None:
        self._config = config
        self._source_config = source_config or ConfiguredSourceConfig()
        self._health_provider = health_provider

    def get_liquidity(self) -> dict[str, Any]:
        payload = DemoLiquidityData.build()
        payload["liquidity_gap"] = 0.0
        payload["source_status"] = self._health_provider.get_health() if self._health_provider is not None else {}
        payload["data_quality_status"] = "HEALTHY" if self._source_config.folder_watch.enabled else "DEGRADED"
        return payload
