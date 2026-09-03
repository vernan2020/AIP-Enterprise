from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

from aip.product.configured.adapters.configured_portfolio_provider import (
    ConfiguredPortfolioProvider,
)
from aip.product.configured.services.configured_portfolio_dv01_service import (
    ConfiguredPortfolioDV01Service,
)
from aip.product.configured.services.configured_portfolio_rate_shock_service import (
    ConfiguredPortfolioRateShockService,
)
from aip.product.configured.services.configured_portfolio_var_service import (
    ConfiguredPortfolioVaRService,
)
from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.ui.modules.price_risk.models.price_risk_row import (
    PriceRiskRow,
    RateShockViewRow,
    RiskChartPoint,
)
from aip.ui.modules.price_risk.viewmodels.price_risk_view_model import PriceRiskViewModel


class PriceRiskPresenter:
    """Adapta resultados certificados de VeR, DV01 y sensibilidad para la UI."""

    def __init__(self, demo_factory: DemoApplicationFactory) -> None:
        self._application_factory = demo_factory

    @staticmethod
    def _decimal(value: object) -> Decimal:
        if isinstance(value, Decimal):
            return value
        if value is None:
            return Decimal("0")
        try:
            return Decimal(str(value))
        except (TypeError, ValueError):
            return Decimal("0")

    @classmethod
    def _format_crc(cls, value: object) -> str:
        return f"₡{cls._decimal(value):,.2f}"

    @classmethod
    def _format_crc_mm(cls, value: object) -> str:
        return f"₡{cls._decimal(value) / Decimal('1000000'):,.2f} MM"

    @classmethod
    def _format_percent(cls, value: object, *, decimals: int = 2) -> str:
        return f"{cls._decimal(value):.{decimals}f}%"

    @classmethod
    def _format_duration(cls, value: object) -> str:
        if value is None:
            return "N/A"
        return f"{cls._decimal(value):.2f}"

    @staticmethod
    def _format_date(value: object) -> str:
        if value is None:
            return "-"
        if isinstance(value, datetime):
            return value.strftime("%d/%m/%Y")
        if isinstance(value, date):
            return value.strftime("%d/%m/%Y")
        text = str(value).strip()
        if not text:
            return "-"
        try:
            return date.fromisoformat(text[:10]).strftime("%d/%m/%Y")
        except ValueError:
            return text

    @classmethod
    def _bucket_payload(
        cls,
        dv01_result: object,
        bucket_key: str,
    ) -> tuple[str, str, str, int, RiskChartPoint]:
        rows = tuple(getattr(dv01_result, "by_bucket", ()) or ())
        row = next((item for item in rows if str(item.key) == bucket_key), None)
        total_dv01 = cls._decimal(getattr(dv01_result, "total_dv01_crc", Decimal("0")))
        if row is None:
            point = RiskChartPoint(bucket_key, Decimal("0"), Decimal("0"))
            return "-", "-", "-", 0, point
        dv01 = cls._decimal(row.dv01_crc)
        share = dv01 / total_dv01 * Decimal("100") if total_dv01 else Decimal("0")
        return (
            cls._format_crc_mm(dv01),
            cls._format_percent(share),
            cls._format_crc_mm(row.market_value_crc),
            int(row.position_count),
            RiskChartPoint(bucket_key, dv01, share),
        )

    @classmethod
    def _build_var_chart_contracts(
        cls,
        positions: tuple[object, ...],
    ) -> tuple[
        tuple[RiskChartPoint, ...],
        tuple[RiskChartPoint, ...],
        tuple[RiskChartPoint, ...],
        tuple[RiskChartPoint, ...],
        Decimal,
    ]:
        """Construye agregaciones de presentación sin alterar el cálculo VeR."""

        contribution_rows = sorted(
            positions,
            key=lambda item: cls._decimal(
                getattr(item, "contribution_at_var_scenario_percent", Decimal("0"))
            ),
            reverse=True,
        )
        all_contribution_points = tuple(
            RiskChartPoint(
                str(getattr(item, "series", "")),
                cls._decimal(getattr(item, "contribution_at_var_scenario_percent", Decimal("0"))),
            )
            for item in contribution_rows
        )
        top_contribution_points = all_contribution_points[:10]

        cumulative = Decimal("0")
        pareto_points: list[RiskChartPoint] = []
        for point in all_contribution_points:
            cumulative += point.value
            pareto_points.append(
                RiskChartPoint(
                    label=point.label,
                    value=point.value,
                    secondary_value=cumulative,
                )
            )

        issuer_values: dict[str, Decimal] = defaultdict(Decimal)
        currency_values: dict[str, Decimal] = defaultdict(Decimal)
        total_market_value = Decimal("0")
        for item in positions:
            issuer = str(getattr(item, "issuer", "N/D") or "N/D")
            currency = str(getattr(item, "currency", "N/D") or "N/D").upper()
            contribution = cls._decimal(
                getattr(item, "contribution_at_var_scenario_percent", Decimal("0"))
            )
            market_value = cls._decimal(getattr(item, "market_value_crc", Decimal("0")))
            issuer_values[issuer] += contribution
            currency_values[currency] += market_value
            total_market_value += market_value

        issuer_points = tuple(
            RiskChartPoint(label, value)
            for label, value in sorted(
                issuer_values.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:8]
        )
        currency_points = tuple(
            RiskChartPoint(
                label,
                value,
                (
                    value / total_market_value * Decimal("100")
                    if total_market_value
                    else Decimal("0")
                ),
            )
            for label, value in sorted(
                currency_values.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        )
        return (
            top_contribution_points,
            tuple(pareto_points),
            issuer_points,
            currency_points,
            cumulative,
        )

    @classmethod
    def _build_var_rows(
        cls,
        positions: tuple[object, ...],
        dv01_result: object | None,
    ) -> tuple[PriceRiskRow, ...]:
        details = {
            str(item.security_key): item
            for item in tuple(getattr(dv01_result, "title_details", ()) or ())
        }
        ordered_positions = tuple(
            sorted(
                positions,
                key=lambda item: cls._decimal(
                    getattr(item, "contribution_at_var_scenario_percent", Decimal("0"))
                ),
                reverse=True,
            )
        )
        rows: list[PriceRiskRow] = []
        for position in ordered_positions:
            security_key = str(position.security_key)
            detail = details.get(security_key)
            rows.append(
                PriceRiskRow(
                    series=str(position.series),
                    issuer=str(position.issuer),
                    currency=str(position.currency),
                    market_value=cls._format_crc_mm(position.market_value_crc),
                    pnl_scenario=cls._format_crc(position.pnl_at_portfolio_var_scenario_crc),
                    contribution_percent=cls._format_percent(
                        position.contribution_at_var_scenario_percent,
                        decimals=4,
                    ),
                    individual_var_percent=cls._format_percent(
                        position.individual_var_percent,
                        decimals=4,
                    ),
                    real_observations=int(position.real_price_observations),
                    synthetic_observations=int(position.synthetic_price_observations),
                    security_key=security_key,
                    modified_duration=(
                        cls._format_duration(detail.modified_duration)
                        if detail is not None
                        else "N/A"
                    ),
                    dv01=(
                        cls._format_crc_mm(detail.dv01_crc)
                        if detail is not None and detail.dv01_crc is not None
                        else "N/A"
                    ),
                    bucket=(str(detail.bucket) if detail is not None else "N/A"),
                    dv01_status=(str(detail.status) if detail is not None else "UNAVAILABLE"),
                )
            )
        return tuple(rows)

    def build_view_model(self, *, force_refresh: bool = False) -> PriceRiskViewModel:
        try:
            portfolio_provider = self._application_factory.container.resolve(
                ConfiguredPortfolioProvider
            )
            portfolio = portfolio_provider.get_portfolio()
            var_service = self._application_factory.container.resolve(ConfiguredPortfolioVaRService)
            var_result = var_service.calculate(
                portfolio=portfolio,
                force_refresh=force_refresh,
            )
        except Exception as exc:
            return PriceRiskViewModel(status="ERROR", diagnostic=str(exc))

        dv01_result = None
        dv01_diagnostic: str | None = None
        try:
            dv01_service = self._application_factory.container.resolve(
                ConfiguredPortfolioDV01Service
            )
            dv01_result = dv01_service.calculate(portfolio=portfolio)
        except Exception as exc:
            dv01_diagnostic = str(exc)

        rate_shock_result = None
        rate_shock_diagnostic: str | None = None
        try:
            rate_shock_service = self._application_factory.container.resolve(
                ConfiguredPortfolioRateShockService
            )
            rate_shock_result = rate_shock_service.calculate(portfolio=portfolio)
        except Exception as exc:
            rate_shock_diagnostic = str(exc)

        dv01_values: dict[str, object] = {
            "dv01_total": "-",
            "dv01_crc": "-",
            "dv01_usd": "-",
            "dv01_coverage_percent": "-",
            "dv01_eligible_market_value": "-",
            "dv01_calculated_positions": 0,
            "dv01_excluded_positions": 0,
            "dv01_data_gaps": 0,
            "dv01_status": "UNAVAILABLE",
        }
        bucket_points: tuple[RiskChartPoint, ...] = ()
        dv01_currency_points: tuple[RiskChartPoint, ...] = ()
        bucket_payload: dict[str, tuple[str, str, str, int]] = {
            "lt1": ("-", "-", "-", 0),
            "1to5": ("-", "-", "-", 0),
            "gt5": ("-", "-", "-", 0),
        }

        if dv01_result is not None:
            dv01_values = {
                "dv01_total": self._format_crc_mm(dv01_result.total_dv01_crc),
                "dv01_crc": self._format_crc_mm(dv01_result.dv01_crc_currency),
                "dv01_usd": self._format_crc_mm(dv01_result.dv01_usd_currency),
                "dv01_coverage_percent": self._format_percent(dv01_result.coverage_percent),
                "dv01_eligible_market_value": self._format_crc_mm(
                    dv01_result.calculated_market_value_crc
                ),
                "dv01_calculated_positions": int(dv01_result.calculated_position_count),
                "dv01_excluded_positions": int(dv01_result.policy_excluded_position_count),
                "dv01_data_gaps": int(dv01_result.data_unavailable_position_count),
                "dv01_status": str(dv01_result.status),
            }
            bucket_rows: list[RiskChartPoint] = []
            for alias, key in (
                ("lt1", "< 1 año"),
                ("1to5", "1 a 5 años"),
                ("gt5", "> 5 años"),
            ):
                value, share, market_value, count, point = self._bucket_payload(
                    dv01_result,
                    key,
                )
                bucket_payload[alias] = (value, share, market_value, count)
                bucket_rows.append(point)
            bucket_points = tuple(bucket_rows)

            total_dv01 = self._decimal(dv01_result.total_dv01_crc)
            dv01_currency_points = tuple(
                RiskChartPoint(
                    str(item.key),
                    self._decimal(item.dv01_crc),
                    (
                        self._decimal(item.dv01_crc) / total_dv01 * Decimal("100")
                        if total_dv01
                        else Decimal("0")
                    ),
                )
                for item in dv01_result.by_currency
            )

        rate_shock_rows: tuple[RateShockViewRow, ...] = ()
        rate_shock_points: tuple[RiskChartPoint, ...] = ()
        rate_shock_coverage = "-"
        rate_shock_status = "UNAVAILABLE"
        worst_shock = "-"
        worst_delta_eve = "-"
        if rate_shock_result is not None:
            ordered_scenarios = tuple(
                sorted(rate_shock_result.scenarios, key=lambda item: item.shock_bp)
            )
            rate_shock_rows = tuple(
                RateShockViewRow(
                    shock_bp=int(item.shock_bp),
                    shock_label=f"{item.shock_bp:+d} pb",
                    delta_eve=self._format_crc_mm(item.delta_eve_crc),
                    shocked_market_value=self._format_crc_mm(item.shocked_market_value_crc),
                    delta_eve_crc=self._decimal(item.delta_eve_crc),
                )
                for item in ordered_scenarios
            )
            rate_shock_points = tuple(
                RiskChartPoint(row.shock_label, row.delta_eve_crc) for row in rate_shock_rows
            )
            rate_shock_coverage = self._format_percent(rate_shock_result.coverage_percent)
            rate_shock_status = str(rate_shock_result.status)
            if rate_shock_result.worst_shock_bp is not None:
                worst_shock = f"{int(rate_shock_result.worst_shock_bp):+d} pb"
            if rate_shock_result.worst_delta_eve_crc is not None:
                worst_delta_eve = self._format_crc_mm(rate_shock_result.worst_delta_eve_crc)

        portfolio_var = var_result.portfolio_var
        combined_diagnostics = tuple(
            item
            for item in (
                var_result.diagnostic,
                f"DV01: {dv01_diagnostic}" if dv01_diagnostic else None,
                (f"Sensibilidad: {rate_shock_diagnostic}" if rate_shock_diagnostic else None),
            )
            if item
        )
        diagnostic = " | ".join(combined_diagnostics) if combined_diagnostics else None

        if portfolio_var is None:
            return PriceRiskViewModel(
                valuation_date=self._format_date(var_result.valuation_date),
                eligible_market_value=self._format_crc_mm(var_result.eligible_market_value_crc),
                calculated_market_value=self._format_crc_mm(var_result.calculated_market_value_crc),
                policy_excluded_market_value=self._format_crc_mm(
                    var_result.policy_excluded_market_value_crc
                ),
                history_excluded_market_value=self._format_crc_mm(
                    var_result.excluded_market_value_crc
                ),
                coverage_percent=self._format_percent(var_result.coverage_percent),
                eligible_positions=int(var_result.eligible_position_count),
                policy_excluded_positions=int(var_result.policy_excluded_position_count),
                calculated_titles=int(var_result.calculated_title_count),
                history_excluded_titles=int(var_result.excluded_title_count),
                required_prices=int(var_result.required_prices),
                horizon_observations=int(var_result.horizon_observations),
                scenario_count=int(var_result.scenario_count),
                dv01_total=str(dv01_values["dv01_total"]),
                dv01_crc=str(dv01_values["dv01_crc"]),
                dv01_usd=str(dv01_values["dv01_usd"]),
                dv01_coverage_percent=str(dv01_values["dv01_coverage_percent"]),
                dv01_eligible_market_value=str(dv01_values["dv01_eligible_market_value"]),
                dv01_calculated_positions=int(dv01_values["dv01_calculated_positions"]),
                dv01_excluded_positions=int(dv01_values["dv01_excluded_positions"]),
                dv01_data_gaps=int(dv01_values["dv01_data_gaps"]),
                dv01_status=str(dv01_values["dv01_status"]),
                rate_shock_coverage_percent=rate_shock_coverage,
                rate_shock_status=rate_shock_status,
                worst_shock=worst_shock,
                worst_delta_eve=worst_delta_eve,
                rate_shock_rows=rate_shock_rows,
                rate_shock_points=rate_shock_points,
                status=str(var_result.status),
                diagnostic=diagnostic,
            )

        rows = self._build_var_rows(tuple(portfolio_var.positions), dv01_result)
        (
            top_contribution_points,
            pareto_points,
            issuer_points,
            currency_market_value_points,
            contribution_reconciliation,
        ) = self._build_var_chart_contracts(tuple(portfolio_var.positions))

        return PriceRiskViewModel(
            valuation_date=self._format_date(var_result.valuation_date),
            var_crc=self._format_crc_mm(portfolio_var.portfolio_var_crc),
            var_percent=self._format_percent(
                portfolio_var.portfolio_var_percent,
                decimals=4,
            ),
            eligible_market_value=self._format_crc_mm(var_result.eligible_market_value_crc),
            calculated_market_value=self._format_crc_mm(var_result.calculated_market_value_crc),
            policy_excluded_market_value=self._format_crc_mm(
                var_result.policy_excluded_market_value_crc
            ),
            history_excluded_market_value=self._format_crc_mm(var_result.excluded_market_value_crc),
            coverage_percent=self._format_percent(var_result.coverage_percent),
            contribution_reconciliation_percent=self._format_percent(
                contribution_reconciliation,
                decimals=4,
            ),
            eligible_positions=int(var_result.eligible_position_count),
            policy_excluded_positions=int(var_result.policy_excluded_position_count),
            calculated_titles=int(var_result.calculated_title_count),
            history_excluded_titles=int(var_result.excluded_title_count),
            required_prices=int(var_result.required_prices),
            horizon_observations=int(var_result.horizon_observations),
            scenario_count=int(portfolio_var.scenario_count),
            var_rank=int(portfolio_var.var_rank),
            scenario_number=int(portfolio_var.var_scenario_number),
            scenario_start_date=self._format_date(portfolio_var.var_scenario_lagged_date),
            scenario_end_date=self._format_date(portfolio_var.var_scenario_date),
            dv01_total=str(dv01_values["dv01_total"]),
            dv01_crc=str(dv01_values["dv01_crc"]),
            dv01_usd=str(dv01_values["dv01_usd"]),
            dv01_coverage_percent=str(dv01_values["dv01_coverage_percent"]),
            dv01_eligible_market_value=str(dv01_values["dv01_eligible_market_value"]),
            dv01_calculated_positions=int(dv01_values["dv01_calculated_positions"]),
            dv01_excluded_positions=int(dv01_values["dv01_excluded_positions"]),
            dv01_data_gaps=int(dv01_values["dv01_data_gaps"]),
            dv01_status=str(dv01_values["dv01_status"]),
            dv01_bucket_lt1_value=bucket_payload["lt1"][0],
            dv01_bucket_lt1_percent=bucket_payload["lt1"][1],
            dv01_bucket_lt1_market_value=bucket_payload["lt1"][2],
            dv01_bucket_lt1_positions=bucket_payload["lt1"][3],
            dv01_bucket_1to5_value=bucket_payload["1to5"][0],
            dv01_bucket_1to5_percent=bucket_payload["1to5"][1],
            dv01_bucket_1to5_market_value=bucket_payload["1to5"][2],
            dv01_bucket_1to5_positions=bucket_payload["1to5"][3],
            dv01_bucket_gt5_value=bucket_payload["gt5"][0],
            dv01_bucket_gt5_percent=bucket_payload["gt5"][1],
            dv01_bucket_gt5_market_value=bucket_payload["gt5"][2],
            dv01_bucket_gt5_positions=bucket_payload["gt5"][3],
            rate_shock_coverage_percent=rate_shock_coverage,
            rate_shock_status=rate_shock_status,
            worst_shock=worst_shock,
            worst_delta_eve=worst_delta_eve,
            rate_shock_rows=rate_shock_rows,
            var_contribution_points=top_contribution_points,
            var_pareto_points=pareto_points,
            issuer_contribution_points=issuer_points,
            currency_market_value_points=currency_market_value_points,
            dv01_bucket_points=bucket_points,
            dv01_currency_points=dv01_currency_points,
            rate_shock_points=rate_shock_points,
            status=str(var_result.status),
            diagnostic=diagnostic,
            rows=rows,
        )

    def refresh(self) -> PriceRiskViewModel:
        return self.build_view_model()
