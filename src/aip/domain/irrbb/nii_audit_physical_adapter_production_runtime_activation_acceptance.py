from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.domain.irrbb.nii_audit_physical_adapter_production_runtime_activation_receipt import (
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceipt,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationStatus,
)


class NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceError(ValueError):
    """Raised when runtime activation acceptance cannot be issued safely."""


class NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceRequirement(str, Enum):
    """Evidence required before an activated production runtime may be accepted."""

    ACTIVATION_RECEIPT_VERIFIED = "ACTIVATION_RECEIPT_VERIFIED"
    RUNTIME_STABILITY_VALIDATED = "RUNTIME_STABILITY_VALIDATED"
    OBSERVABILITY_VALIDATED = "OBSERVABILITY_VALIDATED"
    OPERATIONS_OWNERSHIP_ACCEPTED = "OPERATIONS_OWNERSHIP_ACCEPTED"
    SUPPORT_HANDOVER_CONFIRMED = "SUPPORT_HANDOVER_CONFIRMED"


REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_ACCEPTANCE_REQUIREMENTS = (
    frozenset(NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceRequirement)
)


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceEvidence:
    """Traceable evidence for one runtime-activation acceptance requirement."""

    requirement: NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceRequirement
    source_reference: str

    def __post_init__(self) -> None:
        if not self.source_reference.strip():
            raise ValueError(
                "NII audit physical adapter production runtime activation acceptance evidence "
                "source_reference is required"
            )


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptance:
    """Positive-only acceptance of one exact successful runtime activation receipt."""

    activation_receipt: NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceipt
    acceptance_reference: str
    evidence: tuple[NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceEvidence, ...]

    def __post_init__(self) -> None:
        if (
            self.activation_receipt.status
            is not NIIRunAuditPhysicalAdapterProductionRuntimeActivationStatus.SUCCEEDED
        ):
            raise ValueError(
                "NII audit physical adapter production runtime activation acceptance requires "
                "a successful activation receipt"
            )
        if not all(
            result.status
            is NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointStatus.SUCCEEDED
            for result in self.activation_receipt.checkpoint_results
        ):
            raise ValueError(
                "NII audit physical adapter production runtime activation acceptance requires "
                "every activation checkpoint to succeed"
            )
        if not self.acceptance_reference.strip():
            raise ValueError(
                "NII audit physical adapter production runtime activation "
                "acceptance_reference is required"
            )

        evidence_requirements = tuple(item.requirement for item in self.evidence)
        if len(evidence_requirements) != len(set(evidence_requirements)):
            raise ValueError(
                "Duplicate NII audit physical adapter production runtime activation "
                "acceptance evidence requirement"
            )
        if (
            frozenset(evidence_requirements)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_ACCEPTANCE_REQUIREMENTS
        ):
            raise ValueError(
                "NII audit physical adapter production runtime activation acceptance evidence "
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
                "NII audit physical adapter production runtime activation acceptance evidence "
                "must be canonicalized"
            )

    @property
    def runtime_activation_receipt_reference(self) -> str:
        return self.activation_receipt.receipt_reference

    @property
    def activation_reference(self) -> str:
        return self.activation_receipt.activation_reference

    @property
    def activation_authorization_reference(self) -> str:
        return self.activation_receipt.activation_authorization_reference

    @property
    def post_execution_acceptance_reference(self) -> str:
        return self.activation_receipt.acceptance_reference

    @property
    def deployment_receipt_reference(self) -> str:
        return self.activation_receipt.deployment_receipt_reference

    @property
    def deployment_execution_reference(self) -> str:
        return self.activation_receipt.deployment_execution_reference

    @property
    def deployment_execution_authorization_reference(self) -> str:
        return self.activation_receipt.deployment_execution_authorization_reference

    @property
    def plan_reference(self) -> str:
        return self.activation_receipt.plan_reference

    @property
    def adapter_reference(self) -> str:
        return self.activation_receipt.adapter_reference

    @property
    def environment_reference(self) -> str:
        return self.activation_receipt.environment_reference

    @property
    def artifact_reference(self) -> str:
        return self.activation_receipt.artifact_reference

    @property
    def planned_rollback_reference(self) -> str:
        return self.activation_receipt.planned_rollback_reference
