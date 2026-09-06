from __future__ import annotations

from dataclasses import replace
from datetime import date
from threading import RLock

from aip.domain.financial_analysis.financial_metric_history import (
    FinancialMetricHistoryService,
)
from aip.domain.financial_analysis.models import FinancialAnalysisSnapshot, FinancialMetric
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
            history = self._history.build(
                combined_lines,
                entity_id=entity_id,
                cutoff_date=snapshot.cutoff_date,
            )
            # El universo comparativo se descarga de forma deliberadamente acotada a
            # las cuentas requeridas por 08ME14-01. Para una entidad seleccionada,
            # el lector histórico sí aporta sus estados completos. El histórico solo
            # debe completar KPI faltantes; nunca desplaza un valor ya resuelto por el
            # snapshot principal (por ejemplo, ROA/ROE publicados por SUGEF).
            enriched_metrics = self._analysis.metrics_for_period(
                combined_lines,
                entity_id=entity_id,
                statement_date=snapshot.cutoff_date,
            )
            metrics = self._merge_headline_metrics(snapshot.metrics, enriched_metrics)
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
    def _merge_headline_metrics(
        primary: tuple[FinancialMetric, ...],
        enriched: tuple[FinancialMetric, ...],
    ) -> tuple[FinancialMetric, ...]:
        """Fill primary N/D metrics without overriding already resolved values."""

        enriched_by_code = {metric.code: metric for metric in enriched}
        merged: list[FinancialMetric] = []
        seen: set[str] = set()

        for metric in primary:
            candidate = enriched_by_code.get(metric.code)
            seen.add(metric.code)
            if candidate is None:
                merged.append(metric)
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
