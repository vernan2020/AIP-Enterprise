from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PolicyReference:
    """Immutable reference to an external policy or control artifact."""

    source: str
    identifier: str
    url: str | None = None
