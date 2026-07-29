from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class BCCRConfig:
    """Configuration for the BCCR public indicator connector."""

    base_url: str = "https://api.bccr.fi.cr"
    indicators: list[str] = field(default_factory=list)
    timeout_seconds: float = 10.0
    cache_ttl_seconds: int = 300
    retry_attempts: int = 2
    user_agent: str = "aip-enterprise/1.0"

    def __post_init__(self) -> None:
        if not self.base_url:
            raise ValueError("base_url is required")
        if not self.indicators:
            raise ValueError("indicators is required")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if self.cache_ttl_seconds < 0:
            raise ValueError("cache_ttl_seconds cannot be negative")

    def __repr__(self) -> str:
        return f"BCCRConfig(base_url={self.base_url!r}, indicators={self.indicators!r}, timeout_seconds={self.timeout_seconds!r})"
