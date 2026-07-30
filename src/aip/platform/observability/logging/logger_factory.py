from __future__ import annotations

from aip.platform.observability.configuration.observability_config import ObservabilityConfig
from aip.platform.observability.logging.logger import Logger
from aip.platform.observability.providers.null_provider import NullProvider
from aip.platform.observability.providers.provider import LogProvider


class LoggerFactory:
    @staticmethod
    def create_logger(component: str, *, provider: LogProvider | None = None, config: ObservabilityConfig | None = None) -> Logger:
        effective = config or ObservabilityConfig()
        return Logger(provider=provider or NullProvider())
