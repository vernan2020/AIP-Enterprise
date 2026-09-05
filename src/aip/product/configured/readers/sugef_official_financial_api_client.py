from __future__ import annotations

from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.error import HTTPError, URLError

from aip.domain.financial_analysis.models import FinancialStatementLine, FinancialStatementType
from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_financial_api_client import (
    SUGEFApiReadResult,
    SUGEFFinancialApiClient,
)


@dataclass(frozen=True, slots=True)
class _PrimaryProbe:
    cutoff: date
    balance_lines: tuple[FinancialStatementLine, ...]
    income_lines: tuple[FinancialStatementLine, ...]
    endpoints: tuple[str, ...]


class SUGEFOfficialFinancialApiClient(SUGEFFinancialApiClient):
    """Gateway SUGEF estricto para estados oficiales y universo comparativo SFN.

    La entidad configurada se consulta de forma directa para Balance, Resultados
    e Indicadores. Antes de descargar historia y pares se resuelve el último corte
    contable completo disponible que no excede la fecha solicitada.

    La historia necesaria para 08ME14-01 se obtiene con consultas filtradas por
    ``codigoCuenta``. Esto evita descargar estados completos de decenas de
    entidades y reduce sustancialmente la presión sobre la API pública de SUGEF.
    """

    _BALANCE_REPORT = (
        "ReporteBalanceSituacionAnalisisFinancieroEntidad",
        "listaBalanceSituacionAnalisisFinancieroEntidad",
        FinancialStatementType.BALANCE_SHEET,
    )
    _INCOME_REPORT = (
        "ReporteEstadoResultadosAnalisisFinancieroEntidad",
        "listaEstadoResultadosAnalisisFinancieroEntidad",
        FinancialStatementType.INCOME_STATEMENT,
    )
    _INDICATOR_REPORT = (
        "ReporteIndicadoresFinancierosEntidad",
        "listaIndicadoresFinancierosEntidad",
        FinancialStatementType.INDICATORS,
    )
    _METHODOLOGY_BALANCE_ACCOUNTS = ("10000", "25000")
    _METHODOLOGY_INCOME_ACCOUNTS = ("30000", "31000", "31300", "32000")
    _MAX_DIRECT_PEER_RECOVERY = 4

    def __init__(self, config: SUGEFFinancialSourceConfig) -> None:
        super().__init__(config)

    def read(self, cutoff_date: date) -> SUGEFApiReadResult:
        lines: list[FinancialStatementLine] = []
        endpoints: set[str] = set()
        diagnostics: list[str] = []

        # Fase 0: confirmar un corte contable completo de la entidad principal.
        # Las mismas filas del sondeo se reutilizan para evitar que una segunda
        # llamada idéntica falle después de haber confirmado exitosamente el corte.
        primary_probe = self._resolve_primary_statement_cutoff(cutoff_date, diagnostics)

        if primary_probe is not None:
            resolved_cutoff = primary_probe.cutoff
            lines.extend(primary_probe.balance_lines)
            lines.extend(primary_probe.income_lines)
            endpoints.update(primary_probe.endpoints)

            # Fase 1: recuperar solo las cuentas históricas requeridas por las
            # fórmulas 08ME14-01. El estado completo del corte ya proviene del
            # sondeo anterior, por lo que no se repite una descarga histórica masiva.
            primary_history_jobs = self._methodology_history_jobs(
                self._config.api_entity_codes,
                resolved_cutoff,
            )
            self._execute_filtered_jobs(
                primary_history_jobs,
                lines,
                endpoints,
                diagnostics,
            )

        effective_cutoff = self._primary_statement_cutoff(lines)
        if effective_cutoff is not None:
            effective_period = date(
                effective_cutoff.year,
                effective_cutoff.month,
                1,
            ).strftime("%Y%m%d")

            # Fase 2: indicadores directos de la entidad configurada. No se debe
            # depender de la consulta masiva del SFN para los valores propios.
            primary_indicator_jobs = [
                (entity_code, effective_period, *self._INDICATOR_REPORT)
                for entity_code in self._config.api_entity_codes
            ]
            self._execute_jobs(primary_indicator_jobs, lines, endpoints, diagnostics)

            # Fase 3: indicadores comparativos SFN en una llamada dedicada.
            self._execute_jobs(
                [("", effective_period, *self._INDICATOR_REPORT)],
                lines,
                endpoints,
                diagnostics,
            )

            # Fase 4: historia comparativa optimizada. Se solicitan exclusivamente
            # las seis cuentas IAESF requeridas por 08ME14-01 para todo el universo.
            filtered_peer_jobs = self._methodology_history_jobs(("",), effective_cutoff)
            self._execute_filtered_jobs(
                filtered_peer_jobs,
                lines,
                endpoints,
                diagnostics,
            )

            # No existe fallback a descargas completas del universo: si la API
            # filtrada no entrega suficiente historia se conserva N/D. Solo se
            # permite una recuperación directa, filtrada y acotada cuando son muy
            # pocas las entidades faltantes.
            self._recover_incomplete_peer_history(
                effective_cutoff,
                lines,
                endpoints,
                diagnostics,
            )

        lines = self._deduplicate(lines)
        lines = self._clip_to_primary_statement_cutoff(lines)
        effective_cutoff = self._primary_statement_cutoff(lines)
        if lines and effective_cutoff is not None:
            if effective_cutoff < cutoff_date:
                diagnostics.append(
                    "Corte solicitado en AIP: "
                    f"{cutoff_date.strftime('%d/%m/%Y')}; último corte contable SUGEF "
                    f"completo utilizable: {effective_cutoff.strftime('%d/%m/%Y')}."
                )
            else:
                diagnostics.append(
                    "Corte contable SUGEF completo confirmado: "
                    f"{effective_cutoff.strftime('%d/%m/%Y')}."
                )
            diagnostics.extend(
                (
                    "Balance y Estado de Resultados del corte efectivo consultados exclusivamente en la API pública oficial de SUGEF.",
                    "Indicadores de la entidad seleccionada se consultan directamente en SUGEF; el universo comparativo SFN se consulta mediante codigoEntidad vacío en una llamada dedicada.",
                    "Historia 08ME14-01 optimizada mediante codigoCuenta para las cuentas IAESF 10000, 25000, 30000, 31000, 31300 y 32000; no se descargan estados completos de cada par.",
                )
            )
        else:
            diagnostics.append("La API pública de SUGEF no devolvió registros utilizables.")

        return SUGEFApiReadResult(
            lines=tuple(lines),
            endpoints=tuple(sorted(endpoints)),
            diagnostics=tuple(diagnostics),
        )

    def _resolve_primary_statement_cutoff(
        self,
        requested_cutoff: date,
        diagnostics: list[str],
    ) -> _PrimaryProbe | None:
        if not self._config.api_entity_codes:
            diagnostics.append("No hay códigos de entidad SUGEF configurados.")
            return None

        primary = self._config.api_entity_codes[0]
        requested_month = date(requested_cutoff.year, requested_cutoff.month, 1)
        probe_failures: list[str] = []

        for offset in range(self._COMPARATIVE_LOOKBACK_MONTHS + 1):
            candidate = self._shift_month(requested_month, -offset)
            period = candidate.strftime("%Y%m%d")
            try:
                balance_lines, balance_endpoint = self._read_report(
                    primary,
                    period,
                    *self._BALANCE_REPORT,
                )
                income_lines, income_endpoint = self._read_report(
                    primary,
                    period,
                    *self._INCOME_REPORT,
                )
            except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
                probe_failures.append(
                    f"Sondeo SUGEF {candidate.strftime('%d/%m/%Y')}: "
                    f"{type(exc).__name__}: {exc}"
                )
                continue

            balance_dates = {
                line.statement_date
                for line in balance_lines
                if line.entity.entity_id == primary
                and line.statement_type is FinancialStatementType.BALANCE_SHEET
            }
            income_dates = {
                line.statement_date
                for line in income_lines
                if line.entity.entity_id == primary
                and line.statement_type is FinancialStatementType.INCOME_STATEMENT
            }
            common_dates = balance_dates & income_dates
            if common_dates:
                cutoff = max(common_dates)
                return _PrimaryProbe(
                    cutoff=cutoff,
                    balance_lines=tuple(
                        line for line in balance_lines if line.statement_date == cutoff
                    ),
                    income_lines=tuple(
                        line for line in income_lines if line.statement_date == cutoff
                    ),
                    endpoints=(balance_endpoint, income_endpoint),
                )
            probe_failures.append(
                "Sondeo SUGEF "
                f"{candidate.strftime('%d/%m/%Y')}: no existe un corte común de Balance y Resultados."
            )

        diagnostics.append(
            "No se encontró un corte contable SUGEF completo (Balance + Estado de Resultados) "
            f"que no exceda {requested_cutoff.strftime('%d/%m/%Y')} dentro de la ventana de publicación."
        )
        diagnostics.extend(probe_failures)
        return None

    def _execute_jobs(
        self,
        jobs: list[tuple[str, str, str, str, FinancialStatementType]],
        lines: list[FinancialStatementLine],
        endpoints: set[str],
        diagnostics: list[str],
    ) -> None:
        if not jobs:
            return
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
                    scope = entity_code or "SFN completo"
                    diagnostics.append(
                        f"SUGEF API {report_name} ({scope}): " f"{type(exc).__name__}: {exc}"
                    )

    def _execute_filtered_jobs(
        self,
        jobs: list[tuple[str, str, str, str, FinancialStatementType, str]],
        lines: list[FinancialStatementLine],
        endpoints: set[str],
        diagnostics: list[str],
    ) -> None:
        if not jobs:
            return
        with ThreadPoolExecutor(max_workers=min(2, len(jobs))) as executor:
            futures = {
                executor.submit(
                    self._read_filtered_report,
                    entity_code,
                    period,
                    report_name,
                    list_key,
                    statement_type,
                    account_code,
                ): (entity_code, report_name, account_code)
                for entity_code, period, report_name, list_key, statement_type, account_code in jobs
            }
            for future in as_completed(futures):
                entity_code, report_name, account_code = futures[future]
                try:
                    report_lines, endpoint = future.result()
                    lines.extend(report_lines)
                    endpoints.add(endpoint)
                except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
                    scope = entity_code or "SFN completo"
                    diagnostics.append(
                        f"SUGEF API {report_name} ({scope}, cuenta {account_code}): "
                        f"{type(exc).__name__}: {exc}"
                    )

    def _read_filtered_report(
        self,
        entity_code: str,
        period: str,
        report_name: str,
        list_key: str,
        statement_type: FinancialStatementType,
        account_code: str,
    ) -> tuple[list[FinancialStatementLine], str]:
        endpoint = self._endpoint(report_name)
        rows: list[Any] | None = None
        best_rows: list[Any] = []
        last_message = "SUGEF no publicó datos para el rango solicitado"
        last_error: Exception | None = None

        for candidate_period in self._fallback_periods(period):
            payload = {
                "parametrosEntidad": {
                    "codigoEntidad": entity_code,
                    "periodos": candidate_period,
                    "codigoCuenta": account_code,
                }
            }
            try:
                response = self._post_json(endpoint, payload)
            except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
                last_error = exc
                last_message = f"{type(exc).__name__}: {exc}"
                continue

            last_error = None
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
            if last_error is not None:
                raise last_error
            raise ValueError(last_message)

        result: list[FinancialStatementLine] = []
        for row_number, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                continue
            line = self._line(row, statement_type, endpoint, list_key, row_number)
            if line is not None:
                result.append(line)
        return result, endpoint

    def _methodology_history_jobs(
        self,
        entity_codes: tuple[str, ...],
        cutoff_date: date,
    ) -> list[tuple[str, str, str, str, FinancialStatementType, str]]:
        balance_period = self._period_range(
            cutoff_date,
            lookback_months=self._AVERAGE_LOOKBACK_MONTHS,
        )
        income_period = self._result_periods(cutoff_date)
        jobs: list[tuple[str, str, str, str, FinancialStatementType, str]] = []
        for entity_code in entity_codes:
            jobs.extend(
                (entity_code, balance_period, *self._BALANCE_REPORT, account_code)
                for account_code in self._METHODOLOGY_BALANCE_ACCOUNTS
            )
            jobs.extend(
                (entity_code, income_period, *self._INCOME_REPORT, account_code)
                for account_code in self._METHODOLOGY_INCOME_ACCOUNTS
            )
        return jobs

    def _recover_incomplete_peer_history(
        self,
        cutoff_date: date,
        lines: list[FinancialStatementLine],
        endpoints: set[str],
        diagnostics: list[str],
    ) -> None:
        missing = self._missing_peer_history(lines, cutoff_date)
        if not missing:
            return
        if len(missing) > self._MAX_DIRECT_PEER_RECOVERY:
            diagnostics.append(
                "Recuperación directa de historia SUGEF para comparables omitida: "
                f"{len(missing)} entidades faltantes exceden el máximo seguro de "
                f"{self._MAX_DIRECT_PEER_RECOVERY}; se evita sobrecargar la API pública."
            )
            return

        jobs = self._methodology_history_jobs(missing, cutoff_date)
        self._execute_filtered_jobs(jobs, lines, endpoints, diagnostics)
        recovered = sum(self._has_methodology_history(lines, code, cutoff_date) for code in missing)
        diagnostics.append(
            "Recuperación directa y filtrada de historia SUGEF para comparables 08ME14-01: "
            f"{recovered}/{len(missing)} entidades con historia completa tras la recuperación."
        )

    def _missing_peer_history(
        self,
        lines: list[FinancialStatementLine],
        cutoff_date: date,
    ) -> tuple[str, ...]:
        primary_codes = set(self._config.api_entity_codes)
        peer_codes = sorted(
            {
                line.entity.entity_id
                for line in lines
                if line.statement_date == cutoff_date
                and line.statement_type is FinancialStatementType.INDICATORS
                and line.entity.entity_id not in primary_codes
            }
        )
        return tuple(
            code
            for code in peer_codes
            if not self._has_methodology_history(lines, code, cutoff_date)
        )

    @classmethod
    def _has_methodology_history(
        cls,
        lines: list[FinancialStatementLine],
        entity_code: str,
        cutoff_date: date,
    ) -> bool:
        balance_by_account: dict[str, set[date]] = {
            account: set() for account in cls._METHODOLOGY_BALANCE_ACCOUNTS
        }
        income_by_account: dict[str, set[date]] = {
            account: set() for account in cls._METHODOLOGY_INCOME_ACCOUNTS
        }
        for line in lines:
            if line.entity.entity_id != entity_code or line.statement_date > cutoff_date:
                continue
            account = line.account_code.removesuffix(".0")
            if (
                line.statement_type is FinancialStatementType.BALANCE_SHEET
                and account in balance_by_account
            ):
                balance_by_account[account].add(line.statement_date)
            elif (
                line.statement_type is FinancialStatementType.INCOME_STATEMENT
                and account in income_by_account
            ):
                income_by_account[account].add(line.statement_date)

        required_income_dates = {
            cutoff_date,
            cls._month_end_date(cutoff_date.year - 1, cutoff_date.month),
            cls._month_end_date(cutoff_date.year - 1, 12),
        }
        return all(
            cutoff_date in dates and len(dates) >= cls._AVERAGE_LOOKBACK_MONTHS + 1
            for dates in balance_by_account.values()
        ) and all(
            required_income_dates.issubset(dates) for dates in income_by_account.values()
        )

    @staticmethod
    def _month_end_date(year: int, month: int) -> date:
        return date(year, month, monthrange(year, month)[1])

    @classmethod
    def _peer_balance_periods(cls, cutoff_date: date) -> tuple[str, ...]:
        periods = tuple(
            cls._shift_month(date(cutoff_date.year, cutoff_date.month, 1), -offset)
            for offset in range(cls._AVERAGE_LOOKBACK_MONTHS + 1)
        )
        return tuple(f"{period:%Y%m%d}" for period in sorted(periods))

    @classmethod
    def _peer_income_periods(cls, cutoff_date: date) -> tuple[str, ...]:
        return tuple(part for part in cls._result_periods(cutoff_date).split(",") if part)

    @classmethod
    def _peer_periods(cls, cutoff_date: date) -> str:
        periods = tuple(
            cls._shift_month(date(cutoff_date.year, cutoff_date.month, 1), -offset)
            for offset in range(cls._COMPARATIVE_LOOKBACK_MONTHS + 1)
        )
        return ",".join(f"{period:%Y%m%d}" for period in sorted(periods))

    @staticmethod
    def _deduplicate(lines: list[FinancialStatementLine]) -> list[FinancialStatementLine]:
        unique: dict[
            tuple[str, date, FinancialStatementType, str, str],
            FinancialStatementLine,
        ] = {}
        for line in lines:
            key = (
                line.entity.entity_id,
                line.statement_date,
                line.statement_type,
                line.account_code,
                line.account_name,
            )
            unique.setdefault(key, line)
        return list(unique.values())

    def _primary_statement_cutoff(
        self,
        lines: list[FinancialStatementLine],
    ) -> date | None:
        if not self._config.api_entity_codes:
            return None
        primary = self._config.api_entity_codes[0]
        balance_dates = {
            line.statement_date
            for line in lines
            if line.entity.entity_id == primary
            and line.statement_type is FinancialStatementType.BALANCE_SHEET
        }
        income_dates = {
            line.statement_date
            for line in lines
            if line.entity.entity_id == primary
            and line.statement_type is FinancialStatementType.INCOME_STATEMENT
        }
        common_dates = balance_dates & income_dates
        return max(common_dates) if common_dates else None

    def _clip_to_primary_statement_cutoff(
        self,
        lines: list[FinancialStatementLine],
    ) -> list[FinancialStatementLine]:
        """Evita que un indicador más reciente desplace el corte contable válido."""

        effective_cutoff = self._primary_statement_cutoff(lines)
        if effective_cutoff is None:
            return lines
        return [line for line in lines if line.statement_date <= effective_cutoff]
