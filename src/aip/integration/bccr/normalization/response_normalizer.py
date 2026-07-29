from __future__ import annotations

from typing import Any


class ResponseNormalizer:
    """Normalizes BCCR payloads into a generic shape."""

    def normalize(self, payload: object) -> dict[str, Any]:
        if isinstance(payload, dict):
            normalized: dict[str, Any] = {}
            if "indicatorCode" in payload:
                normalized["indicator_code"] = payload["indicatorCode"]
            if "indicator_code" in payload:
                normalized["indicator_code"] = payload["indicator_code"]
            if "value" in payload:
                normalized["value"] = payload["value"]
            if "indicator_codes" in payload:
                normalized["indicator_codes"] = payload["indicator_codes"]
            if "from_date" in payload:
                normalized["from_date"] = payload["from_date"]
            if "to_date" in payload:
                normalized["to_date"] = payload["to_date"]
            if "format" in payload:
                normalized["format"] = payload["format"]
            if "status_code" in payload:
                normalized["status_code"] = payload["status_code"]
            if "content_type" in payload:
                normalized["content_type"] = payload["content_type"]
            if "body" in payload and isinstance(payload["body"], dict):
                normalized["body"] = self.normalize(payload["body"])
            if "indicators" in payload and isinstance(payload["indicators"], list):
                normalized["indicators"] = [self.normalize(item) for item in payload["indicators"]]
            if not normalized:
                return {"value": payload}
            return normalized
        return {"value": payload}
