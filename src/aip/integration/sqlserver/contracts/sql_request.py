from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SQLRequest:
    """A parameterized SQL request for the connector."""

    query_name: str
    query_text: str
    parameters: dict[str, Any] = field(default_factory=dict)
    page_size: int = 1000
    page_number: int = 0
    stream: bool = False
    checkpoint: str | None = None
    timeout_seconds: int | None = None
    cancellation_token: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
