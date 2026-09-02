from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.product.demo.configuration.demo_config import DemoConfig
from aip.ui.modules.market.models.curve_point import CurvePoint
from aip.ui.modules.market.models.market_row import MarketRow
from aip.ui.modules.market.viewmodels.market_view_model import (
    MarketCurveViewData,
    MarketViewModel,
    RelativeValueViewRow,
    RotationViewRow,
)


class MarketPresenter:
    """Normalize application-layer market analytics for the desktop UI."""

    def __init__(self, demo_factory: DemoApplicationFactory | None = None) -> None:
        self._demo_factory = demo_factory or DemoApplicationFactory(
            DemoConfig(execution_mode="DEMO", demo_mode_enabled=True)
        )
        self._correlation_id = "corr-demo-market"

    @staticmethod
    def _float(value: object, default: float = 0.0) -> float:
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _build_curve_contracts(
        cls,
        raw_curves: list[dict[str, Any]],
    ) -> tuple[tuple[CurvePoint, ...], tuple[MarketCurveViewData, ...]]:
        legacy_points: list[CurvePoint] = []
        curves: list[MarketCurveViewData] = []

        for raw in raw_curves:
            if "observed_points" not in raw:
                legacy_points.append(
                    CurvePoint(
                        label=str(raw.get("label") or "Curve"),
                        value=f"{cls._float(raw.get('value')):.2f}",
                        tenor=str(raw.get("tenor") or ""),
                    )
                )
                continue

            curve_id = str(raw.get("curve_id") or "UNSPECIFIED")
            label = str(raw.get("label") or curve_id)
            observed = tuple(
                (
                    cls._float(point.get("tenor")),
                    cls._float(point.get("yield")),
                )
                for point in raw.get("observed_points", ())
                if isinstance(point, dict)
            )
            fitted = tuple(
                (
                    cls._float(point.get("tenor")),
                    cls._float(point.get("yield")),
                )
                for point in raw.get("nelson_siegel_points", ())
                if isinstance(point, dict)
            )
            model = raw.get("nelson_siegel") or {}
            curves.append(
                MarketCurveViewData(
                    curve_id=curve_id,
                    label=label,
                    official_model=str(raw.get("official_model") or "NELSON_SIEGEL"),
                    observation_count=int(raw.get("observation_count") or len(observed)),
                    rmse=cls._float(model.get("rmse")) if isinstance(model, dict) else 0.0,
                    r_squared=(
                        cls._float(model.get("r_squared")) if isinstance(model, dict) else 0.0
                    ),
                    observed_points=observed,
                    fitted_points=fitted,
                )
            )
            for tenor, rate in fitted:
                legacy_points.append(
                    CurvePoint(
                        label=f"{label} {tenor:g}A",
                        value=f"{rate:.2f}",
                        tenor=f"{tenor:g}",
                    )
                )

        return tuple(legacy_points), tuple(curves)

    @classmethod
    def _portfolio_rv_rows(
        cls,
        entries: list[dict[str, Any]],
    ) -> tuple[RelativeValueViewRow, ...]:
        rows: list[RelativeValueViewRow] = []
        for entry in entries:
            if "spread_bp" not in entry:
                continue
            rows.append(
                RelativeValueViewRow(
                    series=str(entry.get("series") or entry.get("instrument") or ""),
                    issuer=str(entry.get("issuer") or ""),
                    currency=str(entry.get("currency") or ""),
                    curve_id=str(entry.get("curve_id") or ""),
                    tenor=cls._float(entry.get("tenor")),
                    market_yield=cls._float(entry.get("market_yield")),
                    curve_yield=cls._float(entry.get("curve_yield")),
                    spread_bp=cls._float(entry.get("spread_bp")),
                    classification=str(entry.get("classification") or ""),
                    market_value_crc=cls._float(entry.get("market_value_crc")),
                )
            )
        return tuple(rows)

    @classmethod
    def _market_rv_rows(
        cls,
        entries: list[dict[str, Any]],
    ) -> tuple[RelativeValueViewRow, ...]:
        return tuple(
            RelativeValueViewRow(
                series=str(entry.get("series") or ""),
                issuer=str(entry.get("issuer") or ""),
                currency=str(entry.get("currency") or ""),
                curve_id=str(entry.get("curve_id") or ""),
                tenor=cls._float(entry.get("tenor")),
                market_yield=cls._float(entry.get("market_yield")),
                curve_yield=cls._float(entry.get("curve_yield")),
                spread_bp=cls._float(entry.get("spread_bp")),
                classification=str(entry.get("classification") or ""),
                market_price=(
                    cls._float(entry.get("market_price"))
                    if entry.get("market_price") is not None
                    else None
                ),
                in_portfolio=(
                    bool(entry.get("in_portfolio"))
                    if entry.get("in_portfolio") is not None
                    else None
                ),
            )
            for entry in entries
        )

    @classmethod
    def _rotation_rows(
        cls,
        entries: list[dict[str, Any]],
    ) -> tuple[RotationViewRow, ...]:
        rows: list[RotationViewRow] = []
        for entry in entries:
            rows.append(
                RotationViewRow(
                    source_series=str(entry.get("source_series") or ""),
                    target_series=str(entry.get("target_series") or ""),
                    source_issuer=str(entry.get("source_issuer") or ""),
                    target_issuer=str(entry.get("target_issuer") or ""),
                    source_spread_bp=cls._float(entry.get("source_spread_bp")),
                    target_spread_bp=cls._float(entry.get("target_spread_bp")),
                    spread_pickup_bp=cls._float(
                        entry.get("spread_pickup_bp", entry.get("spread_improvement_bp"))
                    ),
                    screening_status=str(entry.get("screening_status") or ""),
                )
            )
        return tuple(rows)

    @classmethod
    def _legacy_market_rows(
        cls,
        entries: list[dict[str, Any]],
        market: dict[str, Any],
    ) -> tuple[MarketRow, ...]:
        rows: list[MarketRow] = []
        for entry in entries:
            if "spread_bp" in entry:
                spread = cls._float(entry.get("spread_bp"))
                market_yield = cls._float(entry.get("market_yield"))
                rows.append(
                    MarketRow(
                        issuer=str(entry.get("issuer") or ""),
                        instrument=str(entry.get("series") or entry.get("instrument") or ""),
                        currency=str(entry.get("currency") or ""),
                        recommendation=str(entry.get("classification") or "NEUTRAL"),
                        confidence="Institutional",
                        spread=f"{spread:.2f}",
                        z_spread=f"{spread:.2f}",
                        benchmark_spread="0.00",
                        market_value=f"{market_yield:.2f}",
                        book_value="-",
                        clean_price="-",
                        dirty_price="-",
                        accrued_interest="-",
                        duration=f"{cls._float(entry.get('tenor')):.2f}",
                        modified_duration="-",
                        convexity="-",
                        dv01="-",
                        pvbp="-",
                    )
                )
                continue

            average_spread = cls._float(market.get("average_spread"))
            rows.append(
                MarketRow(
                    issuer=str(entry.get("issuer") or ""),
                    instrument=str(entry.get("instrument") or ""),
                    currency=str(entry.get("currency") or "USD"),
                    recommendation=str(entry.get("recommendation") or "BUY"),
                    confidence=str(entry.get("confidence") or "High"),
                    spread=f"{average_spread:.2f}",
                    z_spread=f"{average_spread:.2f}",
                    benchmark_spread="0.05",
                    market_value=f"{cls._float(market.get('average_yield')):.2f}",
                    book_value="98.00",
                    clean_price="99.00",
                    dirty_price="100.00",
                    accrued_interest="1.00",
                    duration=f"{cls._float(market.get('average_duration')):.2f}",
                    modified_duration="4.20",
                    convexity="0.10",
                    dv01="0.01",
                    pvbp="0.02",
                )
            )
        return tuple(rows)

    def build_view_model(
        self,
        *,
        theme: str = "light",
        filters: dict[str, str] | None = None,
        selected_curve: str | None = None,
        loading: bool = False,
        error: str | None = None,
    ) -> MarketViewModel:
        workflow_result = self._demo_factory.initial_load_workflow().execute(self._correlation_id)
        market = workflow_result["market"]
        raw_curves = [item for item in market.get("curves", ()) if isinstance(item, dict)]
        pricing_results = [
            item for item in market.get("pricing_results", ()) if isinstance(item, dict)
        ]
        curve_points, curves = self._build_curve_contracts(raw_curves)
        portfolio_rv = self._portfolio_rv_rows(pricing_results)
        market_rv = self._market_rv_rows(
            [
                item
                for item in market.get("market_relative_value_results", ())
                if isinstance(item, dict)
            ]
        )
        rotation_rows = self._rotation_rows(
            [
                item
                for item in market.get("portfolio_rotation_results", ())
                if isinstance(item, dict)
            ]
        )

        summary = SimpleNamespace(
            market_date=str(market.get("market_date") or "-"),
            curves_loaded=len(raw_curves),
            pricing_date=str(market.get("market_date") or "-"),
            relative_value_opportunities=int(market.get("relative_value_opportunities") or 0),
            average_yield=f"{self._float(market.get('average_yield')):.2f}%",
            average_duration=f"{self._float(market.get('average_duration')):.2f}",
            average_spread=f"{self._float(market.get('average_spread')):.2f}",
            market_status=str(market.get("market_status") or "Unavailable"),
            market_relative_value_count=int(market.get("market_relative_value_count") or 0),
            market_cheap_count=int(market.get("market_cheap_count") or 0),
            market_neutral_count=int(market.get("market_neutral_count") or 0),
            market_rich_count=int(market.get("market_rich_count") or 0),
            market_outside_portfolio_count=int(
                market.get("market_outside_portfolio_count") or 0
            ),
            rotation_candidate_count=int(
                market.get("portfolio_rotation_candidate_count") or 0
            ),
            configuration_message=str(market.get("configuration_message") or ""),
        )

        return MarketViewModel(
            summary=summary,
            rows=self._legacy_market_rows(pricing_results, market),
            curve_points=curve_points,
            filters=filters or {},
            selected_curve=selected_curve,
            theme=theme,
            status="error" if error else "loaded",
            warnings=tuple(str(item) for item in workflow_result.get("warnings", ()) or ()),
            calculation_id=str(workflow_result["calculation_references"]["market"]),
            correlation_id=self._correlation_id,
            loading=loading,
            error=error,
            curves=curves,
            portfolio_relative_value=portfolio_rv,
            market_relative_value=market_rv,
            rotation_rows=rotation_rows,
        )

    def refresh(
        self,
        *,
        theme: str = "light",
        filters: dict[str, str] | None = None,
        selected_curve: str | None = None,
    ) -> MarketViewModel:
        return self.build_view_model(theme=theme, filters=filters, selected_curve=selected_curve)

    def select(self, curve: str | None) -> MarketViewModel:
        return self.build_view_model(selected_curve=curve)

    def apply_filters(self, filters: dict[str, str]) -> MarketViewModel:
        return self.build_view_model(filters=filters)

    def handle_theme_change(self, theme: str) -> MarketViewModel:
        return self.build_view_model(theme=theme)

    def handle_application_failure(self, error: str) -> MarketViewModel:
        return self.build_view_model(error=error)

    def set_loading(self) -> MarketViewModel:
        return self.build_view_model(loading=True)
