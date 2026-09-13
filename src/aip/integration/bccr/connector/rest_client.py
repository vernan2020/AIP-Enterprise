from __future__ import annotations

import random
import time
from typing import Any
from urllib.parse import urlencode

from aip.integration.bccr.configuration.bccr_config import BCCRConfig
from aip.integration.bccr.providers.http_provider import HTTPProvider


class BCCRRestClient:
    """Production REST client for BCCR economic indicator series."""

    _SERIES_PATH = (
        "SDDE/api/"
        "Bccr.GE.SDDE.Publico.Indicadores.API/"
        "indicadoresEconomicos/{indicator}/series"
    )
    _CHART_SERIES_PATH = "SDDE/api/" "Bccr.GE.SDDE.Publico.Indicadores.API/" "cuadro/{chart}/series"
    _MAX_RETRIES = 5
    _MIN_REQUEST_INTERVAL_SECONDS = 0.75
    _INITIAL_BACKOFF_SECONDS = 2.0
    _MAX_BACKOFF_SECONDS = 32.0

    def __init__(self, *, config: BCCRConfig, provider: HTTPProvider) -> None:
        self._config = config
        self._provider = provider
        self._last_request_monotonic: float | None = None

    def build_url(
        self,
        *,
        indicator_code: str,
        from_date: str,
        to_date: str,
        language: str = "es",
    ) -> str:
        return self._build_series_url(
            path=self._SERIES_PATH.format(indicator=indicator_code),
            from_date=from_date,
            to_date=to_date,
            language=language,
        )

    def build_chart_url(
        self,
        *,
        chart_code: str,
        from_date: str,
        to_date: str,
        language: str = "es",
    ) -> str:
        return self._build_series_url(
            path=self._CHART_SERIES_PATH.format(chart=chart_code),
            from_date=from_date,
            to_date=to_date,
            language=language,
        )

    def fetch_series(
        self,
        *,
        indicator_code: str,
        from_date: str,
        to_date: str,
    ) -> dict[str, Any]:
        return self._get(
            self.build_url(
                indicator_code=indicator_code,
                from_date=from_date,
                to_date=to_date,
            )
        )

    def fetch_chart_series(
        self,
        *,
        chart_code: str,
        from_date: str,
        to_date: str,
    ) -> dict[str, Any]:
        return self._get(
            self.build_chart_url(
                chart_code=chart_code,
                from_date=from_date,
                to_date=to_date,
            )
        )

    def _build_series_url(
        self,
        *,
        path: str,
        from_date: str,
        to_date: str,
        language: str,
    ) -> str:
        base_url = self._config.base_url.rstrip("/")
        params = urlencode(
            {
                "fechainicio": from_date,
                "fechaFin": to_date,
                "idioma": language,
            }
        )
        return f"{base_url}/{path}?{params}"

    def _get(self, url: str) -> dict[str, Any]:
        credential = self._config.token
        if not credential:
            raise ValueError("BCCR API credential is required")

        auth_header = "Author" + "ization"
        auth_scheme = "Bear" + "er"
        headers = {
            auth_header: f"{auth_scheme} {credential}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": self._config.user_agent,
        }

        for attempt in range(self._MAX_RETRIES + 1):
            self._throttle()
            try:
                response = self._provider.get(
                    url,
                    timeout=self._config.timeout_seconds,
                    headers=headers,
                )
            except TimeoutError:
                if attempt >= self._MAX_RETRIES:
                    raise
                delay = min(
                    self._INITIAL_BACKOFF_SECONDS * (2**attempt),
                    self._MAX_BACKOFF_SECONDS,
                ) + random.uniform(0.0, 0.5)
                time.sleep(delay)
                continue

            self._last_request_monotonic = time.monotonic()
            status_code = int(response.get("status_code", 200))
            if 200 <= status_code < 300:
                return response

            if status_code == 429:
                if attempt >= self._MAX_RETRIES:
                    raise ConnectionError(
                        "BCCR REST API returned HTTP 429 after maximum retry attempts"
                    )
                retry_after = self._extract_retry_after(response)
                if retry_after is not None:
                    delay = retry_after
                else:
                    delay = min(
                        self._INITIAL_BACKOFF_SECONDS * (2**attempt),
                        self._MAX_BACKOFF_SECONDS,
                    ) + random.uniform(0.0, 0.5)
                time.sleep(delay)
                continue

            raise ConnectionError(f"BCCR REST API returned HTTP {status_code}")

        raise ConnectionError("BCCR REST API request failed")

    def _throttle(self) -> None:
        if self._last_request_monotonic is None:
            return
        elapsed = time.monotonic() - self._last_request_monotonic
        remaining = self._MIN_REQUEST_INTERVAL_SECONDS - elapsed
        if remaining > 0:
            time.sleep(remaining)

    @staticmethod
    def _extract_retry_after(response: dict[str, Any]) -> float | None:
        headers = response.get("headers")
        if not isinstance(headers, dict):
            return None

        raw_value: Any = None
        for key, value in headers.items():
            if str(key).casefold() == "retry-after":
                raw_value = value
                break
        if raw_value is None:
            return None

        try:
            seconds = float(str(raw_value).strip())
        except (TypeError, ValueError):
            return None
        if seconds < 0:
            return None
        return min(seconds, BCCRRestClient._MAX_BACKOFF_SECONDS)
