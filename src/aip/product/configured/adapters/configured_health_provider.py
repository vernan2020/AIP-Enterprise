from __future__ import annotations

from typing import Any

from aip.product.configured.configuration.configured_source_config import ConfiguredSourceConfig


class ConfiguredHealthProvider:
    def __init__(self, source_config: ConfiguredSourceConfig | None = None) -> None:
        self._source_config = source_config or ConfiguredSourceConfig()

    def get_health(self) -> dict[str, Any]:
        return {
            "sql_server": "HEALTHY" if self._source_config.sql_server.enabled else "DEGRADED",
            "folder_watch": "HEALTHY" if self._source_config.folder_watch.enabled else "DEGRADED",
            "bccr": "HEALTHY" if self._source_config.bccr.enabled else "DEGRADED",
            "integration_hub": "HEALTHY",
            "data_quality": "HEALTHY",
            "scheduler": "HEALTHY",
            "notifications": "HEALTHY",
            "observability": "HEALTHY",
            "security": "HEALTHY",
        }
