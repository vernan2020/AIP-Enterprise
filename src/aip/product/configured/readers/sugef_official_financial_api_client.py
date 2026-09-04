from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

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

    Balance y resultados se descargan para las entidades configuradas, incluyendo
    la historia mínima necesaria para 08ME14-01. Los indicadores se solicitan una
    sola vez con ``codigoEntidad`` vacío, modalidad documentada por SUGEF para
    retornar todas las entidades del Sistema Financiero Nacional. De esta forma
    los percentiles P15/P85 se construyen exclusivamente con información pública
    oficial y no requieren matrices institucionales de respaldo.
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

        # El manual oficial SUGEF establece que codigoEntidad="" devuelve todas
        # las entidades del SFN para ReporteIndicadoresFinancierosEntidad.
        jobs.append(
            (
                "",
                self._period_range(
                    cutoff_date,
                    lookback_months=self._COMPARATIVE_LOOKBACK_MONTHS,
                ),
                *self._INDICATOR_REPORT,
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
                ): (entity_code, report_name, statement_type)
                for entity_code, period, report_name, list_key, statement_type in jobs
            }
            for future in as_completed(futures):
                entity_code, report_name, statement_type = futures[future]
                try:
                    report_lines, endpoint = future.result()
                    lines.extend(report_lines)
                    endpoints.add(endpoint)
                except Exception as exc:  # boundary: convert source failure to diagnostics
                    scope = entity_code or "SFN completo"
                    diagnostics.append(
                        f"SUGEF API {report_name} ({scope}): "
                        f"{type(exc).__name__}: {exc}"
                    )

        lines = self._clip_to_primary_statement_cutoff(lines)
        if lines:
            latest_date = max(line.statement_date for line in lines)
            diagnostics.extend(
                (
                    "Balance y Estado de Resultados consultados exclusivamente en la API pública oficial de SUGEF.",
                    "Indicadores comparativos consultados para todas las entidades del Sistema Financiero Nacional mediante la modalidad oficial codigoEntidad vacío.",
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
