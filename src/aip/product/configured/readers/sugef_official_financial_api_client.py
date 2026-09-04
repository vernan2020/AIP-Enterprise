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

    Para las entidades configuradas descarga la historia mínima requerida por
    08ME14-01. Además consulta el corte comparativo del SFN con ``codigoEntidad``
    vacío para Balance, Resultados e Indicadores, modalidad documentada por SUGEF.
    Así la pantalla de pares y los percentiles P15/P85 se construyen únicamente
    con información pública oficial, sin matrices institucionales de respaldo.
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
        jobs: list[tuple[str, str, str, str, FinancialStatementType]] = []
        for entity_code in self._config.api_entity_codes:
            jobs.append(
                (
                    entity_code,
                    self._period_range(
                        cutoff_date,
                        lookback_months=self._AVERAGE_LOOKBACK_MONTHS,
                    ),
                    *self._BALANCE_REPORT,
                )
            )
            jobs.append(
                (
                    entity_code,
                    self._result_periods(cutoff_date),
                    *self._INCOME_REPORT,
                )
            )

        peer_periods = self._peer_periods(cutoff_date)
        # El manual oficial SUGEF establece que codigoEntidad="" devuelve todas
        # las entidades del SFN para estos tres reportes por entidad financiera.
        jobs.extend(
            (
                ("", peer_periods, *self._BALANCE_REPORT),
                ("", peer_periods, *self._INCOME_REPORT),
                ("", peer_periods, *self._INDICATOR_REPORT),
            )
        )

        lines: list[FinancialStatementLine] = []
        endpoints: set[str] = set()
        diagnostics: list[str] = []
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

        lines = self._deduplicate(lines)
        lines = self._clip_to_primary_statement_cutoff(lines)
        if lines:
            latest_date = max(line.statement_date for line in lines)
            diagnostics.extend(
                (
                    "Balance y Estado de Resultados consultados exclusivamente en la API pública oficial de SUGEF.",
                    "Balance, Resultados e Indicadores comparativos consultados para todas las entidades del Sistema Financiero Nacional mediante la modalidad oficial codigoEntidad vacío.",
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
            unique[key] = line
        return list(unique.values())

    def _clip_to_primary_statement_cutoff(
        self,
        lines: list[FinancialStatementLine],
    ) -> list[FinancialStatementLine]:
        """Evita que un indicador más reciente desplace el corte contable válido."""

        if not self._config.api_entity_codes:
            return lines
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
        if not common_dates:
            return lines
        effective_cutoff = max(common_dates)
        return [line for line in lines if line.statement_date <= effective_cutoff]
