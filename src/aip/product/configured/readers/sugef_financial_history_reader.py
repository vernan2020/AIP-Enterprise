from __future__ import annotations

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


class SUGEFFinancialHistoryReader(SUGEFFinancialApiClient):
    """Read bounded monthly financial history for one SUGEF entity.

    The UI exposes 12 monthly KPI observations. ROA requires both a 12-month
    rolling average of total assets and trailing-12-month annualized final income
    for every displayed point. The earliest displayed point therefore needs the
    same month of the prior year, so the reader retrieves 24 months of support
    history. History remains entity-scoped; missing months are never converted
    to zero.
    """

    DISPLAY_HISTORY_MONTHS = 12
    SUPPORT_HISTORY_MONTHS = DISPLAY_HISTORY_MONTHS + 12
    _HISTORY_REPORTS = (
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

    def __init__(self, config: SUGEFFinancialSourceConfig) -> None:
        super().__init__(config)

    def read_entity_history(
        self,
        entity_id: str,
        cutoff_date: date,
    ) -> SUGEFApiReadResult:
        return self.read_entity_history_range(
            entity_id,
            cutoff_date,
            lookback_months=self.SUPPORT_HISTORY_MONTHS - 1,
        )

    def read_entity_history_range(
        self,
        entity_id: str,
        cutoff_date: date,
        *,
        lookback_months: int | None,
    ) -> SUGEFApiReadResult:
        if not self._config.api_enabled:
            return SUGEFApiReadResult(
                (),
                (),
                ("Histórico KPI SUGEF no consultado: API pública deshabilitada.",),
            )
        if not entity_id.strip():
            return SUGEFApiReadResult((), (), ("Histórico KPI SUGEF: entidad no definida.",))

        if lookback_months is None:
            # Solicita un rango suficientemente amplio para recuperar toda la
            # historia que la API pública mantenga disponible. Solo se conservan
            # observaciones efectivamente publicadas por SUGEF.
            month_index = 1995 * 12
            start_year, zero_based_month = divmod(month_index, 12)
            start = date(start_year, zero_based_month + 1, 1)
            end = date(cutoff_date.year, cutoff_date.month, 1)
            period = f"{start:%Y%m%d}-{end:%Y%m%d}"
            window_label = "toda la historia disponible"
        else:
            period = self._period_range(
                cutoff_date,
                lookback_months=max(0, lookback_months),
            )
            window_label = f"{lookback_months + 1} meses"
        lines: list[FinancialStatementLine] = []
        endpoints: set[str] = set()
        diagnostics: list[str] = []

        for report_name, list_key, statement_type in self._HISTORY_REPORTS:
            try:
                report_lines, endpoint = self._read_report(
                    entity_id,
                    period,
                    report_name,
                    list_key,
                    statement_type,
                )
                lines.extend(report_lines)
                endpoints.add(endpoint)
            except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
                diagnostics.append(
                    f"Histórico KPI SUGEF {report_name} ({entity_id}): "
                    f"{type(exc).__name__}: {exc}"
                )

        bounded = tuple(
            line
            for line in lines
            if line.entity.entity_id == entity_id and line.statement_date <= cutoff_date
        )
        if bounded:
            periods = {line.statement_date for line in bounded}
            diagnostics.append(
                "Histórico KPI SUGEF: consulta acotada a una entidad, "
                f"{len(periods)} cortes mensuales recibidos para {window_label}."
            )
        else:
            diagnostics.append(
                "Histórico KPI SUGEF: no se obtuvieron observaciones mensuales utilizables."
            )

        return SUGEFApiReadResult(
            lines=bounded,
            endpoints=tuple(sorted(endpoints)),
            diagnostics=tuple(diagnostics),
        )
