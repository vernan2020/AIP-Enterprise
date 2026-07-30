from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SecurityConfig:
    """Immutable configuration for the security platform."""

    session_ttl_seconds: int = 900
    issuer_name: str = "aip-enterprise"
    token_ttl_seconds: int = 300
    allowed_roles: tuple[str, ...] = field(default_factory=tuple)
    claims: dict[str, Any] = field(default_factory=dict)
