from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class BCCRConfig:
    """Runtime configuration for the BCCR integration.

    Credentials are runtime-only values. They are intentionally excluded from
    ``repr`` so diagnostic output cannot disclose them.
    """

    base_url: str = "https://apim.bccr.fi.cr"
    indicators: list[str] = field(default_factory=list)
    timeout_seconds: float = 10.0
    cache_ttl_seconds: int = 300
    retry_attempts: int = 2
    user_agent: str = "aip-enterprise/1.0"
    name: str | None = None
    email: str | None = None
    token: str | None = None

    def __post_init__(self) -> None:
        if not self.base_url or not self.base_url.strip():
            raise ValueError("base_url is required")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if self.cache_ttl_seconds < 0:
            raise ValueError("cache_ttl_seconds cannot be negative")
        if self.retry_attempts < 0:
            raise ValueError("retry_attempts cannot be negative")

    def __repr__(self) -> str:
        return (
            "BCCRConfig("
            f"base_url={self.base_url!r}, "
            f"indicators={self.indicators!r}, "
            f"timeout_seconds={self.timeout_seconds!r}, "
            f"cache_ttl_seconds={self.cache_ttl_seconds!r}, "
            f"retry_attempts={self.retry_attempts!r}"
            ")"
        )
