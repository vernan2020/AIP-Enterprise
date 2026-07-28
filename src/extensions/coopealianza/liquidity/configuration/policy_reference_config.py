from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PolicyReferenceConfig:
    """Immutable configuration for policy references."""

    source: str
    identifier: str
    url: str | None = None
