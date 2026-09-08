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

    The UI exposes 12 monthly KPI observations. ROA requires a 12-month rolling
    average of total assets for every displayed point, so the reader retrieves
    23 months of support history (12 displayed months + 11 prior asset balances).
    History remains entity-scoped; missing months are never converted to zero.
    """

    DISPLAY_HISTORY_MONTHS = 12
    SUPPORT_HISTORY_MONTHS = DISPLAY_HISTORY_MONTHS + 11
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
        if not self._config.api_enabled:
            return SUGEFApiReadResult(
                (),
                (),
                ("Histórico KPI SUGEF no consultado: API pública deshabilitada.",),
            )
        if not entity_id.strip():
            return SUGEFApiReadResult((), (), ("Histórico KPI SUGEF: entidad no definida.",))

        period = self._period_range(
            cutoff_date,
            lookback_months=self.SUPPORT_HISTORY_MONTHS - 1,
        )
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
                f"{len(periods)} cortes mensuales recibidos para una ventana de soporte de "
                f"{self.SUPPORT_HISTORY_MONTHS} meses; la vista mantiene "
                f"{self.DISPLAY_HISTORY_MONTHS} meses."
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
