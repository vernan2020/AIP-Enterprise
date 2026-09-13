from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorization,
)


class NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceiptError(ValueError):
    """Raised when an operational recovery receipt cannot be recorded safely."""


class NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpoint(str, Enum):
    """Externally observed checkpoints for one authorized return-to-service action."""

    AUTHORIZATION_ACKNOWLEDGED = "AUTHORIZATION_ACKNOWLEDGED"
    RECOVERY_ACTION_APPLIED = "RECOVERY_ACTION_APPLIED"
    TARGET_STATE_VERIFIED = "TARGET_STATE_VERIFIED"
    CONTINUITY_CONTROL_CONFIRMED = "CONTINUITY_CONTROL_CONFIRMED"


NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINT_ORDER = (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpoint.AUTHORIZATION_ACKNOWLEDGED,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpoint.RECOVERY_ACTION_APPLIED,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpoint.TARGET_STATE_VERIFIED,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpoint.CONTINUITY_CONTROL_CONFIRMED,
)

REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINTS = frozenset(
    NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINT_ORDER
)


class NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus(str, Enum):
    """Observed result of one operational recovery checkpoint."""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    NOT_EXECUTED = "NOT_EXECUTED"


class NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus(str, Enum):
    """Derived overall result of one authorized return-to-service attempt."""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointResult:
    """Traceable externally observed result for one recovery checkpoint."""

    checkpoint: NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpoint
    status: NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus
    evidence_reference: str

    def __post_init__(self) -> None:
        if not self.evidence_reference.strip():
            raise ValueError(
                "NII audit operational recovery checkpoint evidence_reference is required"
            )


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceipt:
    """Immutable receipt for externally observed return-to-service outcomes."""

    recovery_authorization: NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorization
    receipt_reference: str
    recovery_reference: str
    status: NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus
    checkpoint_results: tuple[
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointResult, ...
    ]

    def __post_init__(self) -> None:
        required_references = {
            "receipt_reference": self.receipt_reference,
            "recovery_reference": self.recovery_reference,
        }
        for name, value in required_references.items():
            if not value.strip():
                raise ValueError(f"NII audit operational recovery {name} is required")

        checkpoints = tuple(item.checkpoint for item in self.checkpoint_results)
        if len(checkpoints) != len(set(checkpoints)):
            raise ValueError("Duplicate NII audit operational recovery checkpoint result")
        if (
            frozenset(checkpoints)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINTS
        ):
            raise ValueError(
                "NII audit operational recovery checkpoint results must cover every required checkpoint"
            )
        if checkpoints != NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINT_ORDER:
            raise ValueError(
                "NII audit operational recovery checkpoint results must be canonicalized"
            )

        derived_status = (
            NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus.SUCCEEDED
            if all(
                result.status
                is NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus.SUCCEEDED
                for result in self.checkpoint_results
            )
            else NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus.FAILED
        )
        if self.status is not derived_status:
            raise ValueError("NII audit operational recovery status must match checkpoint results")

    @property
    def authorization_reference(self) -> str:
        return self.recovery_authorization.authorization_reference

    @property
    def action(self) -> NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction:
        return self.recovery_authorization.action

    @property
    def intervention_acceptance_reference(self) -> str:
        return self.recovery_authorization.intervention_acceptance_reference

    @property
    def intervention_receipt_reference(self) -> str:
        return self.recovery_authorization.intervention_receipt_reference

    @property
    def intervention_reference(self) -> str:
        return self.recovery_authorization.intervention_reference

    @property
    def intervention_authorization_reference(self) -> str:
        return self.recovery_authorization.intervention_authorization_reference

    @property
    def intervention_action(self) -> NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction:
        return self.recovery_authorization.intervention_action

    @property
    def attestation_reference(self) -> str:
        return self.recovery_authorization.attestation_reference

    @property
    def operations_reference(self) -> str:
        return self.recovery_authorization.operations_reference

    @property
    def adapter_reference(self) -> str:
        return self.recovery_authorization.adapter_reference

    @property
    def environment_reference(self) -> str:
        return self.recovery_authorization.environment_reference

    @property
    def artifact_reference(self) -> str:
        return self.recovery_authorization.artifact_reference
