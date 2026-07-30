from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SourceConfig:
    """External source settings for the demo runtime."""

    sql_server_enabled: bool = False
    folder_watch_enabled: bool = False
    bccr_enabled: bool = False
    sql_server_connection: str | None = None
    folder_watch_path: str | None = None
    bccr_endpoint: str | None = None
    options: dict[str, Any] = field(default_factory=dict)
