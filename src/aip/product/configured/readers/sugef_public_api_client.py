from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Literal, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)

JSONBody = dict[str, Any] | list[Any]
HTTPMethod = Literal["GET", "POST"]


@dataclass(frozen=True, slots=True)
class SUGEFPublicApiResponse:
    """Respuesta cruda y trazable de una operación pública SUGEF.

    ``body`` conserva exactamente los valores publicados por SUGEF. En
    particular, un ``null`` permanece ``None`` y nunca se transforma en cero.
    ``rows`` expone la colección principal cuando la respuesta utiliza un campo
    ``lista*`` o cuando el cuerpo JSON es directamente una lista.
    """

    operation: str
    endpoint: str
    method: HTTPMethod
    body: JSONBody
    rows: tuple[Mapping[str, Any], ...]


class SUGEFPublicApiClient:
    """Gateway integral para la API pública oficial de SUGEF.

    El cliente permite consumir todas las familias actualmente documentadas por
    SUGEF sin acoplar la aplicación a Power BI ni a scraping HTML:

    * catálogos de cuentas y entidades;
    * encaje mínimo legal;
    * información crediticia vigente y la histórica hasta diciembre de 2023;
    * información financiera-contable (balanza, balances, resultados e
      indicadores), tanto por entidad como por sector o total.

    Se aceptan únicamente operaciones dentro de los prefijos oficiales
    documentados. Esto permite incorporar nuevas variantes publicadas dentro de
    esas familias sin abrir el transporte a URLs arbitrarias.
    """

    _ALLOWED_PREFIXES = (
        "/Catalogo/MAPI/",
        "/ReporteEncajeLegal/MAPI/",
        "/ReporteCrediticio/MAPI/",
        "/ReporteCrediticioHasta2023/MAPI/",
        "/ReportesFinancieraContable/MAPI/",
    )
    _CATALOG_OPERATIONS = {
        "accounts": "/Catalogo/MAPI/ListarCatalogoCuentasContables",
        "entities": "/Catalogo/MAPI/ListarEntidades",
    }
    _CURRENT_CREDIT_REPORTS = {
        "ReporteActividadEconomica",
        "ReporteActividadEconomicaCategoriaRiesgo",
        "ReporteActividadEconomicaDiasAtraso",
        "ReporteCategoriaRiesgo",
        "ReporteCategoriaRiesgoDiasAtraso",
        "ReporteDiasAtraso",
    }
    _HISTORICAL_CREDIT_REPORTS = {
        "ReporteActividadEconomicaHasta2023",
        "ReporteActividadEconomicaCategoriaRiesgoHasta2023",
        "ReporteActividadEconomicaDiasAtrasoHasta2023",
        "ReporteCategoriaRiesgoHasta2023",
        "ReporteCategoriaRiesgoDiasAtrasoHasta2023",
        "ReporteDiasAtrasoHasta2023",
    }

    def __init__(self, config: SUGEFFinancialSourceConfig) -> None:
        self._config = config

    def list_account_catalog(self) -> SUGEFPublicApiResponse:
        return self.request(self._CATALOG_OPERATIONS["accounts"], method="GET")

    def list_entities(self) -> SUGEFPublicApiResponse:
        return self.request(self._CATALOG_OPERATIONS["entities"], method="GET")

    def read_encaje_legal(
        self,
        *,
        entity_code: str = "",
        sector_code: str = "",
        periods: str,
        currency: str = "",
    ) -> SUGEFPublicApiResponse:
        return self.request(
            "/ReporteEncajeLegal/MAPI/ReporteEncajeLegal",
            method="POST",
            payload={
                "parametrosEncajeLegal": {
                    "codigoEntidad": entity_code,
                    "codigoTipoEntidad": sector_code,
                    "periodos": periods,
                    "tipoMoneda": currency,
                }
            },
        )

    def read_credit_report(
        self,
        report_name: str,
        *,
        entity_code: str = "",
        sector_code: str = "",
        periods: str,
        regulation: str = "1",
        days_arrears: str | None = None,
        historical: bool = False,
    ) -> SUGEFPublicApiResponse:
        """Consulta cualquiera de los seis reportes crediticios oficiales.

        Para datos desde enero de 2024 ``historical`` debe permanecer en
        ``False``. Para la serie hasta diciembre de 2023 debe ser ``True`` y el
        nombre de reporte debe ser la variante ``*Hasta2023`` documentada por
        SUGEF.
        """

        allowed = self._HISTORICAL_CREDIT_REPORTS if historical else self._CURRENT_CREDIT_REPORTS
        if report_name not in allowed:
            raise ValueError(f"Reporte crediticio SUGEF no soportado: {report_name}")
        uses_days = "DiasAtraso" in report_name
        parameters: dict[str, Any] = {
            "codigoEntidad": entity_code,
            "codigoTipoEntidad": sector_code,
            "periodos": periods,
            "normativa": regulation,
        }
        wrapper = "parametrosCrediticio"
        if uses_days:
            wrapper = "parametrosCrediticioDiasAtraso"
            parameters["diasAtraso"] = "" if days_arrears is None else days_arrears
        family = "ReporteCrediticioHasta2023" if historical else "ReporteCrediticio"
        return self.request(
            f"/{family}/MAPI/{report_name}",
            method="POST",
            payload={wrapper: parameters},
        )

    def read_financial_entity_report(
        self,
        report_name: str,
        *,
        entity_code: str,
        periods: str,
        account_code: str = "",
    ) -> SUGEFPublicApiResponse:
        return self.request(
            f"/ReportesFinancieraContable/MAPI/{self._safe_operation_name(report_name)}",
            method="POST",
            payload={
                "parametrosEntidad": {
                    "codigoEntidad": entity_code,
                    "periodos": periods,
                    "codigoCuenta": account_code,
                }
            },
        )

    def read_financial_sector_report(
        self,
        report_name: str,
        *,
        sector_code: str,
        periods: str,
        account_code: str = "",
    ) -> SUGEFPublicApiResponse:
        return self.request(
            f"/ReportesFinancieraContable/MAPI/{self._safe_operation_name(report_name)}",
            method="POST",
            payload={
                "parametrosSector": {
                    "codigoTipoEntidad": sector_code,
                    "periodos": periods,
                    "codigoCuenta": account_code,
                }
            },
        )

    def read_financial_total_report(
        self,
        report_name: str,
        *,
        periods: str,
        account_code: str = "",
    ) -> SUGEFPublicApiResponse:
        return self.request(
            f"/ReportesFinancieraContable/MAPI/{self._safe_operation_name(report_name)}",
            method="POST",
            payload={
                "parametrosTotal": {
                    "periodos": periods,
                    "codigoCuenta": account_code,
                }
            },
        )

    def request(
        self,
        operation: str,
        *,
        method: HTTPMethod,
        payload: dict[str, Any] | None = None,
    ) -> SUGEFPublicApiResponse:
        """Ejecuta una operación oficial dentro de las familias SUGEF permitidas."""

        operation = self._validate_operation(operation)
        if method == "GET" and payload is not None:
            raise ValueError("Las operaciones GET SUGEF no aceptan payload JSON.")
        if method == "POST" and payload is None:
            raise ValueError("Las operaciones POST SUGEF requieren payload JSON.")
        endpoint = self._endpoint(operation)
        body = self._request_json(endpoint, method=method, payload=payload)
        return SUGEFPublicApiResponse(
            operation=operation,
            endpoint=endpoint,
            method=method,
            body=body,
            rows=self._extract_rows(body),
        )

    def _request_json(
        self,
        endpoint: str,
        *,
        method: HTTPMethod,
        payload: dict[str, Any] | None,
    ) -> JSONBody:
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(endpoint, data=data, headers=headers, method=method)
        attempts = max(1, self._config.api_retries + 1)
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                with urlopen(request, timeout=self._config.api_timeout_seconds) as response:
                    decoded = json.loads(response.read().decode("utf-8-sig"))
                if not isinstance(decoded, (dict, list)):
                    raise ValueError("la respuesta SUGEF no es un objeto o lista JSON")
                return decoded
            except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    time.sleep(self._config.api_backoff_seconds * (2**attempt))
        assert last_error is not None
        raise last_error

    def _endpoint(self, operation: str) -> str:
        query = urlencode({"api-version": self._config.api_version})
        return f"{self._config.api_base_url.rstrip('/')}{operation}?{query}"

    @classmethod
    def _validate_operation(cls, operation: str) -> str:
        normalized = "/" + operation.strip().lstrip("/")
        if ".." in normalized or "://" in normalized or "?" in normalized or "#" in normalized:
            raise ValueError("Operación SUGEF inválida.")
        if not any(normalized.startswith(prefix) for prefix in cls._ALLOWED_PREFIXES):
            raise ValueError(f"Familia de operación SUGEF no permitida: {operation}")
        return normalized

    @staticmethod
    def _safe_operation_name(report_name: str) -> str:
        value = report_name.strip()
        if not value or not value.replace("_", "").isalnum():
            raise ValueError(f"Nombre de reporte SUGEF inválido: {report_name}")
        return value

    @staticmethod
    def _extract_rows(body: JSONBody) -> tuple[Mapping[str, Any], ...]:
        if isinstance(body, list):
            return tuple(item for item in body if isinstance(item, dict))
        candidates = (
            value
            for key, value in body.items()
            if key.lower().startswith("lista") and isinstance(value, list)
        )
        for candidate in candidates:
            rows = tuple(item for item in candidate if isinstance(item, dict))
            if rows or candidate == []:
                return rows
        return ()
