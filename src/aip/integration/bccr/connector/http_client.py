from __future__ import annotations

from typing import Any

from aip.integration.bccr.contracts.request import BCCRRequest
from aip.integration.bccr.providers.http_provider import HTTPProvider


class HTTPClient:
    """Thin HTTP client wrapper for BCCR requests."""

    def __init__(self, *, provider: HTTPProvider, timeout_seconds: float = 10.0) -> None:
        self.provider = provider
        self.timeout_seconds = timeout_seconds

    def fetch(self, request: BCCRRequest) -> dict[str, Any]:
        indicator = request.indicator_codes[0] if request.indicator_codes else ""
        url = f"https://api.bccr.fi.cr/indicators/{indicator}" if indicator else "https://api.bccr.fi.cr/indicators"
        headers = {"Accept": "application/json"}
        if request.etag:
            headers["If-None-Match"] = request.etag
        if request.last_modified:
            headers["If-Modified-Since"] = request.last_modified

        response = self.provider.get(url, timeout=self.timeout_seconds, headers=headers)
        if not isinstance(response, dict):
            raise ValueError("response must be a mapping")

        status_code = response.get("status_code", 200)
        content_type = response.get("content_type", "application/json")
        if status_code == 304:
            return {}
        if status_code < 200 or status_code >= 300:
            raise ValueError(f"invalid status code: {status_code}")
        if content_type and "application/json" not in content_type:
            raise ValueError("unsupported content-type")

        body = response.get("body")
        if body is None:
            body = response if not {"status_code", "content_type"}.issubset(response.keys()) else {}
        if body is None:
            return {}
        return body if isinstance(body, dict) else {"value": body}
