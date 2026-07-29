from __future__ import annotations

from typing import Any

from aip.integration.normalization.normalizer import Normalizer


class FileNormalizer(Normalizer):
    """Generically normalizes file metadata without business semantics."""

    def normalize(self, payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            normalized: dict[str, Any] = {}
            for key, value in payload.items():
                normalized[str(key)] = value.strip() if isinstance(value, str) else value
            return normalized
        return {"value": payload}
