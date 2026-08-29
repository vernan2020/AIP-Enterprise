from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from aip.integration.bccr.providers.http_provider import (
    HTTPProvider,
)


class UrllibHTTPProvider(HTTPProvider):
    """
    HTTP transport productivo basado en urllib.

    Retorna:
    - status_code
    - content_type
    - headers
    - body

    Los headers se preservan para permitir tratamiento
    de Retry-After, rate limiting y observabilidad HTTP.
    """

    def get(
        self,
        url: str,
        *,
        timeout: float,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        request = Request(
            url=url,
            headers=headers or {},
            method="GET",
        )

        try:
            with urlopen(
                request,
                timeout=timeout,
            ) as response:
                status_code = int(
                    getattr(
                        response,
                        "status",
                        200,
                    )
                )

                response_headers = (
                    self._normalize_headers(
                        response.headers
                    )
                )

                content_type = (
                    response_headers.get(
                        "Content-Type",
                        "",
                    )
                )

                raw_body = response.read()

        except HTTPError as exc:
            response_headers = (
                self._normalize_headers(
                    exc.headers
                )
            )

            content_type = (
                response_headers.get(
                    "Content-Type",
                    "",
                )
            )

            raw_error = exc.read()

            body = self._decode_body(
                raw_error,
                content_type,
                strict_json=False,
            )

            return {
                "status_code": int(
                    exc.code
                ),
                "content_type": (
                    content_type
                ),
                "headers": (
                    response_headers
                ),
                "body": body,
            }

        except URLError as exc:
            raise ConnectionError(
                f"HTTP connection failed: {exc}"
            ) from exc

        body = self._decode_body(
            raw_body,
            content_type,
            strict_json=True,
        )

        return {
            "status_code": status_code,
            "content_type": (
                content_type
            ),
            "headers": (
                response_headers
            ),
            "body": body,
        }

    @staticmethod
    def _normalize_headers(
        raw_headers: object,
    ) -> dict[str, str]:
        """
        Convierte los headers HTTP a un diccionario
        estándar de strings.
        """

        if raw_headers is None:
            return {}

        try:
            items = raw_headers.items()
        except AttributeError:
            return {}

        return {
            str(key): str(value)
            for key, value
            in items
        }

    @staticmethod
    def _decode_body(
        raw_body: bytes,
        content_type: str,
        *,
        strict_json: bool,
    ) -> object:
        """
        Decodifica el cuerpo HTTP.

        En respuestas exitosas con Content-Type JSON,
        un JSON inválido genera ValueError.

        En respuestas de error se conserva el texto
        recibido aunque no sea JSON válido.
        """

        if not raw_body:
            return {}

        text = raw_body.decode(
            "utf-8",
            errors="replace",
        )

        if (
            "json"
            not in content_type.casefold()
        ):
            return text

        try:
            return json.loads(
                text
            )

        except json.JSONDecodeError as exc:
            if strict_json:
                raise ValueError(
                    "Invalid JSON response"
                ) from exc

            return text
