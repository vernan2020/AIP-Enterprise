from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal, DivisionByZero, InvalidOperation

from aip.domain.financial_analysis.models import (
    FinancialMetricHistorySeries,
    FinancialStatementLine,
)
from aip.product.configured.services.configured_financial_analysis_service import (
    ConfiguredFinancialAnalysisService,
    FinancialAnalysisApplicationSnapshot,
)
from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.ui.modules.financial_analysis.viewmodels.financial_analysis_view_model import (
    FinancialAccountCatalogRow,
    FinancialAnalysisViewModel,
    FinancialEntityComparisonSeriesView,
    FinancialEntityComparisonViewModel,
    FinancialMetricHistoryPointView,
    FinancialMetricHistorySeriesView,
    FinancialMetricView,
    FinancialStatementRow,
    IndicatorReconciliationRow,
    PeerChartPointView,
    PeerChartSeriesView,
    PeerRatingRow,
    PeerSummaryRow,
    RatingDimensionRow,
    RatingIndicatorRow,
)


class FinancialAnalysisPresenter:
    """Adapta el caso de uso SUGEF sin ejecutar cálculos financieros en la UI."""

    _BINARY_CODES = {"PROPORTIONAL_SUPERVISION", "STATE_GUARANTEE"}

    def __init__(self, application_factory: DemoApplicationFactory | None = None) -> None:
        self._factory = application_factory or DemoApplicationFactory()

    def build_view_model(
        self,
        *,
        selected_entity_id: str | None = None,
        force_refresh: bool = False,
    ) -> FinancialAnalysisViewModel:
        try:
            service = self._factory.container.resolve(ConfiguredFinancialAnalysisService)
            snapshot = service.load(
                selected_entity_id=selected_entity_id,
                force_refresh=force_refresh,
            )
        except Exception as exc:
            return FinancialAnalysisViewModel(
                diagnostics=(f"Módulo SUGEF no disponible: {type(exc).__name__}: {exc}",)
            )
        return self._from_snapshot(snapshot)

    def build_comparison_view_model(
        self,
        *,
        entity_ids: tuple[str, ...],
        series_code: str,
        horizon: str = "36M",
        custom_from: date | None = None,
        custom_to: date | None = None,
    ) -> FinancialEntityComparisonViewModel:
        unique_ids = tuple(dict.fromkeys(item for item in entity_ids if item))
        if not unique_ids:
            return FinancialEntityComparisonViewModel(
                series_code=series_code,
                diagnostics=("Seleccione al menos una entidad.",),
            )
        if len(unique_ids) > 5:
            return FinancialEntityComparisonViewModel(
                series_code=series_code,
                diagnostics=("El comparativo admite un máximo de 5 entidades.",),
            )

        try:
            service = self._factory.container.resolve(ConfiguredFinancialAnalysisService)
            display_start, display_end, lookback_months = self._comparison_window(
                horizon=horizon,
                custom_from=custom_from,
                custom_to=custom_to,
            )
            snapshots = service.load_comparison(
                entity_ids=unique_ids,
                cutoff_date=display_end,
                lookback_months=lookback_months,
            )
        except Exception as exc:
            return FinancialEntityComparisonViewModel(
                series_code=series_code,
                diagnostics=(f"Comparativo SUGEF no disponible: {type(exc).__name__}: {exc}",),
            )

        series_views: list[FinancialEntityComparisonSeriesView] = []
        label = ""
        unit = ""
        diagnostics: list[str] = []

        for snapshot in snapshots:
            entity = snapshot.selected_entity
            if entity is None:
                continue
            candidate = next(
                (
                    item
                    for item in (*snapshot.metric_history, *snapshot.statement_history)
                    if item.code == series_code
                ),
                None,
            )
            if candidate is None:
                diagnostics.append(
                    f"{entity.name}: serie no disponible para el corte seleccionado."
                )
                continue

            mapped = self._history_series(candidate)
            mapped = replace(
                mapped,
                points=tuple(
                    point
                    for point in mapped.points
                    if self._point_in_window(
                        point.iso_date,
                        start=display_start,
                        end=display_end,
                    )
                ),
            )
            mapped = replace(
                mapped,
                available_points=sum(point.value is not None for point in mapped.points),
                total_points=len(mapped.points),
            )
            if unit and mapped.unit != unit:
                diagnostics.append(
                    f"{entity.name}: unidad incompatible ({mapped.unit}); serie omitida."
                )
                continue
            label = label or candidate.label
            unit = unit or mapped.unit
            series_views.append(
                FinancialEntityComparisonSeriesView(
                    entity_id=entity.entity_id,
                    entity_name=entity.name,
                    unit=mapped.unit,
                    latest_value=mapped.latest_value,
                    available_points=mapped.available_points,
                    total_points=mapped.total_points,
                    points=mapped.points,
                )
            )

        return FinancialEntityComparisonViewModel(
            series_code=series_code,
            label=label,
            unit=unit,
            entities=tuple(series_views),
            diagnostics=tuple(diagnostics),
        )

    @staticmethod
    def _comparison_window(
        *,
        horizon: str,
        custom_from: date | None,
        custom_to: date | None,
    ) -> tuple[date | None, date | None, int | None]:
        normalized = horizon.strip().upper()
        months = {
            "12M": 12,
            "24M": 24,
            "36M": 36,
            "5Y": 60,
        }.get(normalized)
        if normalized == "ALL":
            return None, custom_to, None
        if normalized == "CUSTOM":
            if custom_from is None or custom_to is None:
                raise ValueError("El horizonte personalizado requiere Desde y Hasta.")
            if custom_from > custom_to:
                raise ValueError("Desde no puede ser posterior a Hasta.")
            display_start = date(custom_from.year, custom_from.month, 1)
            display_end = date(
                custom_to.year,
                custom_to.month,
                monthrange(custom_to.year, custom_to.month)[1],
            )
            month_span = (
                (display_end.year - display_start.year) * 12
                + display_end.month
                - display_start.month
                + 1
            )
            return display_start, display_end, month_span + 11

        if months is None:
            raise ValueError(f"Horizonte no reconocido: {horizon}")
        end = custom_to
        if end is None:
            # El servicio resolverá el corte vigente. El filtro inferior se
            # calcula después sobre cada serie para conservar exactamente N meses.
            return None, None, months + 11
        end = date(end.year, end.month, monthrange(end.year, end.month)[1])
        month_index = end.year * 12 + end.month - months
        start_year, zero_based_month = divmod(month_index, 12)
        return date(start_year, zero_based_month + 1, 1), end, months + 11

    @staticmethod
    def _point_in_window(
        iso_date: str,
        *,
        start: date | None,
        end: date | None,
    ) -> bool:
        point_date = date.fromisoformat(iso_date)
        if start is not None and point_date < start:
            return False
        if end is not None and point_date > end:
            return False
        return True

    @classmethod
    def _from_snapshot(
        cls, snapshot: FinancialAnalysisApplicationSnapshot
    ) -> FinancialAnalysisViewModel:
        metrics = tuple(
            FinancialMetricView(
                code=item.code,
                label=item.label,
                value=cls._metric_value(item.value, item.unit),
                change=cls._change(item.change_percent),
                source_account=item.source_account or "Cuenta no identificada",
            )
            for item in snapshot.metrics
        )
        metric_history = tuple(cls._history_series(item) for item in snapshot.metric_history)
        statement_history = tuple(cls._history_series(item) for item in snapshot.statement_history)
        account_catalog_rows = cls._account_catalog_rows(snapshot)
        statements = tuple(
            FinancialStatementRow(
                statement=cls._statement_label(item.statement_type.value),
                account_code=item.account_code,
                account_name=item.account_name,
                amount=cls._statement_value(
                    item.amount,
                    item.statement_type.value,
                    item.account_code,
                ),
                currency=item.currency,
                trace=(
                    f"{item.trace.file_path} · {item.trace.sheet_name} · fila {item.trace.row_number}"
                    if item.trace is not None
                    else "-"
                ),
                history_code=(
                    f"SUGEF::{item.statement_type.value}::{item.account_code}"
                    if item.account_code
                    else ""
                ),
            )
            for item in snapshot.statement_lines
        )
        peers = tuple(
            PeerSummaryRow(
                entity_id=item.entity.entity_id,
                entity_name=item.entity.name,
                category=item.entity.category,
                assets=cls._money(item.assets),
                loans=cls._money(item.loans),
                equity=cls._money(item.equity),
                net_income=cls._money(item.net_income),
                roa=cls._percent(item.roa_percent),
                roe=cls._percent(item.roe_percent),
            )
            for item in snapshot.peer_summaries
        )
        selected = snapshot.selected_entity
        selected_id = selected.entity_id if selected is not None else ""
        peer_chart_series = cls._peer_chart_series(snapshot, selected_id=selected_id)
        peer_rating_rows: list[PeerRatingRow] = []
        emitted_position = 0
        for item in snapshot.peer_ratings:
            complete = item.status == "COMPLETE" and item.score is not None
            if complete:
                emitted_position += 1
            peer_rating_rows.append(
                PeerRatingRow(
                    position=str(emitted_position) if complete else "N/D",
                    entity_id=item.entity.entity_id,
                    entity_name=item.entity.name,
                    category=item.entity.category,
                    score=f"{item.score:,.3f}" if item.score is not None else "-",
                    grade=item.grade or "Sin emitir",
                    coverage=f"{item.coverage_percent:,.2f}%",
                    indicators=f"{item.available_indicators}/{item.total_indicators}",
                    status="Emitida" if complete else "Incompleta",
                    selected=item.entity.entity_id == selected_id,
                )
            )
        rating = snapshot.rating
        rating_dimensions = (
            tuple(
                RatingDimensionRow(
                    name=item.name,
                    score=f"{item.score:,.3f}",
                    weight=f"{item.weight_percent:,.2f}%",
                    coverage=f"{item.available_indicators}/{item.total_indicators}",
                )
                for item in rating.dimensions
            )
            if rating is not None
            else ()
        )
        rating_indicators = (
            tuple(
                RatingIndicatorRow(
                    indicator=item.label,
                    dimension=item.dimension,
                    value=cls._rating_value(item.value, item.direction.value),
                    peer_count=(
                        "N/A" if item.direction.value == "BINARY" else str(item.peer_count)
                    ),
                    percentile_15=cls._rating_value(item.percentile_15, item.direction.value),
                    midpoint=cls._rating_value(item.midpoint, item.direction.value),
                    percentile_85=cls._rating_value(item.percentile_85, item.direction.value),
                    direction=cls._direction_label(item.direction.value),
                    level=cls._level_label(item.level.value),
                    contribution=(
                        f"{item.contribution:,.3f}" if item.contribution is not None else "-"
                    ),
                    source_account=item.source_account or "Cuenta no identificada",
                )
                for item in rating.indicators
            )
            if rating is not None
            else ()
        )
        reconciliations = tuple(
            IndicatorReconciliationRow(
                indicator=item.label,
                published_value=cls._reconciliation_value(item.published_value, item.code),
                calculated_value=cls._reconciliation_value(item.calculated_value, item.code),
                difference=cls._reconciliation_difference(item.difference, item.code),
                status=cls._reconciliation_status(item.status.value),
                published_source=item.published_source or "-",
                calculated_source=item.calculated_source or "-",
            )
            for item in snapshot.indicator_reconciliations
        )
        source_cutoff = (
            snapshot.cutoff_date.strftime("%d/%m/%Y")
            if snapshot.cutoff_date is not None and snapshot.available_dates
            else "No disponible"
        )
        return FinancialAnalysisViewModel(
            status=snapshot.status,
            cutoff_date=source_cutoff,
            selected_entity_id=selected_id,
            selected_entity_name=selected.name if selected else "Sin datos",
            entities=tuple((item.entity_id, item.name) for item in snapshot.entities),
            metrics=metrics,
            metric_history=metric_history,
            statement_history=statement_history,
            statement_rows=statements,
            account_catalog_rows=account_catalog_rows,
            peer_rows=peers,
            peer_chart_series=peer_chart_series,
            peer_rating_rows=tuple(peer_rating_rows),
            rating_status=rating.status if rating is not None else "INCOMPLETE",
            rating_score=(f"{rating.score:,.3f}" if rating and rating.score is not None else "-"),
            rating_grade=rating.grade if rating and rating.grade else "Sin emitir",
            rating_coverage=(f"{rating.coverage_percent:,.2f}%" if rating is not None else "0.00%"),
            rating_methodology=(
                f"{rating.methodology_code} · {rating.methodology_version}"
                if rating is not None
                else "08ME14-01"
            ),
            rating_dimensions=rating_dimensions,
            rating_indicators=rating_indicators,
            indicator_reconciliations=reconciliations,
            rating_diagnostics=rating.diagnostics if rating is not None else (),
            diagnostics=snapshot.diagnostics,
            source_name=snapshot.source_name,
            source_url=snapshot.source_url,
            source_file_count=len(snapshot.source_files),
        )

    @classmethod
    def _account_catalog_rows(
        cls,
        snapshot: FinancialAnalysisApplicationSnapshot,
    ) -> tuple[FinancialAccountCatalogRow, ...]:
        by_code: dict[str, list[FinancialStatementLine]] = {}
        for line in snapshot.statement_lines:
            code = line.account_code.strip().removesuffix(".0")
            if code:
                by_code.setdefault(code, []).append(line)

        rows: list[FinancialAccountCatalogRow] = []
        for entry in snapshot.account_catalog:
            code = entry.account_code.strip().removesuffix(".0")
            matches = by_code.get(code, [])
            balance = "N/D"
            currency = "-"
            balance_status = "Sin saldo publicado"
            history_code = ""

            if len(matches) == 1:
                line = matches[0]
                balance = cls._statement_value(
                    line.amount,
                    line.statement_type.value,
                    line.account_code,
                )
                currency = line.currency
                balance_status = "Disponible"
                history_code = (
                    f"SUGEF::{line.statement_type.value}::{line.account_code}"
                    if line.account_code
                    else ""
                )
            elif len(matches) > 1:
                distinct = {
                    (line.statement_type.value, line.amount, line.currency) for line in matches
                }
                if len(distinct) == 1:
                    line = matches[0]
                    balance = cls._statement_value(
                        line.amount,
                        line.statement_type.value,
                        line.account_code,
                    )
                    currency = line.currency
                    balance_status = "Disponible"
                    history_code = (
                        f"SUGEF::{line.statement_type.value}::{line.account_code}"
                        if line.account_code
                        else ""
                    )
                else:
                    balance_status = "Coincidencia múltiple"

            rows.append(
                FinancialAccountCatalogRow(
                    account_code=entry.account_code,
                    account_name=entry.account_name,
                    catalog_type_code=entry.catalog_type_code,
                    catalog_type_name=entry.catalog_type_name,
                    level=("-" if entry.level is None else f"{entry.level.normalize()}"),
                    parent_account_code=entry.parent_account_code or "-",
                    sign=("-" if entry.sign is None else str(entry.sign)),
                    balance=balance,
                    currency=currency,
                    balance_status=balance_status,
                    history_code=history_code,
                )
            )

        return tuple(
            sorted(
                rows,
                key=lambda item: (
                    item.catalog_type_code,
                    item.account_code,
                    item.account_name.casefold(),
                ),
            )
        )

    @classmethod
    def _peer_chart_series(
        cls,
        snapshot: FinancialAnalysisApplicationSnapshot,
        *,
        selected_id: str,
    ) -> tuple[PeerChartSeriesView, ...]:
        definitions = (
            ("PEER_ASSETS", "Activos por entidad", "₡ MM", "assets", "MONEY"),
            ("PEER_LOANS", "Cartera por entidad", "₡ MM", "loans", "MONEY"),
            ("PEER_LIABILITIES", "Pasivos por entidad", "₡ MM", "liabilities", "MONEY"),
            ("PEER_EQUITY", "Patrimonio por entidad", "₡ MM", "equity", "MONEY"),
            ("PEER_NET_INCOME", "Resultado neto por entidad", "₡ MM", "net_income", "MONEY"),
            ("PEER_ROA", "ROA por entidad", "%", "roa_percent", "PERCENT"),
            ("PEER_ROE", "ROE por entidad", "%", "roe_percent", "PERCENT"),
        )
        output: list[PeerChartSeriesView] = []
        for code, label, unit, attribute, value_kind in definitions:
            points: list[PeerChartPointView] = []
            for item in snapshot.peer_summaries:
                raw_value = getattr(item, attribute)
                if raw_value is None:
                    continue
                chart_value = (
                    float(raw_value / Decimal("1000000"))
                    if value_kind == "MONEY"
                    else float(raw_value)
                )
                points.append(
                    PeerChartPointView(
                        entity_id=item.entity.entity_id,
                        entity_name=item.entity.name,
                        value=chart_value,
                        display_value=(
                            cls._money(raw_value)
                            if value_kind == "MONEY"
                            else cls._percent(raw_value)
                        ),
                        selected=item.entity.entity_id == selected_id,
                    )
                )
            if points:
                output.append(
                    PeerChartSeriesView(
                        code=code,
                        label=label,
                        unit=unit,
                        chart_type="BAR",
                        points=tuple(points),
                    )
                )
        for series in snapshot.market_composition:
            output.append(
                PeerChartSeriesView(
                    code=series.code,
                    label=series.label,
                    unit="%",
                    chart_type="PIE",
                    points=tuple(
                        PeerChartPointView(
                            entity_id=point.entity.entity_id,
                            entity_name=point.entity.name,
                            value=float(point.share_percent),
                            display_value=f"{point.share_percent:,.2f}%",
                            selected=point.entity.entity_id == selected_id,
                        )
                        for point in series.points
                    ),
                )
            )
        return tuple(output)

    @classmethod
    def _history_series(
        cls,
        series: FinancialMetricHistorySeries,
    ) -> FinancialMetricHistorySeriesView:
        points = tuple(
            FinancialMetricHistoryPointView(
                iso_date=point.statement_date.isoformat(),
                date_label=point.statement_date.strftime("%m/%Y"),
                value=cls._chart_value(point.value, series.unit),
                display_value=cls._metric_value(point.value, series.unit),
            )
            for point in series.points
        )
        available = tuple(point for point in series.points if point.value is not None)
        latest = available[-1].value if available else None
        period_change = cls._history_change(
            available[0].value if len(available) >= 2 else None,
            latest if len(available) >= 2 else None,
            series.unit,
        )
        if series.unit == "PERCENT":
            display_unit = "%"
        elif series.unit == "NUMBER":
            display_unit = "Valor"
        else:
            display_unit = (
                "₡ MM" if series.unit == "CRC" else (f"{series.unit} MM" if series.unit else "MM")
            )
        return FinancialMetricHistorySeriesView(
            code=series.code,
            label=series.label,
            unit=display_unit,
            latest_value=cls._metric_value(latest, series.unit),
            period_change=period_change,
            source_account=series.source_account or "Cuenta no identificada",
            available_points=len(available),
            total_points=len(series.points),
            points=points,
        )

    @staticmethod
    def _chart_value(value: Decimal | None, unit: str) -> float | None:
        if value is None:
            return None
        scaled = value if unit in {"PERCENT", "NUMBER"} else value / Decimal("1000000")
        return float(scaled)

    @staticmethod
    def _history_change(
        first: Decimal | None,
        latest: Decimal | None,
        unit: str,
    ) -> str:
        if first is None or latest is None:
            return "Sin comparación en la ventana"
        if unit == "PERCENT":
            difference = latest - first
            sign = "+" if difference > 0 else ""
            return f"{sign}{difference:,.2f} pp en la ventana"
        if unit == "NUMBER":
            return "Serie discreta"
        if first == Decimal("0"):
            return "Sin comparación en la ventana"
        try:
            change = (latest / first - Decimal("1")) * Decimal("100")
        except (DivisionByZero, InvalidOperation):
            return "Sin comparación en la ventana"
        sign = "+" if change > 0 else ""
        return f"{sign}{change:,.2f}% en la ventana"

    @staticmethod
    def _money(value: Decimal | None) -> str:
        if value is None:
            return "-"
        return f"₡{value / Decimal('1000000'):,.2f} MM"

    @classmethod
    def _statement_value(cls, value: Decimal, statement_type: str, account_code: str) -> str:
        if statement_type != "INDICATORS":
            return cls._money(value)
        normalized_code = account_code.removeprefix("CALC:")
        if normalized_code in cls._BINARY_CODES:
            return "Sí" if value == Decimal("1") else "No"
        return f"{value * Decimal('100'):,.3f}%"

    @staticmethod
    def _percent(value: Decimal | None) -> str:
        return "-" if value is None else f"{value:,.2f}%"

    @classmethod
    def _metric_value(cls, value: Decimal | None, unit: str) -> str:
        if value is None:
            return "-"
        if unit == "PERCENT":
            return cls._percent(value)
        if unit == "NUMBER":
            return f"{value:,.3f}"
        return cls._money(value)

    @staticmethod
    def _change(value: Decimal | None) -> str:
        if value is None:
            return "Sin período comparable"
        sign = "+" if value > 0 else ""
        return f"{sign}{value:,.2f}% vs. período anterior"

    @staticmethod
    def _statement_label(value: str) -> str:
        return {
            "BALANCE_SHEET": "Balance de situación",
            "INCOME_STATEMENT": "Estado de resultados",
            "INDICATORS": "Indicadores financieros",
            "TRIAL_BALANCE": "Balanza de comprobación",
            "UNKNOWN": "Estado financiero",
        }.get(value, value)

    @staticmethod
    def _rating_value(value: Decimal | None, direction: str) -> str:
        if value is None:
            return "-"
        if direction == "BINARY":
            return "Sí (1)" if value == Decimal("1") else "No (0)"
        return f"{value * Decimal('100'):,.3f}%"

    @classmethod
    def _reconciliation_value(cls, value: Decimal | None, code: str) -> str:
        if value is None:
            return "-"
        if code in cls._BINARY_CODES:
            return "Sí (1)" if value == Decimal("1") else "No (0)"
        return f"{value * Decimal('100'):,.3f}%"

    @classmethod
    def _reconciliation_difference(cls, value: Decimal | None, code: str) -> str:
        if value is None:
            return "-"
        if code in cls._BINARY_CODES:
            return f"{value:,.0f}"
        sign = "+" if value > 0 else ""
        return f"{sign}{value * Decimal('100'):,.3f} pp"

    @staticmethod
    def _reconciliation_status(value: str) -> str:
        return {
            "MATCH": "Coincide",
            "TOLERANCE": "Dentro de tolerancia",
            "MISMATCH": "Diferencia",
            "PUBLISHED_ONLY": "Solo SUGEF",
            "CALCULATED_ONLY": "Solo AIP",
            "MISSING_INPUT": "Sin insumos",
        }.get(value, value)

    @staticmethod
    def _direction_label(value: str) -> str:
        return {
            "HIGHER_IS_BETTER": "Mayor es mejor",
            "LOWER_IS_BETTER": "Menor es mejor",
            "BINARY": "Binario 1/0",
        }.get(value, value)

    @staticmethod
    def _level_label(value: str) -> str:
        return {
            "OUTSTANDING": "Sobresaliente",
            "SATISFACTORY": "Satisfactorio",
            "IMPROVABLE": "Mejorable",
            "CRITICAL": "Crítico",
            "UNAVAILABLE": "Sin datos",
        }.get(value, value)
