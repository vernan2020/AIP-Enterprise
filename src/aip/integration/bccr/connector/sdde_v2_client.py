"""Clean SDDE REST v2 connector, independent of the previous BCCR REST stack.

Contract: https://apim.bccr.fi.cr/SDDE/api/Bccr.GE.SDDE.Publico.Indicadores.API
Registered BCCR name and email identify the account; the *only* API
authentication field is Authorization: Bearer <existing private token>.
No secrets are persisted, interpolated into URLs, printed or logged.
"""

from __future__ import annotations

import re
import time
from datetime import date
from threading import Lock
from typing import Any
from urllib.parse import urlencode, urlsplit

from aip.integration.bccr.configuration.bccr_config import BCCRConfig
from aip.integration.bccr.providers.http_provider import HTTPProvider
from aip.integration.bccr.providers.sdde_v2_http_provider import SDDEv2HTTPProvider

_API_PREFIX = "/SDDE/api/Bccr.GE.SDDE.Publico.Indicadores.API"
_CODE = re.compile(r"[0-9]{1,12}\Z")
_VALID_LANGUAGES = frozenset(("ES", "EN"))


class SDDEv2Client:
    """Bounded rate-limited authenticated SDDE series client for Macro Intelligence."""

    _REQUEST_INTERVAL = 0.75
    _BACKOFF_SECONDS = 1.0
    _MAX_RETRY_AFTER = 8.0

    def __init__(
        self, *, config: BCCRConfig, provider: HTTPProvider | None = None
    ) -> None:
        self._config = config
        self._base_url = self._validate_origin(config.base_url)
        self._provider = provider if provider is not None else SDDEv2HTTPProvider()
        self._last_reserved = 0.0
        self._lock = Lock()

    @staticmethod
    def _validate_origin(origin: str) -> str:
        parsed = urlsplit(origin.strip())
        if (
            parsed.scheme != "https"
            or parsed.hostname != "apim.bccr.fi.cr"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
            or parsed.query
            or parsed.fragment
            or parsed.path.rstrip("/") not in ("", "/SDDE")
        ):
            raise ValueError("BCCR SDDE host must be the official HTTPS endpoint")
        return "https://apim.bccr.fi.cr"

    @staticmethod
    def _dates(start: str, end: str) -> tuple[str, str]:
        if not re.fullmatch(r"\d{4}/\d{2}/\d{2}", start) or not re.fullmatch(
            r"\d{4}/\d{2}/\d{2}", end
        ):
            raise ValueError("BCCR SDDE dates must use yyyy/mm/dd")
        begin = date.fromisoformat(start.replace("/", "-"))
        finish = date.fromisoformat(end.replace("/", "-"))
        if begin > finish:
            raise ValueError("BCCR SDDE start date exceeds end date")
        return start, end

    def _url(
        self, *, segment: str, code: str, from_date: str, to_date: str, language: str
    ) -> str:
        if not _CODE.fullmatch(str(code)):
            raise ValueError("BCCR SDDE code must be a positive integer")
        if int(code) <= 0:
            raise ValueError("BCCR SDDE code must be a positive integer")
        start, end = self._dates(from_date, to_date)
        locale = language.upper()
        if locale not in _VALID_LANGUAGES:
            raise ValueError("Unsupported SDDE language")
        query = urlencode({"fechaInicio": start, "fechaFin": end, "idioma": locale})
        return f"{self._base_url}{_API_PREFIX}/{segment}/{code}/series?{query}"

    def build_url(
        self, *, indicator_code: str, from_date: str, to_date: str, language: str = "ES"
    ) -> str:
        return self._url(
            segment="indicadoresEconomicos",
            code=indicator_code,
            from_date=from_date,
            to_date=to_date,
            language=language,
        )

    def build_chart_url(
        self, *, chart_code: str, from_date: str, to_date: str, language: str = "ES"
    ) -> str:
        return self._url(
            segment="cuadro",
            code=chart_code,
            from_date=from_date,
            to_date=to_date,
            language=language,
        )

    def fetch_series(
        self, *, indicator_code: str, from_date: str, to_date: str
    ) -> dict[str, Any]:
        return self._request(
            self.build_url(
                indicator_code=indicator_code, from_date=from_date, to_date=to_date
            ),
            resource="indicator",
        )

    def fetch_chart_series(
        self, *, chart_code: str, from_date: str, to_date: str
    ) -> dict[str, Any]:
        return self._request(
            self.build_chart_url(chart_code=chart_code, from_date=from_date, to_date=to_date),
            resource="chart",
        )

    def _throttle(self) -> None:
        with self._lock:
            now = time.monotonic()
            next_start = max(now, self._last_reserved + self._REQUEST_INTERVAL)
            self._last_reserved = next_start
        delay = next_start - now
        if delay > 0:
            time.sleep(delay)

    def _request(self, url: str, *, resource: str) -> dict[str, Any]:
        token = (self._config.token or "").strip()
        if not token or "\r" in token or "\n" in token:
            raise ValueError("BCCR SDDE bearer token is missing or invalid")
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        attempts = self._config.retry_attempts + 1
        for attempt in range(attempts):
            self._throttle()
            try:
                result = self._provider.get(
                    url, timeout=self._config.timeout_seconds, headers=headers
                )
            except (TimeoutError, ConnectionError, OSError) as exc:
                if attempt + 1 == attempts:
                    raise ConnectionError("BCCR SDDE transport unavailable") from exc
                time.sleep(self._BACKOFF_SECONDS * (attempt + 1))
                continue
            status = int(result.get("status_code", 0))
            if 200 <= status < 300:
                body = result.get("body")
                if not isinstance(body, dict) or body.get("estado") is not True:
                    raise ValueError("BCCR SDDE returned unsuccessful or invalid JSON")
                data = body.get("datos")
                if not isinstance(data, list):
                    raise ValueError("BCCR SDDE response does not contain datos list")
                # Do not interpret an HTTP-200 empty series as a valid price.
                return {
                    "status_code": status,
                    "body": {"estado": True, "mensaje": "Consulta exitosa", "datos": data},
                }
            if status not in (429, 502, 503, 504) or attempt + 1 == attempts:
                raise ConnectionError(f"BCCR SDDE HTTP {status} on {resource} request")
            retry_header = result.get("headers") or {}
            raw_retry = next(
                (value for key, value in retry_header.items() if key.lower() == "retry-after"),
                None,
            )
            try:
                delay = float(raw_retry)
            except (TypeError, ValueError):
                delay = self._BACKOFF_SECONDS * (attempt + 1)
            time.sleep(min(self._MAX_RETRY_AFTER, max(0.0, delay)))
        raise ConnectionError("BCCR SDDE request failed")

    def close(self) -> None:
        close = getattr(self._provider, "close", None)
        if callable(close):
            close()
