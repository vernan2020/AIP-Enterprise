from __future__ import annotations

import json
import time
from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialStatementLine,
    FinancialStatementType,
    SourceTrace,
)
from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)


@dataclass(frozen=True, slots=True)
class SUGEFApiReadResult:
    lines: tuple[FinancialStatementLine, ...]
    endpoints: tuple[str, ...]
    diagnostics: tuple[str, ...]


class SUGEFFinancialApiClient:
    """Gateway tipado para la API pública oficial de reportes SUGEF."""

    _REPORTS = (
        (
            "ReporteBalanceSituacionAnalisisFinancieroEntidad",
            "listaBalanceSituacionAnalisisFinancieroEntidad",
            FinancialStatementType.BALANCE_SHEET,
        ),
        (
            "ReporteEstadoResultadosAnalisisFinancieroEntidad",
            "listaEstadoResultadosAnalisisFinancieroEntidad",
            FinancialStatementType.INCOME_STATEMENT,
        ),
        (
            "ReporteIndicadoresFinancierosEntidad",
            "listaIndicadoresFinancierosEntidad",
            FinancialStatementType.INDICATORS,
        ),
    )
    _SOURCE_NAME = "SUGEF - API pública de Información Financiera Contable"

    def __init__(self, config: SUGEFFinancialSourceConfig) -> None:
        self._config = config

    def read(self, cutoff_date: date) -> SUGEFApiReadResult:
        period = cutoff_date.strftime("%Y%m%d")
        jobs = [
            (entity_code, report_name, list_key, statement_type)
            for entity_code in self._config.api_entity_codes
            for report_name, list_key, statement_type in self._REPORTS
        ]
        lines: list[FinancialStatementLine] = []
        endpoints: set[str] = set()
        diagnostics: list[str] = []
        if not jobs:
            return SUGEFApiReadResult((), (), ("No hay códigos de entidad SUGEF configurados.",))

        with ThreadPoolExecutor(max_workers=min(8, len(jobs))) as executor:
            futures = {
                executor.submit(
                    self._read_report,
                    entity_code,
                    period,
                    report_name,
                    list_key,
                    statement_type,
                ): (entity_code, report_name)
                for entity_code, report_name, list_key, statement_type in jobs
            }
            for future in as_completed(futures):
                entity_code, report_name = futures[future]
                try:
                    report_lines, endpoint = future.result()
                    lines.extend(report_lines)
                    endpoints.add(endpoint)
                except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
                    diagnostics.append(
                        f"SUGEF API {report_name} ({entity_code}): " f"{type(exc).__name__}: {exc}"
                    )

        if lines:
            diagnostics.append(
                "Balance, Estado de Resultados e Indicadores consultados en la API pública oficial de SUGEF."
            )
        return SUGEFApiReadResult(tuple(lines), tuple(sorted(endpoints)), tuple(diagnostics))

    def _read_report(
        self,
        entity_code: str,
        period: str,
        report_name: str,
        list_key: str,
        statement_type: FinancialStatementType,
    ) -> tuple[list[FinancialStatementLine], str]:
        endpoint = self._endpoint(report_name)
        payload = {
            "parametrosEntidad": {
                "codigoEntidad": entity_code,
                "periodos": period,
                "codigoCuenta": "",
            }
        }
        response = self._post_json(endpoint, payload)
        if bool(response.get("tieneError")):
            raise ValueError(str(response.get("mensaje") or "SUGEF reportó un error"))
        rows = response.get(list_key)
        if not isinstance(rows, list):
            raise ValueError(f"respuesta sin la colección esperada {list_key}")
        result: list[FinancialStatementLine] = []
        for row_number, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                continue
            line = self._line(row, statement_type, endpoint, list_key, row_number)
            if line is not None:
                result.append(line)
        return result, endpoint

    def _post_json(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            endpoint,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            method="POST",
        )
        attempts = max(1, self._config.api_retries + 1)
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                with urlopen(request, timeout=self._config.api_timeout_seconds) as response:
                    decoded = json.loads(response.read().decode("utf-8-sig"))
                if not isinstance(decoded, dict):
                    raise ValueError("la respuesta SUGEF no es un objeto JSON")
                return decoded
            except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    time.sleep(self._config.api_backoff_seconds * (2**attempt))
        assert last_error is not None
        raise last_error

    def _endpoint(self, report_name: str) -> str:
        query = urlencode({"api-version": self._config.api_version})
        return (
            f"{self._config.api_base_url.rstrip('/')}"
            f"/ReportesFinancieraContable/MAPI/{report_name}?{query}"
        )

    def _line(
        self,
        row: dict[str, Any],
        statement_type: FinancialStatementType,
        endpoint: str,
        list_key: str,
        row_number: int,
    ) -> FinancialStatementLine | None:
        entity_id = self._text(row.get("codigoEntidad"))
        entity_name = self._text(row.get("nombreEntidad"))
        statement_date = self._month_end(row.get("periodo"))
        if statement_type is FinancialStatementType.INDICATORS:
            account_code = self._text(row.get("codigoIndicador"))
            account_name = self._text(row.get("nombreIndicador"))
            amount = self._decimal(row.get("valorIndicador"))
        else:
            account_code = self._text(row.get("cuentaIASEF"))
            account_name = self._text(row.get("nombreCuenta"))
            amount = self._decimal(row.get("saldoIASEF"))
        if not entity_id or not entity_name or statement_date is None:
            return None
        # Null is unavailable data. It must never be silently converted to zero.
        if not account_name or amount is None:
            return None
        entity = FinancialEntity(
            entity_id=entity_id,
            name=entity_name,
            category=self._text(row.get("descripcionSector")) or "Sin clasificar",
        )
        return FinancialStatementLine(
            entity=entity,
            statement_date=statement_date,
            statement_type=statement_type,
            account_code=account_code,
            account_name=account_name,
            amount=amount,
            currency="CRC",
            trace=SourceTrace(
                source_name=self._SOURCE_NAME,
                source_url=self._config.api_base_url,
                file_path=endpoint,
                sheet_name=list_key,
                row_number=row_number,
            ),
        )

    @staticmethod
    def _month_end(value: Any) -> date | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            return None
        return date(parsed.year, parsed.month, monthrange(parsed.year, parsed.month)[1])

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip()
