from __future__ import annotations

from datetime import date

from aip.domain.irrbb.models import (
    STANDARD_STRESS_SCENARIOS,
    BankingBookPosition,
    EconomicValueResult,
    IRRBBCashFlow,
    IRRBBMethodologyProfile,
    IRRBBScenario,
)
from aip.domain.irrbb.ports import (
    DiscountFactorProvider,
    ExchangeRateProvider,
    ScenarioPositionCashFlowProvider,
)
from aip.domain.irrbb.scenario_evaluation import IRRBBScenarioEvaluationResult
from aip.domain.irrbb.services.delta_eve_service import DeltaEVEExposureService
from aip.domain.irrbb.services.economic_value_service import EconomicValueService
from aip.shared.money import Currency, Money


class IRRBBScenarioEvaluationService:
    """Orchestrate BASE + stressed EVE and Delta EVE for calculation-ready positions.

    This service does not construct source records, curves or instrument schedules.
    It consumes final scenario cash flows and market-data ports, preserving strict
    separation from the SUGEF repricing-GAP calculation path.
    """

    def __init__(
        self,
        *,
        scenario_cashflows: ScenarioPositionCashFlowProvider,
        discount_factors: DiscountFactorProvider,
        exchange_rates: ExchangeRateProvider | None = None,
    ) -> None:
        self._scenario_cashflows = scenario_cashflows
        self._discount_factors = discount_factors
        self._exchange_rates = exchange_rates

    def evaluate(
        self,
        *,
        positions: tuple[BankingBookPosition, ...],
        valuation_date: date,
        reporting_currency: Currency,
        tier_one_capital: Money,
        methodology: IRRBBMethodologyProfile,
        required_scenarios: tuple[IRRBBScenario, ...] = STANDARD_STRESS_SCENARIOS,
    ) -> IRRBBScenarioEvaluationResult:
        self._validate_positions(positions)
        self._validate_required_scenarios(required_scenarios)

        base = self._evaluate_scenario(
            positions=positions,
            valuation_date=valuation_date,
            reporting_currency=reporting_currency,
            scenario=IRRBBScenario.BASE,
        )
        stressed = tuple(
            self._evaluate_scenario(
                positions=positions,
                valuation_date=valuation_date,
                reporting_currency=reporting_currency,
                scenario=scenario,
            )
            for scenario in required_scenarios
        )
        exposure = DeltaEVEExposureService.calculate(
            base=base,
            stressed=stressed,
            tier_one_capital=tier_one_capital,
            required_scenarios=required_scenarios,
        )
        return IRRBBScenarioEvaluationResult(
            methodology=methodology,
            valuation_date=valuation_date,
            reporting_currency=reporting_currency,
            position_count=len(positions),
            base=base,
            stressed=stressed,
            exposure=exposure,
        )

    def _evaluate_scenario(
        self,
        *,
        positions: tuple[BankingBookPosition, ...],
        valuation_date: date,
        reporting_currency: Currency,
        scenario: IRRBBScenario,
    ) -> EconomicValueResult:
        cashflows: list[IRRBBCashFlow] = []
        for position in positions:
            position_flows = self._scenario_cashflows.cashflows_for(
                position=position,
                scenario=scenario,
                valuation_date=valuation_date,
            )
            self._validate_position_cashflows(position=position, cashflows=position_flows)
            cashflows.extend(position_flows)

        ordered = tuple(
            sorted(
                cashflows,
                key=lambda flow: (
                    flow.cashflow_date,
                    flow.position_id,
                    flow.flow_type,
                    flow.source_reference,
                ),
            )
        )
        return EconomicValueService.calculate(
            cashflows=ordered,
            valuation_date=valuation_date,
            scenario=scenario,
            reporting_currency=reporting_currency,
            discount_factors=self._discount_factors,
            exchange_rates=self._exchange_rates,
        )

    @staticmethod
    def _validate_positions(positions: tuple[BankingBookPosition, ...]) -> None:
        if not positions:
            raise ValueError("IRRBB scenario evaluation requires at least one position")
        identifiers = tuple(position.position_id for position in positions)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("IRRBB scenario evaluation position_id values must be unique")

    @staticmethod
    def _validate_required_scenarios(required_scenarios: tuple[IRRBBScenario, ...]) -> None:
        if not required_scenarios:
            raise ValueError("IRRBB scenario evaluation requires at least one stress scenario")
        if IRRBBScenario.BASE in required_scenarios:
            raise ValueError("required stress scenarios cannot contain BASE")
        if len(set(required_scenarios)) != len(required_scenarios):
            raise ValueError("required stress scenarios cannot contain duplicates")

    @staticmethod
    def _validate_position_cashflows(
        *,
        position: BankingBookPosition,
        cashflows: tuple[IRRBBCashFlow, ...],
    ) -> None:
        if not cashflows:
            raise ValueError(
                f"calculation-ready position {position.position_id} produced no scenario cash flows"
            )
        for flow in cashflows:
            if flow.position_id != position.position_id:
                raise ValueError("scenario provider returned a cash flow for a different position")
            if flow.amount.currency is not position.currency:
                raise ValueError("scenario provider returned a cash flow in a different currency")
