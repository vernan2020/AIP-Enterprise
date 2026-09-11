from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.domain.irrbb.nii_audit_physical_adapter_production_deployment_execution_receipt import (
    NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceipt,
    NIIRunAuditPhysicalAdapterProductionDeploymentExecutionStatus,
    NIIRunAuditPhysicalAdapterProductionDeploymentRollbackStatus,
)


class NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceError(ValueError):
    """Raised when post-execution acceptance cannot be issued safely."""


class NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceRequirement(str, Enum):
    """Evidence required before a successful deployment may be accepted."""

    EXECUTION_RECEIPT_VERIFIED = "EXECUTION_RECEIPT_VERIFIED"
    POST_DEPLOYMENT_VALIDATION_COMPLETED = "POST_DEPLOYMENT_VALIDATION_COMPLETED"
    OPERATIONAL_HEALTH_CONFIRMED = "OPERATIONAL_HEALTH_CONFIRMED"
    OBSERVABILITY_CONFIRMED = "OBSERVABILITY_CONFIRMED"
    CHANGE_CLOSURE_RECORDED = "CHANGE_CLOSURE_RECORDED"


REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_POST_EXECUTION_ACCEPTANCE_REQUIREMENTS = (
    frozenset(NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceRequirement)
)


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceEvidence:
    """Traceable evidence for one post-execution acceptance requirement."""

    requirement: NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceRequirement
    source_reference: str

    def __post_init__(self) -> None:
        if not self.source_reference.strip():
            raise ValueError(
                "NII audit physical adapter production post-execution acceptance evidence "
                "source_reference is required"
            )


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptance:
    """Positive-only acceptance of one exact successful deployment receipt."""

    execution_receipt: NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceipt
    acceptance_reference: str
    evidence: tuple[
        NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceEvidence, ...
    ]

    def __post_init__(self) -> None:
        if (
            self.execution_receipt.status
            is not NIIRunAuditPhysicalAdapterProductionDeploymentExecutionStatus.SUCCEEDED
        ):
            raise ValueError(
                "NII audit physical adapter production post-execution acceptance requires "
                "a successful execution receipt"
            )
        if (
            self.execution_receipt.rollback_status
            is not NIIRunAuditPhysicalAdapterProductionDeploymentRollbackStatus.NOT_REQUIRED
        ):
            raise ValueError(
                "NII audit physical adapter production post-execution acceptance requires "
                "rollback status NOT_REQUIRED"
            )
        if not self.acceptance_reference.strip():
            raise ValueError(
                "NII audit physical adapter production post-execution acceptance_reference "
                "is required"
            )

        evidence_requirements = tuple(item.requirement for item in self.evidence)
        if len(evidence_requirements) != len(set(evidence_requirements)):
            raise ValueError(
                "Duplicate NII audit physical adapter production post-execution acceptance "
                "evidence requirement"
            )
        if (
            frozenset(evidence_requirements)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_POST_EXECUTION_ACCEPTANCE_REQUIREMENTS
        ):
            raise ValueError(
                "NII audit physical adapter production post-execution acceptance evidence "
                "must cover every required acceptance"
            )

        canonical_evidence = tuple(
            sorted(
                self.evidence,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        if self.evidence != canonical_evidence:
            raise ValueError(
                "NII audit physical adapter production post-execution acceptance evidence "
                "must be canonicalized"
            )

    @property
    def receipt_reference(self) -> str:
        return self.execution_receipt.receipt_reference

    @property
    def execution_reference(self) -> str:
        return self.execution_receipt.execution_reference

    @property
    def execution_authorization_reference(self) -> str:
        return self.execution_receipt.execution_authorization_reference

    @property
    def plan_reference(self) -> str:
        return self.execution_receipt.plan_reference

    @property
    def adapter_reference(self) -> str:
        return self.execution_receipt.adapter_reference

    @property
    def environment_reference(self) -> str:
        return self.execution_receipt.environment_reference

    @property
    def artifact_reference(self) -> str:
        return self.execution_receipt.artifact_reference

    @property
    def planned_rollback_reference(self) -> str:
        return self.execution_receipt.planned_rollback_reference
