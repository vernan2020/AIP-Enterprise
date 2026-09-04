from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from urllib.error import HTTPError, URLError

from aip.domain.financial_analysis.models import FinancialStatementLine, FinancialStatementType
from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_financial_api_client import (
    SUGEFApiReadResult,
    SUGEFFinancialApiClient,
)


class SUGEFOfficialFinancialApiClient(SUGEFFinancialApiClient):
    """Gateway SUGEF estricto para estados oficiales y universo comparativo SFN.

    La entidad configurada se consulta de forma directa para Balance, Resultados
    e Indicadores. El universo comparativo se consulta con ``codigoEntidad`` vacío,
    pero la historia de Balance se solicita mes a mes y la de Resultados por cada
    período requerido por 08ME14-01. Así se evita depender de una respuesta masiva
    que puede no conservar 12 observaciones por entidad y se mantiene la entidad
    seleccionada disponible aun si una consulta comparativa del SFN falla.
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

    def __init__(self, config: SUGEFFinancialSourceConfig) -> None:
        super().__init__(config)

    def read(self, cutoff_date: date) -> SUGEFApiReadResult:
        lines: list[FinancialStatementLine] = []
        endpoints: set[str] = set()
        diagnostics: list[str] = []

        # Fase 1: estados de las entidades configuradas. Estos estados determinan
        # el último corte contable utilizable antes de consultar indicadores y pares.
        primary_jobs: list[tuple[str, str, str, str, FinancialStatementType]] = []
        for entity_code in self._config.api_entity_codes:
            primary_jobs.append(
                (
                    entity_code,
                    self._period_range(
                        cutoff_date,
                        lookback_months=self._AVERAGE_LOOKBACK_MONTHS,
                    ),
                    *self._BALANCE_REPORT,
                )
            )
            primary_jobs.append(
                (
                    entity_code,
                    self._result_periods(cutoff_date),
                    *self._INCOME_REPORT,
                )
            )
        self._execute_jobs(primary_jobs, lines, endpoints, diagnostics)

        effective_cutoff = self._primary_statement_cutoff(lines)
        if effective_cutoff is not None:
            effective_period = f"{effective_cutoff:%Y%m%d}"

            # Fase 2: indicadores directos de la entidad configurada. No se debe
            # depender de la consulta masiva del SFN para los valores propios.
            primary_indicator_jobs = [
                (entity_code, effective_period, *self._INDICATOR_REPORT)
                for entity_code in self._config.api_entity_codes
            ]
            self._execute_jobs(primary_indicator_jobs, lines, endpoints, diagnostics)

            # Fase 3: universo SFN. Balance se obtiene mes a mes para garantizar
            # 12 observaciones por entidad; Resultados se consulta únicamente para
            # los períodos necesarios para anualización móvil; Indicadores usa el
            # corte contable efectivo exacto.
            peer_jobs: list[tuple[str, str, str, str, FinancialStatementType]] = []
            peer_jobs.extend(
                ("", period, *self._BALANCE_REPORT)
                for period in self._peer_balance_periods(effective_cutoff)
            )
            peer_jobs.extend(
                ("", period, *self._INCOME_REPORT)
                for period in self._peer_income_periods(effective_cutoff)
            )
            peer_jobs.append(("", effective_period, *self._INDICATOR_REPORT))
            self._execute_jobs(peer_jobs, lines, endpoints, diagnostics)

        lines = self._deduplicate(lines)
        lines = self._clip_to_primary_statement_cutoff(lines)
        if lines:
            latest_date = max(line.statement_date for line in lines)
            diagnostics.extend(
                (
                    "Balance y Estado de Resultados consultados exclusivamente en la API pública oficial de SUGEF.",
                    "Indicadores de la entidad seleccionada se consultan directamente en SUGEF; el universo comparativo SFN se consulta mediante codigoEntidad vacío.",
                    "La historia comparativa de Balance se consulta mes a mes y Resultados por los períodos requeridos por 08ME14-01 para preservar 12 observaciones por entidad.",
                    "Último corte SUGEF utilizable en el conjunto oficial: "
                    f"{latest_date.strftime('%d/%m/%Y')}.",
                )
            )
        else:
            diagnostics.append("La API pública de SUGEF no devolvió registros utilizables.")

        return SUGEFApiReadResult(
            lines=tuple(lines),
            endpoints=tuple(sorted(endpoints)),
            diagnostics=tuple(diagnostics),
        )

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
            # Las consultas directas de la entidad se ejecutan antes que las del
            # universo SFN; conservar la primera observación evita que una fila
            # masiva sustituya innecesariamente la trazabilidad directa.
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
