from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.domain.irrbb.nii_audit_physical_adapter_production_deployment_execution_authorization import (
    NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorization,
)


class NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceiptError(ValueError):
    """Raised when a deployment execution receipt cannot be recorded safely."""


class NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus(str, Enum):
    """Observed result of one authorized deployment-plan step."""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    NOT_EXECUTED = "NOT_EXECUTED"


class NIIRunAuditPhysicalAdapterProductionDeploymentExecutionStatus(str, Enum):
    """Derived overall result of the authorized deployment execution."""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class NIIRunAuditPhysicalAdapterProductionDeploymentRollbackStatus(str, Enum):
    """Observed rollback state associated with a failed or completed execution."""

    NOT_REQUIRED = "NOT_REQUIRED"
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionDeploymentStepResult:
    """Traceable result for one step in the exact authorized deployment plan."""

    sequence: int
    status: NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus
    evidence_reference: str

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError(
                "NII audit physical adapter production deployment step result sequence must be positive"
            )
        if not self.evidence_reference.strip():
            raise ValueError(
                "NII audit physical adapter production deployment step result evidence_reference is required"
            )


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceipt:
    """Immutable receipt for the externally observed result of one authorized plan."""

    execution_authorization: NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorization
    receipt_reference: str
    execution_reference: str
    status: NIIRunAuditPhysicalAdapterProductionDeploymentExecutionStatus
    step_results: tuple[NIIRunAuditPhysicalAdapterProductionDeploymentStepResult, ...]
    rollback_status: NIIRunAuditPhysicalAdapterProductionDeploymentRollbackStatus
    rollback_evidence_reference: str

    def __post_init__(self) -> None:
        required_references = {
            "receipt_reference": self.receipt_reference,
            "execution_reference": self.execution_reference,
            "rollback_evidence_reference": self.rollback_evidence_reference,
        }
        for name, value in required_references.items():
            if not value.strip():
                raise ValueError(
                    f"NII audit physical adapter production deployment execution {name} is required"
                )

        expected_sequences = tuple(
            step.sequence
            for step in self.execution_authorization.deployment_plan.steps
        )
        result_sequences = tuple(result.sequence for result in self.step_results)
        if result_sequences != expected_sequences:
            raise ValueError(
                "NII audit physical adapter production deployment execution step results must exactly cover the authorized plan in canonical order"
            )

        derived_status = (
            NIIRunAuditPhysicalAdapterProductionDeploymentExecutionStatus.SUCCEEDED
            if all(
                result.status
                is NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus.SUCCEEDED
                for result in self.step_results
            )
            else NIIRunAuditPhysicalAdapterProductionDeploymentExecutionStatus.FAILED
        )
        if self.status is not derived_status:
            raise ValueError(
                "NII audit physical adapter production deployment execution status must match step results"
            )

        if (
            self.status
            is NIIRunAuditPhysicalAdapterProductionDeploymentExecutionStatus.SUCCEEDED
            and self.rollback_status
            is not NIIRunAuditPhysicalAdapterProductionDeploymentRollbackStatus.NOT_REQUIRED
        ):
            raise ValueError(
                "Successful NII audit physical adapter production deployment execution cannot require rollback"
            )

    @property
    def execution_authorization_reference(self) -> str:
        return self.execution_authorization.execution_authorization_reference

    @property
    def plan_reference(self) -> str:
        return self.execution_authorization.plan_reference

    @property
    def adapter_reference(self) -> str:
        return self.execution_authorization.adapter_reference

    @property
    def environment_reference(self) -> str:
        return self.execution_authorization.environment_reference

    @property
    def artifact_reference(self) -> str:
        return self.execution_authorization.artifact_reference

    @property
    def planned_rollback_reference(self) -> str:
        return self.execution_authorization.rollback_reference
