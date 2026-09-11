from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.domain.irrbb.models import IRRBBScenario
from aip.domain.irrbb.nii import DeltaNIIResult, NetInterestIncomeResult, NIIProjectionBasis
from aip.domain.irrbb.nii_certification import (
    NIIProjectionCertificationResult,
    NIIProjectionCertificationStatus,
)
from aip.shared.money import Currency


class NIIScenarioSetEvaluationStatus(str, Enum):
    """Portfolio-level outcome of explicit multi-scenario NII evaluation."""

    EVALUATED = "EVALUATED"
    BLOCKED = "BLOCKED"
    NO_INCLUDED_POSITIONS = "NO_INCLUDED_POSITIONS"


@dataclass(frozen=True, slots=True)
class NIIScenarioSetEvaluationResult:
    """Auditable result for BASE plus an explicit set of stressed NII scenarios."""

    basis: NIIProjectionBasis
    reporting_currency: Currency
    required_stressed_scenarios: tuple[IRRBBScenario, ...]
    status: NIIScenarioSetEvaluationStatus
    certifications: tuple[NIIProjectionCertificationResult, ...]
    scenario_results: tuple[NetInterestIncomeResult, ...] = ()
    delta_nii: DeltaNIIResult | None = None

    def __post_init__(self) -> None:
        if not self.required_stressed_scenarios:
            raise ValueError("NII scenario set requires stressed scenarios")
        if IRRBBScenario.BASE in self.required_stressed_scenarios:
            raise ValueError("NII stressed scenarios cannot include BASE")
        if len(set(self.required_stressed_scenarios)) != len(self.required_stressed_scenarios):
            raise ValueError("NII stressed scenarios cannot contain duplicates")

        expected_scenarios = (IRRBBScenario.BASE, *self.required_stressed_scenarios)
        observed_certification_scenarios = tuple(item.scenario for item in self.certifications)
        if observed_certification_scenarios != expected_scenarios:
            raise ValueError("NII certifications must match the exact requested scenario order")
        if any(item.basis != self.basis for item in self.certifications):
            raise ValueError("NII certifications must use the requested projection basis")

        blocked = tuple(
            item
            for item in self.certifications
            if item.status is NIIProjectionCertificationStatus.BLOCKED
        )
        excluded = tuple(
            item
            for item in self.certifications
            if item.status is NIIProjectionCertificationStatus.NO_INCLUDED_POSITIONS
        )
        projected = tuple(
            item
            for item in self.certifications
            if item.status is NIIProjectionCertificationStatus.PROJECTED
        )

        if self.status is NIIScenarioSetEvaluationStatus.BLOCKED:
            if not blocked:
                raise ValueError("BLOCKED NII scenario set requires a blocked certification")
            if self.scenario_results or self.delta_nii is not None:
                raise ValueError("BLOCKED NII scenario set cannot contain NII results")
            return

        if self.status is NIIScenarioSetEvaluationStatus.NO_INCLUDED_POSITIONS:
            if len(excluded) != len(self.certifications):
                raise ValueError(
                    "NO_INCLUDED_POSITIONS requires every scenario certification to be excluded"
                )
            if self.scenario_results or self.delta_nii is not None:
                raise ValueError("excluded-only NII scenario set cannot contain NII results")
            return

        if blocked or excluded:
            raise ValueError("EVALUATED NII scenario set requires every certification PROJECTED")
        if len(projected) != len(self.certifications):
            raise ValueError("EVALUATED NII scenario set requires projected certifications")

        observed_result_scenarios = tuple(item.scenario for item in self.scenario_results)
        if observed_result_scenarios != expected_scenarios:
            raise ValueError("NII results must match the exact requested scenario order")
        if any(item.basis != self.basis for item in self.scenario_results):
            raise ValueError("NII results must use the requested projection basis")
        if any(item.reporting_currency is not self.reporting_currency for item in self.scenario_results):
            raise ValueError("NII results must use the requested reporting currency")
        if self.delta_nii is None:
            raise ValueError("EVALUATED NII scenario set requires delta_nii")
        if self.delta_nii.basis != self.basis:
            raise ValueError("delta NII substituted projection basis")
        if self.delta_nii.reporting_currency is not self.reporting_currency:
            raise ValueError("delta NII substituted reporting currency")
        observed_delta_scenarios = tuple(item.scenario for item in self.delta_nii.assessments)
        if observed_delta_scenarios != self.required_stressed_scenarios:
            raise ValueError("delta NII assessments must match the requested stressed scenarios")
