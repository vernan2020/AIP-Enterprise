from __future__ import annotations

from datetime import date
from threading import RLock

from aip.domain.financial_analysis.models import FinancialAnalysisSnapshot
from aip.domain.financial_analysis.services import FinancialAnalysisService
from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.context.valuation_date_context import ValuationDateContext
from aip.product.configured.readers.sugef_financial_statement_reader import (
    SUGEFFinancialReadResult,
    SUGEFFinancialStatementReader,
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
    ) -> None:
        self._config = config
        self._valuation_date_context = valuation_date_context
        self._reader = reader or SUGEFFinancialStatementReader(config)
        self._analysis = analysis_service or FinancialAnalysisService()
        self._cached_results: dict[date, SUGEFFinancialReadResult] = {}
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
        return self._analysis.build_snapshot(
            result.lines,
            selected_entity_id=selected_entity_id,
            cutoff_date=requested_date,
            diagnostics=result.diagnostics,
            source_files=result.source_files,
        )

    def _read(
        self, *, cutoff_date: date, force_refresh: bool
    ) -> SUGEFFinancialReadResult:
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
