from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class HTTPProvider(ABC):
    """Transport abstraction for HTTP requests."""

    @abstractmethod
    def get(
        self, url: str, *, timeout: float, headers: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Perform a GET request and return a JSON-like dictionary."""
