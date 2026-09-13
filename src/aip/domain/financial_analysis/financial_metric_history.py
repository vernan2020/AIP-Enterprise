from __future__ import annotations

from calendar import monthrange
from datetime import date

from aip.domain.financial_analysis.models import (
    FinancialMetricHistoryPoint,
    FinancialMetricHistorySeries,
    FinancialStatementLine,
)
from aip.domain.financial_analysis.return_on_assets import ReturnOnAssetsService
from aip.domain.financial_analysis.services import FinancialAnalysisService


class FinancialMetricHistoryService:
    """Build monthly headline-KPI series from official financial statement lines."""

    DEFAULT_MONTHS = 12
    _DEFINITIONS = (
        ("ASSETS", "Activos", "CRC"),
        ("LOANS", "Cartera de crédito", "CRC"),
        ("LIABILITIES", "Pasivos", "CRC"),
        ("EQUITY", "Patrimonio", "CRC"),
        ("NET_INCOME", "Resultado neto", "CRC"),
        ("ROA", "ROA", "PERCENT"),
        ("ROE", "ROE", "PERCENT"),
    )

    def __init__(
        self,
        analysis_service: FinancialAnalysisService | None = None,
        roa_service: ReturnOnAssetsService | None = None,
    ) -> None:
        self._analysis = analysis_service or FinancialAnalysisService()
        self._roa = roa_service or ReturnOnAssetsService()

    def build(
        self,
        lines: tuple[FinancialStatementLine, ...],
        *,
        entity_id: str,
        cutoff_date: date,
        months: int = DEFAULT_MONTHS,
    ) -> tuple[FinancialMetricHistorySeries, ...]:
        if months < 1:
            raise ValueError("months must be at least 1")

        dates = self._monthly_cutoffs(cutoff_date, months)
        values: dict[str, list[FinancialMetricHistoryPoint]] = {
            code: [] for code, _label, _unit in self._DEFINITIONS
        }
        sources: dict[str, str | None] = {code: None for code in values}
        sources["ROA"] = ReturnOnAssetsService.SOURCE_ACCOUNT

        for statement_date in dates:
            metrics = {
                item.code: item
                for item in self._analysis.metrics_for_period(
                    lines,
                    entity_id=entity_id,
                    statement_date=statement_date,
                )
            }
            roa = self._roa.calculate(
                lines,
                entity_id=entity_id,
                cutoff_date=statement_date,
            )
            for code in values:
                if code == "ROA":
                    value = roa.value_percent
                    source_account = roa.source_account
                else:
                    metric = metrics.get(code)
                    value = metric.value if metric is not None else None
                    source_account = metric.source_account if metric is not None else None
                values[code].append(
                    FinancialMetricHistoryPoint(
                        statement_date=statement_date,
                        value=value,
                    )
                )
                if source_account and (value is not None or code == "ROA"):
                    sources[code] = source_account

        return tuple(
            FinancialMetricHistorySeries(
                code=code,
                label=label,
                unit=unit,
                points=tuple(values[code]),
                source_account=sources[code],
            )
            for code, label, unit in self._DEFINITIONS
        )

    @classmethod
    def _monthly_cutoffs(cls, cutoff_date: date, months: int) -> tuple[date, ...]:
        month_start = date(cutoff_date.year, cutoff_date.month, 1)
        starts = tuple(cls._shift_month(month_start, -offset) for offset in reversed(range(months)))
        return tuple(
            date(value.year, value.month, monthrange(value.year, value.month)[1])
            for value in starts
        )

    @staticmethod
    def _shift_month(value: date, offset: int) -> date:
        month_index = value.year * 12 + value.month - 1 + offset
        year, zero_based_month = divmod(month_index, 12)
        return date(year, zero_based_month + 1, 1)
