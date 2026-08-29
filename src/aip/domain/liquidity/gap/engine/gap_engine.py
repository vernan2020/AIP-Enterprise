from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable, cast

from aip.domain.analytics.explainability.explanation_factor import ExplanationFactor
from aip.domain.liquidity.cashflow.engine.cashflow_engine import CashFlowEngine
from aip.domain.liquidity.cashflow.models.projection_request import ProjectionRequest
from aip.domain.liquidity.gap.aggregation.gap_aggregation import GapAggregation
from aip.domain.liquidity.gap.analytics.gap_analytics import GapAnalytics
from aip.domain.liquidity.gap.exceptions import (
    AggregationError,
    CurrencyAggregationError,
    CurrencyMismatchError,
    GapProviderError,
    LiquidityGapError,
)
from aip.domain.liquidity.gap.explainability.gap_explanation import GapExplanation
from aip.domain.liquidity.gap.models.gap_request import GapRequest
from aip.domain.liquidity.gap.models.gap_result import GapResult
from aip.domain.liquidity.gap.models.gap_value import GapValue


class GapEngine:
    """Compose cash flow projections into liquidity gap metrics."""

    def __init__(self) -> None:
        self._cashflow_engine = CashFlowEngine()
        self._aggregation = GapAggregation()
        self._analytics = GapAnalytics()
        self._explanation = GapExplanation()

    def project(self, request: GapRequest) -> GapResult:
        projection_request = self._resolve_projection_request(request)
        if (
            request.currency is not None
            and projection_request.currency is not None
            and request.currency != projection_request.currency
        ):
            raise CurrencyMismatchError("Gap currency must match projection currency")

        sanitized_request = self._sanitize_projection_request(projection_request)
        projection_result = self._cashflow_engine.project(sanitized_request)
        config = self._resolve_configuration(request)
        gap_values = self._build_gap_values(
            projection_result.projected_cashflows, projection_request, config
        )
        if not gap_values:
            return GapResult(
                valuation_date=request.valuation_date,
                gap_type=self._normalize_gap_type(request.gap_type),
                net_gap=Decimal("0"),
                gross_inflow=Decimal("0"),
                gross_outflow=Decimal("0"),
                incremental_gap=Decimal("0"),
                cumulative_gap=Decimal("0"),
                summary_value=Decimal("0"),
                aggregation={
                    "bucket": {},
                    "currency": {},
                    "scenario": {},
                    "product": {},
                    "counterparty": {},
                    "instrument": {},
                    "portfolio": {},
                    "business_unit": {},
                },
                analytics={
                    "concentration": {},
                    "distribution": {},
                    "percentiles": {},
                    "weighted_statistics": {},
                    "scenario_comparison": {},
                },
                opening_liquidity=self._opening_liquidity(config),
                position="neutral",
                projection_type=projection_result.projection_type,
                source_cashflows=projection_result.projected_cashflows,
                scenario=projection_result.scenario,
                currency=request.currency or projection_request.currency or "USD",
                bucket_assignments=tuple(gap.bucket for gap in gap_values),
            )

        gap_values = self._apply_currency_policy(gap_values, request, projection_request, config)
        net_gap = sum((value.net_gap for value in gap_values), Decimal("0"))
        gross_inflow = sum((value.gross_inflow for value in gap_values), Decimal("0"))
        gross_outflow = sum((value.gross_outflow for value in gap_values), Decimal("0"))
        incremental_gap = sum((value.incremental_gap for value in gap_values), Decimal("0"))
        cumulative_gap = gap_values[-1].cumulative_gap if gap_values else Decimal("0")
        factors = [
            ExplanationFactor(
                name="net_gap",
                value=net_gap,
                direction="higher_is_better",
                contribution=net_gap,
                source_reference="gap",
            ),
        ]
        assumptions = request.assumptions
        if not assumptions and sanitized_request.behavioral_assumptions:
            assumptions = tuple(
                assumption.name for assumption in sanitized_request.behavioral_assumptions
            )
        explanation = self._explanation.build(
            "Liquidity gap derived from projected cash flows",
            factors,
            assumptions=assumptions,
            warnings=request.warnings,
            references=request.references,
        )
        position = self._position_for(net_gap, self._opening_liquidity(config))
        return GapResult(
            valuation_date=request.valuation_date,
            gap_type=self._normalize_gap_type(request.gap_type),
            net_gap=net_gap,
            gross_inflow=gross_inflow,
            gross_outflow=gross_outflow,
            incremental_gap=incremental_gap,
            cumulative_gap=cumulative_gap,
            summary_value=self._summary_value_for(request.gap_type, net_gap),
            gaps=gap_values,
            aggregation=self._aggregation.aggregate(gap_values, projection_request),
            analytics=self._analytics.build(gap_values),
            factors=tuple(factors),
            assumptions=assumptions,
            warnings=request.warnings,
            references=request.references,
            explanation=explanation,
            opening_liquidity=self._opening_liquidity(config),
            position=position,
            projection_type=projection_result.projection_type,
            source_cashflows=projection_result.projected_cashflows,
            scenario=projection_result.scenario,
            currency=request.currency or projection_request.currency or "USD",
            bucket_assignments=tuple(gap.bucket for gap in gap_values),
            calculation_identifier=f"gap-{request.valuation_date.isoformat()}-{self._normalize_gap_type(request.gap_type)}",
        )

    def _resolve_projection_request(self, request: GapRequest) -> ProjectionRequest:
        if request.gap_provider is not None:
            try:
                resolved = request.gap_provider.get_projection_request(request)
            except Exception as exc:
                raise GapProviderError("Gap provider failed") from exc
            return resolved
        if request.cashflow_request is None:
            raise GapProviderError("A projection request is required")
        return request.cashflow_request

    def _build_gap_values(
        self, cashflows: tuple[object, ...], request: ProjectionRequest, config: dict[str, object]
    ) -> tuple[GapValue, ...]:
        values: list[GapValue] = []
        source_cashflows = tuple(request.contractual_cashflows or ())
        cumulative_total = self._opening_liquidity(config)
        bucket_configuration = self._bucket_configuration(config)
        if bucket_configuration:
            self._validate_bucket_configuration(bucket_configuration)
        for cashflow in sorted(
            cashflows,
            key=lambda item: (
                getattr(item, "payment_date", request.valuation_date),
                getattr(item, "currency", ""),
            ),
        ):
            amount = Decimal(str(getattr(cashflow, "amount", Decimal("0"))))
            magnitude = abs(amount)
            source_amount = self._resolve_source_amount(cashflow, source_cashflows)
            if source_amount is not None:
                magnitude = abs(source_amount)
                amount = source_amount

            if amount >= 0:
                gross_inflow = magnitude
                gross_outflow = Decimal("0")
                net_gap = amount
            else:
                gross_inflow = Decimal("0")
                gross_outflow = magnitude
                net_gap = amount

            bucket = self._bucket_for(cashflow, request, bucket_configuration)
            incremental_gap = net_gap
            cumulative_total += incremental_gap
            values.append(
                GapValue(
                    period_start=getattr(cashflow, "payment_date", request.valuation_date),
                    period_end=getattr(cashflow, "payment_date", request.valuation_date),
                    net_gap=net_gap,
                    gross_inflow=gross_inflow,
                    gross_outflow=gross_outflow,
                    incremental_gap=incremental_gap,
                    cumulative_gap=cumulative_total,
                    currency=getattr(cashflow, "currency", request.currency or "USD"),
                    bucket=bucket,
                    scenario=getattr(cashflow, "scenario", request.scenario_name or "base"),
                )
            )
        return tuple(values)

    def _resolve_source_amount(
        self, cashflow: object, source_cashflows: tuple[object, ...]
    ) -> Decimal | None:
        payment_date = getattr(cashflow, "payment_date", None)
        currency = getattr(cashflow, "currency", None)
        for source_cashflow in source_cashflows:
            if (
                getattr(source_cashflow, "payment_date", None) == payment_date
                and getattr(source_cashflow, "currency", None) == currency
            ):
                return Decimal(str(getattr(source_cashflow, "amount", Decimal("0"))))
        return None

    def _resolve_configuration(self, request: GapRequest) -> dict[str, object]:
        config: dict[str, object] = dict(request.configuration)
        if request.liquidity_policy_provider is not None:
            try:
                policy = request.liquidity_policy_provider.get_policy(request)
            except Exception as exc:
                raise LiquidityGapError("Liquidity policy provider failed") from exc
            config.update(policy)
        if "opening_liquidity" not in config:
            config["opening_liquidity"] = Decimal("0")
        if "bucket_configuration" not in config:
            config["bucket_configuration"] = ()
        return config

    def _opening_liquidity(self, config: dict[str, object]) -> Decimal:
        value = config.get("opening_liquidity", Decimal("0"))
        return Decimal(str(value)) if value is not None else Decimal("0")

    def _bucket_configuration(
        self, config: dict[str, object]
    ) -> tuple[tuple[date, date, str], ...]:
        raw = config.get("bucket_configuration", ())
        if not raw:
            return ()
        return tuple(cast(Iterable[tuple[date, date, str]], raw))

    def _validate_bucket_configuration(
        self, bucket_configuration: tuple[tuple[date, date, str], ...]
    ) -> None:
        for index, current in enumerate(bucket_configuration):
            for other in bucket_configuration[index + 1 :]:
                if current[0] <= other[1] and other[0] <= current[1]:
                    raise AggregationError("Overlapping bucket configuration is not allowed")

    def _bucket_for(
        self,
        cashflow: object,
        request: ProjectionRequest,
        bucket_configuration: tuple[tuple[date, date, str], ...],
    ) -> str:
        payment_date = getattr(cashflow, "payment_date", request.valuation_date)
        if not bucket_configuration:
            return getattr(cashflow, "bucket", request.business_unit or "default")
        for start, end, bucket_name in bucket_configuration:
            if start <= payment_date <= end:
                return bucket_name
        return "default"

    def _position_for(self, net_gap: Decimal, opening_liquidity: Decimal) -> str:
        if net_gap > opening_liquidity:
            return "surplus"
        if net_gap < opening_liquidity:
            return "deficit"
        return "neutral"

    def _apply_currency_policy(
        self,
        gaps: tuple[GapValue, ...],
        request: GapRequest,
        projection_request: ProjectionRequest,
        config: dict[str, object],
    ) -> tuple[GapValue, ...]:
        currencies = {gap.currency for gap in gaps}
        if len(currencies) <= 1:
            return gaps

        target_currency = request.currency or projection_request.currency
        if target_currency is None:
            return gaps
        if request.exchange_rate_policy_provider is None:
            raise CurrencyAggregationError(
                "Multi-currency aggregation requires an exchange rate policy provider"
            )

        converted: list[GapValue] = []
        for gap in gaps:
            try:
                rate = request.exchange_rate_policy_provider.get_rate(
                    gap.currency, target_currency, request.valuation_date
                )
            except Exception as exc:
                raise CurrencyAggregationError("Exchange rate policy provider failed") from exc
            if rate is None:
                raise CurrencyAggregationError("Exchange rate is required for currency conversion")
            converted.append(
                GapValue(
                    period_start=gap.period_start,
                    period_end=gap.period_end,
                    net_gap=gap.net_gap * rate,
                    gross_inflow=gap.gross_inflow * rate,
                    gross_outflow=gap.gross_outflow * rate,
                    incremental_gap=gap.incremental_gap * rate,
                    cumulative_gap=gap.cumulative_gap * rate,
                    currency=target_currency,
                    bucket=gap.bucket,
                    scenario=gap.scenario,
                )
            )
        return tuple(converted)

    def _normalize_gap_type(self, gap_type: str | None) -> str:
        normalized = (gap_type or "net").strip().lower()
        if normalized in {
            "net",
            "gross",
            "incremental",
            "cumulative",
            "contractual",
            "behavioral",
            "scenario",
        }:
            return normalized
        return "net"

    def _summary_value_for(self, gap_type: str | None, net_gap: Decimal) -> Decimal:
        normalized = self._normalize_gap_type(gap_type)
        if normalized in {"contractual", "behavioral", "scenario"}:
            return Decimal("0")
        return net_gap

    def _sanitize_projection_request(self, request: ProjectionRequest) -> ProjectionRequest:
        sanitized_cashflows = tuple(
            type(cashflow)(
                payment_date=cashflow.payment_date,
                amount=abs(cashflow.amount),
                currency=cashflow.currency,
                cash_flow_type=getattr(cashflow, "cash_flow_type", "coupon"),
                source_reference=getattr(cashflow, "source_reference", None),
            )
            for cashflow in request.contractual_cashflows
        )
        return ProjectionRequest(
            valuation_date=request.valuation_date,
            contractual_cashflows=sanitized_cashflows,
            behavioral_assumptions=request.behavioral_assumptions,
            scenario_name=request.scenario_name,
            portfolio_reference=request.portfolio_reference,
            business_unit=request.business_unit,
            currency=request.currency,
            product_type=request.product_type,
            counterparty=request.counterparty,
            instrument_id=request.instrument_id,
            projection_type=request.projection_type,
            behavioral_provider=request.behavioral_provider,
            scenario_provider=request.scenario_provider,
            rollover_provider=request.rollover_provider,
            assumptions=request.assumptions,
            warnings=request.warnings,
            references=request.references,
            configuration=request.configuration,
        )
