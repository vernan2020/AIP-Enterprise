from __future__ import annotations

from dataclasses import dataclass

from aip.domain.irrbb.nii_audit_physical_adapter_production_promotion import (
    NIIRunAuditPhysicalAdapterProductionPromotionAuthorization,
)


class NIIRunAuditPhysicalAdapterProductionDeploymentPlanError(ValueError):
    """Raised when a production deployment plan cannot be built safely."""


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionDeploymentStep:
    """One declarative, non-executable instruction reference in a deployment plan."""

    sequence: int
    instruction_reference: str

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError(
                "NII audit physical adapter production deployment step sequence must be positive"
            )
        if not self.instruction_reference.strip():
            raise ValueError(
                "NII audit physical adapter production deployment step instruction_reference is required"
            )


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionDeploymentPlan:
    """Immutable deployment plan for one explicitly authorized production promotion."""

    promotion_authorization: NIIRunAuditPhysicalAdapterProductionPromotionAuthorization
    plan_reference: str
    release_reference: str
    change_reference: str
    artifact_reference: str
    rollback_reference: str
    steps: tuple[NIIRunAuditPhysicalAdapterProductionDeploymentStep, ...]

    def __post_init__(self) -> None:
        required_references = {
            "plan_reference": self.plan_reference,
            "release_reference": self.release_reference,
            "change_reference": self.change_reference,
            "artifact_reference": self.artifact_reference,
            "rollback_reference": self.rollback_reference,
        }
        for name, value in required_references.items():
            if not value.strip():
                raise ValueError(
                    f"NII audit physical adapter production deployment {name} is required"
                )

        if not self.steps:
            raise ValueError(
                "NII audit physical adapter production deployment plan requires at least one step"
            )

        sequences = tuple(step.sequence for step in self.steps)
        expected_sequences = tuple(range(1, len(self.steps) + 1))
        if sequences != expected_sequences:
            raise ValueError(
                "NII audit physical adapter production deployment steps must be contiguous and canonical"
            )

        instruction_references = tuple(step.instruction_reference for step in self.steps)
        if len(instruction_references) != len(set(instruction_references)):
            raise ValueError(
                "Duplicate NII audit physical adapter production deployment instruction_reference"
            )

    @property
    def adapter_reference(self) -> str:
        return self.promotion_authorization.adapter_reference

    @property
    def environment_reference(self) -> str:
        return self.promotion_authorization.environment_reference

    @property
    def authorization_reference(self) -> str:
        return self.promotion_authorization.authorization_reference
