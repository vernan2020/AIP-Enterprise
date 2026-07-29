from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ValidationPipeline(ABC):
    """Contract for reusable validation pipelines."""

    @abstractmethod
    def validate(self, payload: Any) -> list[dict[str, Any]]:
        """Validate the supplied payload."""
