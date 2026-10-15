from __future__ import annotations

from typing import Any

from aip.integration.bccr.providers.http_provider import HTTPProvider


class HttpxHTTPProvider(HTTPProvider):
    """SDDE transport matching TicoTrader's httpx GET, without redirect following.

    Return the existing AIP response envelope; never log request headers,
    tokens, URLs containing query strings or raw error response bodies.
    """

    def __init__(self, *, transport: Any | None = None) -> None:
        self._transport = transport

    def get(
        self,
        url: str,
        *,
        timeout: float,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        import httpx

        try:
            with httpx.Client(
                timeout=timeout,
                follow_redirects=False,
                transport=self._transport,
            ) as client:
                response = client.get(url, headers=headers)
                content_type = response.headers.get("Content-Type", "")
                try:
                    body = response.json()
                except ValueError as exc:
                    if 200 <= response.status_code < 300:
                        raise ValueError("BCCR response is not valid JSON") from exc
                    body = None
                return {
                    "status_code": response.status_code,
                    "content_type": content_type,
                    "headers": dict(response.headers),
                    "body": body,
                }
        except httpx.TimeoutException as exc:
            raise TimeoutError("BCCR HTTP request timed out") from exc
        except httpx.RequestError as exc:
            raise ConnectionError("BCCR HTTP transport unavailable") from exc
