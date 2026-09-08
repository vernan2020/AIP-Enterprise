from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from threading import RLock

from aip.domain.financial_analysis.financial_metric_history import (
    FinancialMetricHistoryService,
)
from aip.domain.financial_analysis.models import (
    FinancialAnalysisSnapshot,
    FinancialMetric,
    FinancialMetricHistoryPoint,
    FinancialMetricHistorySeries,
)
from aip.domain.financial_analysis.services import FinancialAnalysisService
from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.context.valuation_date_context import ValuationDateContext
from aip.product.configured.readers.sugef_financial_api_client import SUGEFApiReadResult
from aip.product.configured.readers.sugef_financial_history_reader import (
    SUGEFFinancialHistoryReader,
)
from aip.product.configured.readers.sugef_financial_statement_reader import (
    SUGEFFinancialReadResult,
    SUGEFFinancialStatementReader,
)
from aip.product.configured.readers.sugef_official_financial_statement_reader import (
    SUGEFOfficialFinancialStatementReader,
)

FinancialAnalysisApplicationSnapshot = FinancialAnalysisSnapshot


class ConfiguredFinancialAnalysisService:
    """Caso de uso de análisis SUGEF con caché invalidada por cambios de archivo."""

    def __init__(
        self,
        config: SUGEFFinancialSourceConfig,
        valuation_date_context: ValuationDateContext,
        *,
        reader: SUGEFFinancialStatementReader | None = None,
        analysis_service: FinancialAnalysisService | None = None,
        history_reader: SUGEFFinancialHistoryReader | None = None,
        history_service: FinancialMetricHistoryService | None = None,
    ) -> None:
        self._config = config
        self._valuation_date_context = valuation_date_context
        # Runtime productivo: nunca completa saldos/indicadores con la matriz
        # histórica incluida en el paquete. Solo API pública o exportación SUGEF.
        self._reader = reader or SUGEFOfficialFinancialStatementReader(config)
        self._analysis = analysis_service or FinancialAnalysisService()
        self._history_reader = history_reader or SUGEFFinancialHistoryReader(config)
        self._history = history_service or FinancialMetricHistoryService(self._analysis)
        self._cached_results: dict[date, SUGEFFinancialReadResult] = {}
        self._cached_history: dict[tuple[str, date], SUGEFApiReadResult] = {}
        self._lock = RLock()

    def load(
        self,
        *,
        selected_entity_id: str | None = None,
        cutoff_date: date | None = None,
        force_refresh: bool = False,
    ) -> FinancialAnalysisSnapshot:
        requested_date = cutoff_date or self._valuation_date_context.value
        result = self._read(cutoff_date=requested_date, force_refresh=force_refresh)
        snapshot = self._analysis.build_snapshot(
            result.lines,
            selected_entity_id=selected_entity_id,
            cutoff_date=requested_date,
            diagnostics=result.diagnostics,
            source_files=result.source_files,
        )
        if snapshot.selected_entity is None or snapshot.cutoff_date is None:
            return snapshot

        entity_id = snapshot.selected_entity.entity_id
        try:
            history_result = self._read_history(
                entity_id=entity_id,
                cutoff_date=snapshot.cutoff_date,
                force_refresh=force_refresh,
            )
            combined_lines = result.lines + history_result.lines
            raw_history = self._history.build(
                combined_lines,
                entity_id=entity_id,
                cutoff_date=snapshot.cutoff_date,
            )
            # El histórico de la entidad seleccionada completa KPI faltantes y
            # aporta la metodología institucional de ROA. El ROA calculado desde
            # utilidad final anualizada y activos promedio de 12 meses es canónico
            # y reemplaza cualquier ROA publicado o derivado con otra metodología.
            enriched_metrics = self._analysis.metrics_for_period(
                combined_lines,
                entity_id=entity_id,
                statement_date=snapshot.cutoff_date,
            )
            enriched_metrics = self._apply_institutional_roa(
                enriched_metrics,
                raw_history,
                cutoff_date=snapshot.cutoff_date,
            )
            metrics = self._merge_headline_metrics(snapshot.metrics, enriched_metrics)
            history = self._align_history_current_cutoff(
                raw_history,
                metrics,
                cutoff_date=snapshot.cutoff_date,
            )
        except Exception as exc:
            return replace(
                snapshot,
                diagnostics=snapshot.diagnostics
                + (
                    "Histórico KPI SUGEF no disponible; el análisis del corte permanece válido: "
                    f"{type(exc).__name__}: {exc}",
                ),
            )

        return replace(
            snapshot,
            metrics=metrics,
            metric_history=history,
            diagnostics=snapshot.diagnostics + history_result.diagnostics,
        )

    @staticmethod
    def _apply_institutional_roa(
        metrics: tuple[FinancialMetric, ...],
        history: tuple[FinancialMetricHistorySeries, ...],
        *,
        cutoff_date: date,
    ) -> tuple[FinancialMetric, ...]:
        """Replace ROA with the canonical rolling-12-month institutional result."""

        series = next((item for item in history if item.code == "ROA"), None)
        if series is None:
            return metrics

        current_point = next(
            (point for point in series.points if point.statement_date == cutoff_date),
            None,
        )
        previous_point = next(
            (
                point
                for point in sorted(
                    (point for point in series.points if point.statement_date < cutoff_date),
                    key=lambda item: item.statement_date,
                    reverse=True,
                )
            ),
            None,
        )
        current_value = current_point.value if current_point is not None else None
        previous_value = previous_point.value if previous_point is not None else None
        change_percent = None
        if current_value is not None and previous_value not in {None, Decimal("0")}:
            change_percent = (current_value / previous_value - Decimal("1")) * Decimal("100")

        return tuple(
            replace(
                metric,
                value=current_value,
                previous_value=previous_value,
                change_percent=change_percent,
                source_account=series.source_account,
            )
            if metric.code == "ROA"
            else metric
            for metric in metrics
        )

    @staticmethod
    def _merge_headline_metrics(
        primary: tuple[FinancialMetric, ...],
        enriched: tuple[FinancialMetric, ...],
    ) -> tuple[FinancialMetric, ...]:
        """Merge headline metrics while enforcing canonical institutional ROA."""

        enriched_by_code = {metric.code: metric for metric in enriched}
        merged: list[FinancialMetric] = []
        seen: set[str] = set()

        for metric in primary:
            candidate = enriched_by_code.get(metric.code)
            seen.add(metric.code)
            if candidate is None:
                merged.append(metric)
                continue
            if metric.code == "ROA":
                merged.append(candidate)
                continue
            if metric.value is None and candidate.value is not None:
                merged.append(candidate)
                continue
            if metric.value is not None and candidate.value == metric.value:
                merged.append(
                    replace(
                        metric,
                        previous_value=(
                            metric.previous_value
                            if metric.previous_value is not None
                            else candidate.previous_value
                        ),
                        change_percent=(
                            metric.change_percent
                            if metric.change_percent is not None
                            else candidate.change_percent
                        ),
                        source_account=metric.source_account or candidate.source_account,
                    )
                )
                continue
            merged.append(metric)

        merged.extend(metric for metric in enriched if metric.code not in seen)
        return tuple(merged)

    @staticmethod
    def _align_history_current_cutoff(
        history: tuple[FinancialMetricHistorySeries, ...],
        metrics: tuple[FinancialMetric, ...],
        *,
        cutoff_date: date,
    ) -> tuple[FinancialMetricHistorySeries, ...]:
        """Make the current history point equal the canonical headline KPI."""

        current_by_code = {metric.code: metric for metric in metrics if metric.value is not None}
        aligned: list[FinancialMetricHistorySeries] = []
        for series in history:
            metric = current_by_code.get(series.code)
            if metric is None:
                aligned.append(series)
                continue
            points = tuple(
                FinancialMetricHistoryPoint(
                    statement_date=point.statement_date,
                    value=(metric.value if point.statement_date == cutoff_date else point.value),
                )
                for point in series.points
            )
            aligned.append(replace(series, points=points))
        return tuple(aligned)

    def _read(self, *, cutoff_date: date, force_refresh: bool) -> SUGEFFinancialReadResult:
        with self._lock:
            cached = self._cached_results.get(cutoff_date)
            if force_refresh or not self._config.cache_enabled or cached is None:
                result = self._reader.read(cutoff_date=cutoff_date)
                self._cached_results[cutoff_date] = result
                return result
            current_fingerprint = self._reader.fingerprint(cutoff_date=cutoff_date)
            if current_fingerprint != cached.fingerprint:
                cached = self._reader.read(cutoff_date=cutoff_date)
                self._cached_results[cutoff_date] = cached
            return cached

    def _read_history(
        self,
        *,
        entity_id: str,
        cutoff_date: date,
        force_refresh: bool,
    ) -> SUGEFApiReadResult:
        key = (entity_id, cutoff_date)
        with self._lock:
            cached = self._cached_history.get(key)
            if force_refresh or not self._config.cache_enabled or cached is None:
                cached = self._history_reader.read_entity_history(entity_id, cutoff_date)
                self._cached_history[key] = cached
            return cached
