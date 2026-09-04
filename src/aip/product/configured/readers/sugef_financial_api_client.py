from __future__ import annotations

import json
import time
from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, DivisionByZero, InvalidOperation
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

    # SUGEF identifica cada período contable con el primer día del mes. Balance
    # requiere 12 cortes para promedios; resultados usa períodos puntuales para
    # anualización móvil e indicadores conserva dos meses de contingencia.
    _COMPARATIVE_LOOKBACK_MONTHS = 2
    _AVERAGE_LOOKBACK_MONTHS = 11

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
        jobs = [
            (
                entity_code,
                (
                    self._result_periods(cutoff_date)
                    if statement_type is FinancialStatementType.INCOME_STATEMENT
                    else self._period_range(
                        cutoff_date,
                        lookback_months=(
                            self._AVERAGE_LOOKBACK_MONTHS
                            if statement_type is FinancialStatementType.BALANCE_SHEET
                            else self._COMPARATIVE_LOOKBACK_MONTHS
                        ),
                    )
                ),
                report_name,
                list_key,
                statement_type,
            )
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
                for entity_code, period, report_name, list_key, statement_type in jobs
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
            latest_date = max(line.statement_date for line in lines)
            diagnostics.append(
                "Balance, Estado de Resultados e Indicadores consultados en la API pública oficial de SUGEF."
            )
            diagnostics.append(
                "Último corte SUGEF disponible en el rango consultado: "
                f"{latest_date.strftime('%d/%m/%Y')}."
            )
        return SUGEFApiReadResult(tuple(lines), tuple(sorted(endpoints)), tuple(diagnostics))

    @classmethod
    def _period_range(cls, cutoff_date: date, *, lookback_months: int | None = None) -> str:
        """Build the monthly SUGEF range using first-of-month identifiers."""

        end = date(cutoff_date.year, cutoff_date.month, 1)
        lookback = cls._COMPARATIVE_LOOKBACK_MONTHS if lookback_months is None else lookback_months
        month_index = end.year * 12 + end.month - 1 - lookback
        start_year, zero_based_month = divmod(month_index, 12)
        start = date(start_year, zero_based_month + 1, 1)
        return f"{start.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}"

    @classmethod
    def _result_periods(cls, cutoff_date: date) -> str:
        """Request only the periods needed for TTM results and publication lag."""

        current_candidates = tuple(
            cls._shift_month(date(cutoff_date.year, cutoff_date.month, 1), -offset)
            for offset in range(3)
        )
        periods = set(current_candidates)
        for candidate in current_candidates:
            periods.add(date(candidate.year - 1, candidate.month, 1))
            periods.add(date(candidate.year - 1, 12, 1))
        return ",".join(f"{period:%Y%m%d}" for period in sorted(periods))

    def _read_report(
        self,
        entity_code: str,
        period: str,
        report_name: str,
        list_key: str,
        statement_type: FinancialStatementType,
    ) -> tuple[list[FinancialStatementLine], str]:
        endpoint = self._endpoint(report_name)
        rows: list[Any] | None = None
        best_rows: list[Any] = []
        last_message = "SUGEF no publicó datos para el rango solicitado"
        for candidate_period in self._fallback_periods(period):
            payload = {
                "parametrosEntidad": {
                    "codigoEntidad": entity_code,
                    "periodos": candidate_period,
                    "codigoCuenta": "",
                }
            }
            response = self._post_json(endpoint, payload)
            candidate_rows = response.get(list_key)
            if not bool(response.get("tieneError")) and isinstance(candidate_rows, list):
                if len(candidate_rows) > len(best_rows):
                    best_rows = candidate_rows
                if self._has_expected_coverage(
                    candidate_rows,
                    statement_type,
                    candidate_period=candidate_period,
                ):
                    rows = candidate_rows
                    break
                last_message = "No se encontraron registros para los datos consultados."
            else:
                last_message = str(response.get("mensaje") or "SUGEF reportó un error")
        if rows is None and best_rows:
            rows = best_rows
        if rows is None:
            raise ValueError(last_message)
        result: list[FinancialStatementLine] = []
        for row_number, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                continue
            line = self._line(row, statement_type, endpoint, list_key, row_number)
            if line is not None:
                result.append(line)
        return result, endpoint

    @staticmethod
    def _has_expected_coverage(
        rows: list[Any],
        statement_type: FinancialStatementType,
        *,
        candidate_period: str,
    ) -> bool:
        if not rows:
            return False
        if "-" not in candidate_period:
            return True
        periods = {
            str(row.get("periodo"))[:7]
            for row in rows
            if isinstance(row, dict) and row.get("periodo")
        }
        end = datetime.strptime(candidate_period.partition("-")[2], "%Y%m%d").date()
        latest_expected = SUGEFFinancialApiClient._shift_month(end, -1).strftime("%Y-%m")
        has_latest = bool(periods) and max(periods) >= latest_expected
        if statement_type is FinancialStatementType.BALANCE_SHEET:
            return has_latest and len(periods) >= 12
        return has_latest

    @classmethod
    def _fallback_periods(cls, period: str) -> tuple[str, ...]:
        """Try the requested range and two prior month-ends for publication lag."""

        start_text, separator, end_text = period.partition("-")
        if not separator:
            return (period,)
        start = datetime.strptime(start_text, "%Y%m%d").date()
        end = datetime.strptime(end_text, "%Y%m%d").date()
        return tuple(
            f"{cls._shift_month(start, -offset):%Y%m%d}-" f"{cls._shift_month(end, -offset):%Y%m%d}"
            for offset in range(3)
        )

    @staticmethod
    def _shift_month(value: date, offset: int) -> date:
        month_index = value.year * 12 + value.month - 1 + offset
        year, zero_based_month = divmod(month_index, 12)
        return date(year, zero_based_month + 1, 1)

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
            account_code = self._identifier(row.get("codigoIndicador"))
            account_name = self._text(row.get("nombreIndicador"))
            amount = self._indicator_value(row)
        else:
            account_code = self._identifier(row.get("cuentaIASEF"))
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

    @classmethod
    def _indicator_value(cls, row: dict[str, Any]) -> Decimal | None:
        numerator = cls._decimal(row.get("numerador"))
        denominator = cls._decimal(row.get("denominador"))
        if numerator is not None and denominator not in {None, Decimal("0")}:
            try:
                return numerator / denominator
            except (DivisionByZero, InvalidOperation):
                pass
        published = cls._decimal(row.get("valorIndicador"))
        # Algunas respuestas históricas no incluyen numerador/denominador. En
        # ese formato legado, el valor publicado usa puntos porcentuales.
        return published / Decimal("100") if published is not None else None

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip()

    @classmethod
    def _identifier(cls, value: Any) -> str:
        text = cls._text(value)
        return text[:-2] if text.endswith(".0") and text[:-2].isdigit() else text
