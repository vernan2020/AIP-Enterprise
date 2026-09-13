from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

from aip.product.configured.services.configured_advanced_macro_forecasting_service import (
    ConfiguredAdvancedMacroForecastingService,
)
from aip.product.configured.services.configured_macro_intelligence_service import (
    ConfiguredMacroIntelligenceService,
)
from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.ui.modules.macro_intelligence.viewmodels.macro_intelligence_view_model import (
    MacroEnsembleWeightView,
    MacroForecastLabViewModel,
    MacroForecastPointView,
    MacroModelComparisonView,
    MacroModelMetricView,
    MacroProjectionRow,
    MacroProjectionViewModel,
)


class MacroIntelligencePresenter:
    """Presentation adapter for governed macro projections and forecast analytics."""

    _LABELS = {
        "FX_SELL": "USD / CRC",
        "TPM": "TPM",
        "TBP": "TBP",
        "TRI_CRC_12M": "TRI CRC 12M",
        "TRI_USD_12M": "TRI USD 12M",
        "INFLATION": "Inflación",
        "IMAE": "IMAE",
    }

    def __init__(self, application_factory: DemoApplicationFactory) -> None:
        self._application_factory = application_factory

    @staticmethod
    def _date(value: object) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                return None
        return None

    @staticmethod
    def _float(value: object) -> float:
        try:
            return float(str(value))
        except (TypeError, ValueError):
            return 0.0

    def build_projection(self) -> MacroProjectionViewModel:
        try:
            service = self._application_factory.container.resolve(
                ConfiguredMacroIntelligenceService
            )
            payload: dict[str, Any] = service.get_projection()
        except Exception as exc:
            return MacroProjectionViewModel(
                status="ERROR",
                diagnostic=f"{type(exc).__name__}: {exc}",
            )

        if str(payload.get("status") or "").upper() != "AVAILABLE":
            return MacroProjectionViewModel(
                status=str(payload.get("status") or "UNAVAILABLE"),
                scenario_id=str(payload.get("scenario_id") or "-"),
                diagnostic=str(payload.get("diagnostic") or "Projection unavailable"),
            )

        rows: list[MacroProjectionRow] = []
        for raw in payload.get("rows", ()):
            if not isinstance(raw, dict):
                continue
            period = self._date(raw.get("period"))
            if period is None:
                continue
            rows.append(
                MacroProjectionRow(
                    period=period,
                    fx_sell=self._float(raw.get("fx_sell")),
                    tpm=self._float(raw.get("tpm")),
                    tbp=self._float(raw.get("tbp")),
                    tri_crc_12m=self._float(raw.get("tri_crc_12m")),
                    tri_usd_12m=self._float(raw.get("tri_usd_12m")),
                    inflation=self._float(raw.get("inflation")),
                    imae=self._float(raw.get("imae")),
                )
            )

        rows.sort(key=lambda item: item.period)
        return MacroProjectionViewModel(
            status="AVAILABLE",
            scenario_id=str(payload.get("scenario_id") or "-"),
            version=int(payload.get("version") or 0),
            scenario_type=str(payload.get("scenario_type") or "-"),
            scenario_status=str(payload.get("scenario_status") or "-"),
            dataset_as_of_date=self._date(payload.get("dataset_as_of_date")),
            horizon=int(payload.get("horizon") or len(rows)),
            rows=tuple(rows),
        )

    def build_forecast_lab(
        self,
        indicator_code: str,
        *,
        force_refresh: bool = False,
    ) -> MacroForecastLabViewModel:
        code = indicator_code.strip().upper()
        label = self._LABELS.get(code, code)
        try:
            service = self._application_factory.container.resolve(
                ConfiguredAdvancedMacroForecastingService
            )
            result = service.evaluate_indicator(
                code,
                forecast_horizon=12,
                force_refresh=force_refresh,
            )
        except Exception as exc:
            return MacroForecastLabViewModel(
                indicator_code=code,
                indicator_label=label,
                status="ERROR",
                diagnostic=f"{type(exc).__name__}: {exc}",
            )

        ranked = sorted(
            result.model_results,
            key=lambda item: (
                0 if item.available and item.weighted_relative_score is not None else 1,
                float(item.weighted_relative_score or math.inf),
                item.model_name,
            ),
        )
        model_views: list[MacroModelComparisonView] = []
        rank = 0
        for item in ranked:
            if item.available and item.weighted_relative_score is not None:
                rank += 1
                rank_text = str(rank)
            else:
                rank_text = "N/D"
            metrics = tuple(
                MacroModelMetricView(
                    horizon=f"{metric.horizon_months}M",
                    rmse=self._number(metric.rmse),
                    mae=self._number(metric.mae),
                    bias=self._signed(metric.bias),
                    directional_accuracy=self._percent_ratio(metric.directional_accuracy),
                    relative_rmse=self._number(metric.relative_rmse_vs_naive),
                )
                for metric in item.metrics
            )
            model_views.append(
                MacroModelComparisonView(
                    rank=rank_text,
                    model_name=item.model_name,
                    family=item.model_family,
                    status=item.status,
                    weighted_score=self._number(item.weighted_relative_score),
                    improvement_vs_naive=self._percent_ratio(item.improvement_vs_naive),
                    metrics=metrics,
                )
            )

        ensemble = tuple(
            MacroEnsembleWeightView(
                model_name=item.model_name,
                family=item.model_family,
                weight=f"{item.weight * 100.0:,.1f}%",
            )
            for item in result.ensemble_weights
        )
        points = tuple(
            MacroForecastPointView(
                horizon=item.horizon_months,
                period=item.target_period,
                forecast=item.point_forecast,
                lower_80=item.lower_80,
                upper_80=item.upper_80,
                lower_95=item.lower_95,
                upper_95=item.upper_95,
            )
            for item in result.forecast_points
        )

        return MacroForecastLabViewModel(
            indicator_code=code,
            indicator_label=label,
            status=result.status,
            forecast_origin=result.forecast_origin,
            historical_observations=result.historical_observations,
            champion_model=result.champion_model_name or "-",
            champion_family=result.champion_model_family or "-",
            confidence_score=(
                f"{result.confidence_score:,.1f}%" if result.confidence_score is not None else "-"
            ),
            projection_1m=self._forecast_value(code, result.point_at_horizon(1)),
            projection_3m=self._forecast_value(code, result.point_at_horizon(3)),
            projection_6m=self._forecast_value(code, result.point_at_horizon(6)),
            projection_12m=self._forecast_value(code, result.point_at_horizon(12)),
            models=tuple(model_views),
            ensemble=ensemble,
            points=points,
            diagnostic=result.diagnostic,
        )

    @staticmethod
    def _number(value: float | None) -> str:
        if value is None or not math.isfinite(value):
            return "-"
        return f"{value:,.4f}"

    @staticmethod
    def _signed(value: float | None) -> str:
        if value is None or not math.isfinite(value):
            return "-"
        return f"{value:+,.4f}"

    @staticmethod
    def _percent_ratio(value: float | None) -> str:
        if value is None or not math.isfinite(value):
            return "-"
        return f"{value * 100.0:,.1f}%"

    @staticmethod
    def _forecast_value(code: str, point: object) -> str:
        if point is None:
            return "-"
        value = getattr(point, "point_forecast", None)
        if value is None:
            return "-"
        numeric = float(value)
        return f"₡{numeric:,.2f}" if code == "FX_SELL" else f"{numeric:,.2f}%"
