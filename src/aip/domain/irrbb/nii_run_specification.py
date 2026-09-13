from __future__ import annotations

from dataclasses import dataclass

from aip.domain.irrbb.models import IRRBBScenario
from aip.domain.irrbb.nii import NIIProjectionBasis
from aip.domain.irrbb.nii_scenario_set import NIIScenarioSetEvaluationResult
from aip.shared.money import Currency


@dataclass(frozen=True, slots=True)
class NIIMethodologyRunSpecification:
    """Immutable governance contract for one explicit Delta NII methodology run."""

    run_reference: str
    basis: NIIProjectionBasis
    reporting_currency: Currency
    stressed_scenarios: tuple[IRRBBScenario, ...]
    policy_references: tuple[str, ...]
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.run_reference.strip():
            raise ValueError("NII run_reference is required")
        if not self.stressed_scenarios:
            raise ValueError("NII methodology run requires stressed scenarios")
        if IRRBBScenario.BASE in self.stressed_scenarios:
            raise ValueError("NII methodology run stressed scenarios cannot include BASE")
        if len(set(self.stressed_scenarios)) != len(self.stressed_scenarios):
            raise ValueError("NII methodology run stressed scenarios cannot contain duplicates")
        self._validate_references("policy", self.policy_references)
        self._validate_references("evidence", self.evidence_references)

    @staticmethod
    def _validate_references(kind: str, references: tuple[str, ...]) -> None:
        if not references:
            raise ValueError(f"NII methodology run requires {kind} references")
        if any(not reference.strip() for reference in references):
            raise ValueError(f"NII methodology run {kind} references cannot be blank")
        if len(set(references)) != len(references):
            raise ValueError(f"NII methodology run {kind} references cannot contain duplicates")


@dataclass(frozen=True, slots=True)
class NIIMethodologyRunResult:
    """Scenario-set evaluation bound to the exact methodology run specification."""

    specification: NIIMethodologyRunSpecification
    evaluation: NIIScenarioSetEvaluationResult

    def __post_init__(self) -> None:
        if self.evaluation.basis != self.specification.basis:
            raise ValueError("NII methodology run result substituted projection basis")
        if self.evaluation.reporting_currency is not self.specification.reporting_currency:
            raise ValueError("NII methodology run result substituted reporting currency")
        if self.evaluation.required_stressed_scenarios != self.specification.stressed_scenarios:
            raise ValueError("NII methodology run result substituted stressed scenarios")
