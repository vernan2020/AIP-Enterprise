from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from aip.product.configured.services.configured_portfolio_dv01_service import (
    ConfiguredPortfolioDV01Service,
)
from aip.product.configured.services.configured_portfolio_var_service import (
    ConfiguredPortfolioVaRService,
)
from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.ui.modules.price_risk.models.price_risk_row import PriceRiskRow, RiskChartPoint
from aip.ui.modules.price_risk.viewmodels.price_risk_view_model import PriceRiskViewModel


class PriceRiskPresenter:
    """Adapt certified VaR and DV01 application results for the desktop UI."""

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
    def _row_abs_pnl(cls, row: PriceRiskRow) -> Decimal:
        return abs(cls._decimal(row.pnl_scenario.replace("₡", "").replace(",", "").strip()))

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

    def build_view_model(self) -> PriceRiskViewModel:
        try:
            var_service = self._application_factory.container.resolve(ConfiguredPortfolioVaRService)
            var_result = var_service.calculate()
        except Exception as exc:
            return PriceRiskViewModel(status="ERROR", diagnostic=str(exc))

        try:
            dv01_service = self._application_factory.container.resolve(ConfiguredPortfolioDV01Service)
            dv01_result = dv01_service.calculate()
        except Exception:
            dv01_result = None

        portfolio_var = var_result.portfolio_var
        if portfolio_var is None:
            return PriceRiskViewModel(
                valuation_date=self._format_date(var_result.valuation_date),
                eligible_market_value=self._format_crc_mm(var_result.eligible_market_value_crc),
                coverage_percent=self._format_percent(var_result.coverage_percent),
                eligible_positions=int(var_result.eligible_position_count),
                calculated_titles=int(var_result.calculated_title_count),
                required_prices=int(var_result.required_prices),
                horizon_observations=int(var_result.horizon_observations),
                scenario_count=int(var_result.scenario_count),
                status=str(var_result.status),
                diagnostic=var_result.diagnostic,
            )

        rows: list[PriceRiskRow] = []
        contribution_points: list[RiskChartPoint] = []
        for position in portfolio_var.positions:
            contribution = self._decimal(position.contribution_at_var_scenario_percent)
            rows.append(
                PriceRiskRow(
                    series=str(position.series),
                    issuer=str(position.issuer),
                    currency=str(position.currency),
                    market_value=self._format_crc_mm(position.market_value_crc),
                    pnl_scenario=self._format_crc(position.pnl_at_portfolio_var_scenario_crc),
                    contribution_percent=self._format_percent(contribution, decimals=4),
                    individual_var_percent=self._format_percent(
                        position.individual_var_percent,
                        decimals=4,
                    ),
                    real_observations=int(position.real_price_observations),
                    synthetic_observations=int(position.synthetic_price_observations),
                    security_key=str(position.security_key),
                )
            )
            contribution_points.append(
                RiskChartPoint(str(position.series), abs(contribution), Decimal("0"))
            )

        rows.sort(key=self._row_abs_pnl, reverse=True)
        contribution_points.sort(key=lambda point: point.value, reverse=True)
        top_points = tuple(contribution_points[:10])
        cumulative = Decimal("0")
        pareto: list[RiskChartPoint] = []
        for point in top_points:
            cumulative += point.value
            pareto.append(RiskChartPoint(point.label, point.value, cumulative))

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
        currency_points: tuple[RiskChartPoint, ...] = ()
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
                value, share, market_value, count, point = self._bucket_payload(dv01_result, key)
                bucket_payload[alias] = (value, share, market_value, count)
                bucket_rows.append(point)
            bucket_points = tuple(bucket_rows)
            total_dv01 = self._decimal(dv01_result.total_dv01_crc)
            currency_rows: list[RiskChartPoint] = []
            for item in dv01_result.by_currency:
                value = self._decimal(item.dv01_crc)
                share = value / total_dv01 * Decimal("100") if total_dv01 else Decimal("0")
                currency_rows.append(RiskChartPoint(str(item.key), value, share))
            currency_points = tuple(currency_rows)

        return PriceRiskViewModel(
            valuation_date=self._format_date(var_result.valuation_date),
            var_crc=self._format_crc_mm(portfolio_var.portfolio_var_crc),
            var_percent=self._format_percent(portfolio_var.portfolio_var_percent, decimals=4),
            eligible_market_value=self._format_crc_mm(var_result.eligible_market_value_crc),
            coverage_percent=self._format_percent(var_result.coverage_percent),
            eligible_positions=int(var_result.eligible_position_count),
            calculated_titles=int(var_result.calculated_title_count),
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
            var_contribution_points=top_points,
            var_pareto_points=tuple(pareto),
            dv01_bucket_points=bucket_points,
            dv01_currency_points=currency_points,
            status=str(var_result.status),
            diagnostic=var_result.diagnostic,
            rows=tuple(rows),
        )

    def refresh(self) -> PriceRiskViewModel:
        return self.build_view_model()
