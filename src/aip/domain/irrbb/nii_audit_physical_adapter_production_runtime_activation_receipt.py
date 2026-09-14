from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.domain.irrbb.nii_audit_physical_adapter_production_runtime_activation_authorization import (
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationAuthorization,
)


class NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceiptError(ValueError):
    """Raised when a runtime activation receipt cannot be recorded safely."""


class NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpoint(str, Enum):
    """Externally observed checkpoints for one authorized runtime activation."""

    DEPENDENCY_WIRING_APPLIED = "DEPENDENCY_WIRING_APPLIED"
    ADAPTER_REGISTRATION_CONFIRMED = "ADAPTER_REGISTRATION_CONFIRMED"
    STARTUP_SEQUENCE_COMPLETED = "STARTUP_SEQUENCE_COMPLETED"
    RUNTIME_HEALTH_CONFIRMED = "RUNTIME_HEALTH_CONFIRMED"


NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_CHECKPOINT_ORDER = (
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpoint.DEPENDENCY_WIRING_APPLIED,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpoint.ADAPTER_REGISTRATION_CONFIRMED,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpoint.STARTUP_SEQUENCE_COMPLETED,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpoint.RUNTIME_HEALTH_CONFIRMED,
)

REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_CHECKPOINTS = frozenset(
    NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_CHECKPOINT_ORDER
)


class NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointStatus(str, Enum):
    """Observed result of one runtime-activation checkpoint."""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    NOT_EXECUTED = "NOT_EXECUTED"


class NIIRunAuditPhysicalAdapterProductionRuntimeActivationStatus(str, Enum):
    """Derived overall result of one authorized runtime activation attempt."""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointResult:
    """Traceable externally observed result for one activation checkpoint."""

    checkpoint: NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpoint
    status: NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointStatus
    evidence_reference: str

    def __post_init__(self) -> None:
        if not self.evidence_reference.strip():
            raise ValueError(
                "NII audit physical adapter production runtime activation checkpoint "
                "evidence_reference is required"
            )


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceipt:
    """Immutable receipt for the externally observed result of one authorized activation."""

    activation_authorization: NIIRunAuditPhysicalAdapterProductionRuntimeActivationAuthorization
    receipt_reference: str
    activation_reference: str
    status: NIIRunAuditPhysicalAdapterProductionRuntimeActivationStatus
    checkpoint_results: tuple[
        NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointResult, ...
    ]

    def __post_init__(self) -> None:
        required_references = {
            "receipt_reference": self.receipt_reference,
            "activation_reference": self.activation_reference,
        }
        for name, value in required_references.items():
            if not value.strip():
                raise ValueError(
                    "NII audit physical adapter production runtime activation "
                    f"{name} is required"
                )

        result_checkpoints = tuple(item.checkpoint for item in self.checkpoint_results)
        if len(result_checkpoints) != len(set(result_checkpoints)):
            raise ValueError(
                "Duplicate NII audit physical adapter production runtime activation "
                "checkpoint result"
            )
        if (
            frozenset(result_checkpoints)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_CHECKPOINTS
        ):
            raise ValueError(
                "NII audit physical adapter production runtime activation checkpoint results "
                "must cover every required checkpoint"
            )
        if (
            result_checkpoints
            != NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_CHECKPOINT_ORDER
        ):
            raise ValueError(
                "NII audit physical adapter production runtime activation checkpoint results "
                "must be canonicalized"
            )

        derived_status = (
            NIIRunAuditPhysicalAdapterProductionRuntimeActivationStatus.SUCCEEDED
            if all(
                result.status
                is NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointStatus.SUCCEEDED
                for result in self.checkpoint_results
            )
            else NIIRunAuditPhysicalAdapterProductionRuntimeActivationStatus.FAILED
        )
        if self.status is not derived_status:
            raise ValueError(
                "NII audit physical adapter production runtime activation status must match "
                "checkpoint results"
            )

    @property
    def activation_authorization_reference(self) -> str:
        return self.activation_authorization.activation_authorization_reference

    @property
    def acceptance_reference(self) -> str:
        return self.activation_authorization.acceptance_reference

    @property
    def deployment_receipt_reference(self) -> str:
        return self.activation_authorization.receipt_reference

    @property
    def deployment_execution_reference(self) -> str:
        return self.activation_authorization.execution_reference

    @property
    def deployment_execution_authorization_reference(self) -> str:
        return self.activation_authorization.execution_authorization_reference

    @property
    def plan_reference(self) -> str:
        return self.activation_authorization.plan_reference

    @property
    def adapter_reference(self) -> str:
        return self.activation_authorization.adapter_reference

    @property
    def environment_reference(self) -> str:
        return self.activation_authorization.environment_reference

    @property
    def artifact_reference(self) -> str:
        return self.activation_authorization.artifact_reference

    @property
    def planned_rollback_reference(self) -> str:
        return self.activation_authorization.planned_rollback_reference
