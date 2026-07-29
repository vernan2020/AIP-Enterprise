from __future__ import annotations

from typing import Any


class Normalizer:
    """Reusable normalizer for connector payloads."""

    def normalize(self, payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            normalized: dict[str, Any] = {}
            for key, value in payload.items():
                normalized[str(key)] = value.strip() if isinstance(value, str) else value
            return normalized
        return {"value": payload}
