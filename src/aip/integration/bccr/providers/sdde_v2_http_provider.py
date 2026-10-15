"""New reusable SDDE HTTP transport; never logs bearer credentials or response bodies."""

from __future__ import annotations

from typing import Any

from aip.integration.bccr.providers.http_provider import HTTPProvider


class SDDEv2HTTPProvider(HTTPProvider):
    """Pooled TLS-verified httpx client, safe for concurrent macro series requests."""

    def __init__(self, *, transport: Any | None = None) -> None:
        import httpx

        self._httpx = httpx
        self._client = httpx.Client(
            transport=transport,
            timeout=30.0,
            follow_redirects=False,
            trust_env=True,
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=4),
        )

    def get(
        self, url: str, *, timeout: float, headers: dict[str, str] | None = None
    ) -> dict[str, Any]:
        try:
            response = self._client.get(url, headers=headers, timeout=timeout)
        except self._httpx.TimeoutException as exc:
            raise TimeoutError("BCCR SDDE request timeout") from exc
        except self._httpx.RequestError as exc:
            raise ConnectionError("BCCR SDDE connection failed") from exc

        # Never preserve arbitrary server data for an HTTP error. In particular,
        # upstream error pages can echo sensitive request information.
        body: object | None = None
        if 200 <= response.status_code < 300:
            try:
                body = response.json()
            except ValueError as exc:
                raise ValueError("BCCR SDDE returned malformed JSON") from exc

        return {
            "status_code": response.status_code,
            "content_type": response.headers.get("content-type", ""),
            "headers": {"retry-after": response.headers.get("retry-after", "")},
            "body": body,
        }

    def close(self) -> None:
        self._client.close()
