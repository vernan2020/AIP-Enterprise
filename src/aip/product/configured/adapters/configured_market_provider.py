from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from aip.product.configured.services.institutional_portfolio_rotation_service import (
    InstitutionalPortfolioRotationService,
)

from aip.domain.financial_math.curves.nelson_siegel import (
    nelson_siegel_zero_rate,
)
from aip.product.configured.configuration.configured_source_config import (
    ConfiguredSourceConfig,
)
from aip.product.configured.context.valuation_date_context import ValuationDateContext
from aip.product.configured.protocols import (
    PortfolioDataProvider,
    SourceHealthProvider,
)
from aip.product.configured.services.institutional_market_curve_service import (
    InstitutionalMarketCurveService,
)
from aip.product.configured.services.institutional_market_relative_value_service import (
    InstitutionalMarketRelativeValueService,
)
from aip.product.configured.services.institutional_relative_value_service import (
    InstitutionalRelativeValueService,
)
from aip.product.demo.configuration.demo_config import DemoConfig


class ConfiguredMarketProvider:
    """Configured provider for institutional market analytics."""

    def __init__(
        self,
        config: DemoConfig,
        source_config: ConfiguredSourceConfig | None = None,
        health_provider: SourceHealthProvider | None = None,
        portfolio_provider: PortfolioDataProvider | None = None,
        curve_service: InstitutionalMarketCurveService | None = None,
        relative_value_service: InstitutionalRelativeValueService | None = None,
        market_relative_value_service: InstitutionalMarketRelativeValueService | None = None,
        rotation_service: InstitutionalPortfolioRotationService | None = None,
        valuation_date_context: ValuationDateContext | None = None,
    ) -> None:
        self._config = config
        self._source_config = source_config or ConfiguredSourceConfig()

        self._health_provider = health_provider

        self._portfolio_provider = portfolio_provider

        self._curve_service = curve_service or InstitutionalMarketCurveService()

        self._relative_value_service = relative_value_service or InstitutionalRelativeValueService()

        self._market_relative_value_service = (
            market_relative_value_service or InstitutionalMarketRelativeValueService()
        )

        self._rotation_service = rotation_service or InstitutionalPortfolioRotationService()

        self._valuation_date_context = valuation_date_context

    def get_market(
        self,
    ) -> dict[str, Any]:
        source_status = (
            self._health_provider.get_health() if self._health_provider is not None else {}
        )

        if self._portfolio_provider is None:
            return self._empty_market_payload(
                source_status,
                "No portfolio/vector provider is configured",
            )

        portfolio = self._portfolio_provider.get_portfolio()

        vector_payload = (
            portfolio.get(
                "price_vector",
                {},
            )
            or {}
        )

        vector_records = (
            vector_payload.get(
                "records",
                [],
            )
            or []
        )

        valuation_date = portfolio.get("valuation_date") or self._current_cutoff_date()

        cutoff_date = (
            date.fromisoformat(valuation_date)
            if isinstance(
                valuation_date,
                str,
            )
            else valuation_date
        )

        if not vector_records:
            return self._empty_market_payload(
                source_status,
                "Price vector is unavailable",
            )

        # =========================================================
        # CURVAS INSTITUCIONALES
        # =========================================================

        curve_results = self._curve_service.build_curves(
            vector_records,
            cutoff_date,
        )

        curves = [self._serialize_curve(result) for result in curve_results]

        # =========================================================
        # RV PORTAFOLIO
        # =========================================================

        portfolio_relative_value_results = self._relative_value_service.calculate(
            portfolio.get(
                "positions",
                [],
            )
            or [],
            curves,
            cutoff_date,
        )

        pricing_results = [
            self._serialize_relative_value(result) for result in portfolio_relative_value_results
        ]

        relative_value_opportunities = sum(
            1
            for result in portfolio_relative_value_results
            if result.classification
            in {
                "CHEAP",
                "RICH",
            }
        )

        average_spread = (
            sum(float(result.spread_bp) for result in portfolio_relative_value_results)
            / len(portfolio_relative_value_results)
            if portfolio_relative_value_results
            else 0.0
        )

        # =========================================================
        # RV MERCADO
        # =========================================================

        market_relative_value_results = self._market_relative_value_service.calculate(
            vector_records,
            curves,
            cutoff_date,
            portfolio.get(
                "positions",
                [],
            )
            or [],
        )

        market_relative_value_payload = [
            self._serialize_market_relative_value(result)
            for result in market_relative_value_results
        ]

        market_cheap_count = sum(
            1 for result in market_relative_value_results if result.classification == "BARATO"
        )

        market_neutral_count = sum(
            1 for result in market_relative_value_results if result.classification == "NEUTRAL"
        )

        market_rich_count = sum(
            1 for result in market_relative_value_results if result.classification == "CARO"
        )

        market_outside_portfolio_count = sum(
            1 for result in market_relative_value_results if not result.in_portfolio
        )

        market_in_portfolio_count = sum(
            1 for result in market_relative_value_results if result.in_portfolio
        )

        # =========================================================
        # SCREENING DE ROTACIÓN
        # =========================================================

        rotation_results = self._rotation_service.calculate(
            pricing_results,
            market_relative_value_payload,
        )

        rotation_payload = [self._serialize_rotation(result) for result in rotation_results]

        rotation_candidate_count = sum(
            1 for result in rotation_results if result.screening_status == "CANDIDATO"
        )

        rotation_review_count = sum(
            1 for result in rotation_results if result.screening_status == "REVISAR"
        )

        rotation_discard_count = sum(
            1 for result in rotation_results if result.screening_status == "DESCARTAR"
        )

        # =========================================================
        # PAYLOAD
        # =========================================================

        return {
            "market_date": (cutoff_date.isoformat()),
            "market_status": ("Configured" if curves else "Unavailable"),
            # Curvas
            "curves": curves,
            # -----------------------------------------------------
            # RV Portafolio
            # -----------------------------------------------------
            "pricing_results": (pricing_results),
            "relative_value_opportunities": (relative_value_opportunities),
            "average_spread": (average_spread),
            # -----------------------------------------------------
            # RV Mercado
            # -----------------------------------------------------
            "market_relative_value_results": (market_relative_value_payload),
            "market_relative_value_count": (len(market_relative_value_results)),
            "market_cheap_count": (market_cheap_count),
            "market_neutral_count": (market_neutral_count),
            "market_rich_count": (market_rich_count),
            "market_outside_portfolio_count": (market_outside_portfolio_count),
            "market_in_portfolio_count": (market_in_portfolio_count),
            # -----------------------------------------------------
            # Rotación preliminar
            # -----------------------------------------------------
            "portfolio_rotation_results": (rotation_payload),
            "portfolio_rotation_count": (len(rotation_results)),
            "portfolio_rotation_candidate_count": (rotation_candidate_count),
            "portfolio_rotation_review_count": (rotation_review_count),
            "portfolio_rotation_discard_count": (rotation_discard_count),
            # -----------------------------------------------------
            # Métricas reservadas
            # -----------------------------------------------------
            "average_yield": 0.0,
            "average_duration": 0.0,
            # -----------------------------------------------------
            # Estado
            # -----------------------------------------------------
            "source_status": (source_status),
            "data_quality_status": ("HEALTHY" if len(curves) == 3 else "DEGRADED"),
            "configuration_message": (
                "Institutional curves, portfolio RV, market RV "
                "and preliminary rotation screening built from PiPCA"
                if curves
                else "Institutional market analytics could not be built"
            ),
        }

    def _current_cutoff_date(self) -> date:
        if self._valuation_date_context is not None:
            return self._valuation_date_context.value
        return self._config.data_cutoff_date

    def _empty_market_payload(
        self,
        source_status: dict[str, Any],
        message: str,
    ) -> dict[str, Any]:
        return {
            "market_date": (self._current_cutoff_date().isoformat()),
            "market_status": ("Unavailable"),
            # Curvas
            "curves": [],
            # RV Portafolio
            "pricing_results": [],
            "relative_value_opportunities": 0,
            "average_spread": 0.0,
            # RV Mercado
            "market_relative_value_results": [],
            "market_relative_value_count": 0,
            "market_cheap_count": 0,
            "market_neutral_count": 0,
            "market_rich_count": 0,
            "market_outside_portfolio_count": 0,
            "market_in_portfolio_count": 0,
            # Rotación
            "portfolio_rotation_results": [],
            "portfolio_rotation_count": 0,
            "portfolio_rotation_candidate_count": 0,
            "portfolio_rotation_review_count": 0,
            "portfolio_rotation_discard_count": 0,
            # Métricas reservadas
            "average_yield": 0.0,
            "average_duration": 0.0,
            # Estado
            "source_status": (source_status),
            "data_quality_status": ("DEGRADED"),
            "configuration_message": (message),
        }

    @staticmethod
    def _serialize_curve(
        result: Any,
    ) -> dict[str, Any]:
        ns = result.nelson_siegel
        poly = result.polynomial_degree2

        observed_points = [
            {
                "tenor": float(tenor),
                "yield": float(rate),
            }
            for tenor, rate in result.observations
        ]

        max_tenor = float(result.max_tenor)

        standard_tenors = (
            0.25,
            0.5,
            1.0,
            2.0,
            3.0,
            5.0,
            7.0,
            10.0,
            15.0,
            20.0,
            25.0,
            30.0,
        )

        grid = [tenor for tenor in standard_tenors if tenor <= max_tenor]

        if not grid or grid[-1] < max_tenor:
            grid.append(max_tenor)

        nelson_siegel_points: list[dict[str, float]] = []

        polynomial_degree2_points: list[dict[str, float]] = []

        for tenor in grid:
            tenor_decimal = Decimal(str(tenor))

            ns_rate = nelson_siegel_zero_rate(
                tenor_decimal,
                beta0=ns.beta0,
                beta1=ns.beta1,
                beta2=ns.beta2,
                tau=ns.tau,
            )

            poly_rate = (
                poly.curve.a
                + poly.curve.b * tenor_decimal
                + poly.curve.c * tenor_decimal * tenor_decimal
            )

            nelson_siegel_points.append(
                {
                    "tenor": tenor,
                    "yield": float(ns_rate),
                }
            )

            polynomial_degree2_points.append(
                {
                    "tenor": tenor,
                    "yield": float(poly_rate),
                }
            )

        return {
            "curve_id": (result.curve_id),
            "label": (
                result.curve_id.replace(
                    "_",
                    " ",
                ).title()
            ),
            "official_model": ("NELSON_SIEGEL"),
            "observation_count": (result.observation_count),
            "min_tenor": float(result.min_tenor),
            "max_tenor": float(result.max_tenor),
            "observed_points": (observed_points),
            "nelson_siegel_points": (nelson_siegel_points),
            "polynomial_degree2_points": (polynomial_degree2_points),
            "nelson_siegel": {
                "beta0": float(ns.beta0),
                "beta1": float(ns.beta1),
                "beta2": float(ns.beta2),
                "tau": float(ns.tau),
                "rmse": float(ns.metrics.rmse),
                "mae": float(ns.metrics.mae),
                "r_squared": float(ns.metrics.r_squared),
            },
            "polynomial_degree2": {
                "a": float(poly.curve.a),
                "b": float(poly.curve.b),
                "c": float(poly.curve.c),
                "rmse": float(poly.metrics.rmse),
                "mae": float(poly.metrics.mae),
                "r_squared": float(poly.metrics.r_squared),
            },
        }

    @staticmethod
    def _serialize_relative_value(
        result: Any,
    ) -> dict[str, Any]:
        """Serializa Valor Relativo del portafolio."""

        return {
            "issuer": (result.issuer),
            "instrument": (result.series),
            "isin": (result.isin),
            "series": (result.series),
            "currency": (result.currency),
            "product_code": (result.product_code),
            "curve_id": (result.curve_id),
            "maturity_date": (result.maturity_date.isoformat()),
            "tenor": float(result.tenor),
            "position_count": (result.position_count),
            "market_value_crc": float(result.market_value_crc),
            "market_yield": float(result.market_yield),
            "curve_yield": float(result.curve_yield),
            "spread_bp": float(result.spread_bp),
            "classification": (result.classification),
        }

    @staticmethod
    def _serialize_market_relative_value(
        result: Any,
    ) -> dict[str, Any]:
        """Serializa Valor Relativo del universo completo PiPCA."""

        return {
            "curve_id": (result.curve_id),
            "issuer": (result.issuer),
            "series": (result.series),
            "isin": (result.isin),
            "maturity_date": (result.maturity_date.isoformat()),
            "tenor": float(result.tenor),
            "market_yield": float(result.market_yield),
            "curve_yield": float(result.curve_yield),
            "spread_bp": float(result.spread_bp),
            "classification": (result.classification),
            "market_price": (
                float(result.market_price) if result.market_price is not None else None
            ),
            "in_portfolio": (result.in_portfolio),
        }

    @staticmethod
    def _serialize_rotation(
        result: Any,
    ) -> dict[str, Any]:
        """Serializa el screening preliminar de rotación."""

        return {
            # Origen
            "source_series": (result.source_series),
            "source_issuer": (result.source_issuer),
            "source_currency": (result.source_currency),
            "source_curve_id": (result.source_curve_id),
            "source_spread_bp": (result.source_spread_bp),
            "source_market_yield": (result.source_market_yield),
            "source_curve_yield": (result.source_curve_yield),
            "source_tenor": (result.source_tenor),
            "source_market_value_crc": (result.source_market_value_crc),
            # Destino
            "target_series": (result.target_series),
            "target_issuer": (result.target_issuer),
            "target_currency": (result.target_currency),
            "target_curve_id": (result.target_curve_id),
            "target_spread_bp": (result.target_spread_bp),
            "target_market_yield": (result.target_market_yield),
            "target_curve_yield": (result.target_curve_yield),
            "target_tenor": (result.target_tenor),
            "target_market_price": (result.target_market_price),
            "target_in_portfolio": (result.target_in_portfolio),
            # Comparación
            "spread_improvement_bp": (result.spread_improvement_bp),
            "yield_improvement_bp": (result.yield_improvement_bp),
            "tenor_difference_years": (result.tenor_difference_years),
            # Screening
            "rotation_score": (result.rotation_score),
            "screening_status": (result.screening_status),
            "signal_type": (result.signal_type),
            "requires_duration_review": (result.requires_duration_review),
            "requires_liquidity_review": (result.requires_liquidity_review),
            "requires_concentration_review": (result.requires_concentration_review),
            "explanation": (result.explanation),
        }
