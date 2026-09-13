from __future__ import annotations

from datetime import date

from aip.domain.irrbb.models import (
    BankingBookPosition,
    IRRBBCashFlow,
    IRRBBInstrumentClass,
    IRRBBScenario,
    OptionalityType,
    PaymentStructure,
    RateType,
)
from aip.domain.irrbb.ports import (
    BehavioralCashFlowModel,
    RepricingCashFlowBuilderResolver,
    ScenarioCashFlowProjector,
)


class StandardScenarioPositionCashFlowProvider:
    """Prepare final per-position cash flows for BASE and stressed EVE.

    Supported pathways are intentionally narrow and auditable:

    - ordinary fixed-rate positions use their contractual schedule unchanged;
    - ordinary floating-rate positions use the injected scenario projector in stress;
    - non-maturity deposits use an approved behavioral model;
    - other material optionality is rejected until an integrated instrument-specific
      scenario strategy is approved.

    This avoids assuming that prepayment, early withdrawal and floating-rate
    repricing can always be applied in the same order.
    """

    def __init__(
        self,
        *,
        builder_resolver: RepricingCashFlowBuilderResolver,
        scenario_projector: ScenarioCashFlowProjector | None = None,
        nmd_behavioral_model: BehavioralCashFlowModel | None = None,
    ) -> None:
        self._builder_resolver = builder_resolver
        self._scenario_projector = scenario_projector
        self._nmd_behavioral_model = nmd_behavioral_model

    def cashflows_for(
        self,
        *,
        position: BankingBookPosition,
        scenario: IRRBBScenario,
        valuation_date: date,
    ) -> tuple[IRRBBCashFlow, ...]:
        if self._is_nmd(position):
            return self._nmd_cashflows(
                position=position,
                scenario=scenario,
                valuation_date=valuation_date,
            )

        if position.optionality is not OptionalityType.NONE:
            raise ValueError(
                f"position {position.position_id} has optionality {position.optionality.value}; "
                "an integrated scenario-specific behavioral strategy is required"
            )

        builder = self._builder_resolver.resolve(position=position)
        base_cashflows = builder.build(position=position, valuation_date=valuation_date)
        self._validate_cashflows(position=position, cashflows=base_cashflows)

        if scenario is IRRBBScenario.BASE or position.rate_type is RateType.FIXED:
            return base_cashflows

        if self._scenario_projector is None:
            raise ValueError(
                f"floating-rate position {position.position_id} requires a scenario cash-flow projector"
            )

        projected = self._scenario_projector.project(
            position=position,
            base_cashflows=base_cashflows,
            scenario=scenario,
            valuation_date=valuation_date,
        )
        self._validate_cashflows(position=position, cashflows=projected)
        return projected

    def _nmd_cashflows(
        self,
        *,
        position: BankingBookPosition,
        scenario: IRRBBScenario,
        valuation_date: date,
    ) -> tuple[IRRBBCashFlow, ...]:
        if self._nmd_behavioral_model is None:
            raise ValueError(
                f"non-maturity deposit {position.position_id} requires an approved behavioral model"
            )
        result = self._nmd_behavioral_model.apply(
            position=position,
            contractual_cashflows=(),
            scenario=scenario,
            valuation_date=valuation_date,
        )
        self._validate_cashflows(position=position, cashflows=result)
        return result

    @staticmethod
    def _is_nmd(position: BankingBookPosition) -> bool:
        return (
            position.instrument_class is IRRBBInstrumentClass.NON_MATURITY_DEPOSIT
            or position.payment_structure is PaymentStructure.NON_MATURITY
            or position.optionality is OptionalityType.NON_MATURITY_DEPOSIT
        )

    @staticmethod
    def _validate_cashflows(
        *,
        position: BankingBookPosition,
        cashflows: tuple[IRRBBCashFlow, ...],
    ) -> None:
        for flow in cashflows:
            if flow.position_id != position.position_id:
                raise ValueError("scenario cash flow belongs to a different position")
            if flow.amount.currency is not position.currency:
                raise ValueError("scenario cash-flow currency must match position currency")
