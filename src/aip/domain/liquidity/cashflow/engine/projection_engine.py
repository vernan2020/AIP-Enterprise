from __future__ import annotations

from aip.domain.liquidity.cashflow.calculators.behavioral_projection import BehavioralProjection
from aip.domain.liquidity.cashflow.calculators.contractual_projection import ContractualProjection
from aip.domain.liquidity.cashflow.exceptions import BehavioralError
from aip.domain.liquidity.cashflow.models.projected_cashflow import ProjectedCashFlow
from aip.domain.liquidity.cashflow.models.projection_request import ProjectionRequest


class ProjectionEngine:
    """Coordinate contractual and behavioral projection steps."""

    def __init__(self) -> None:
        self._contractual_projection = ContractualProjection()
        self._behavioral_projection = BehavioralProjection()

    def project(self, request: ProjectionRequest) -> tuple[ProjectedCashFlow, ...]:
        if request.behavioral_provider is not None:
            try:
                assumptions = request.behavioral_provider.get_behavioral_assumptions(request)
            except Exception as exc:
                raise BehavioralError("Behavioral provider failed") from exc
            request = ProjectionRequest(
                valuation_date=request.valuation_date,
                contractual_cashflows=request.contractual_cashflows,
                behavioral_assumptions=assumptions,
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
        try:
            contract_result = self._contractual_projection.project(request)
        except Exception as exc:
            if request.behavioral_provider is not None:
                raise BehavioralError("Behavioral projection failed") from exc
            raise
        if request.behavioral_assumptions:
            try:
                return self._behavioral_projection.project(request, [contract_result])
            except Exception as exc:
                raise BehavioralError("Behavioral projection failed") from exc
        return contract_result
