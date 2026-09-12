from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorization,
)


class NIIRunAuditPhysicalAdapterProductionOperationalInterventionReceiptError(ValueError):
    """Raised when an intervention receipt cannot be recorded safely."""


class NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpoint(str, Enum):
    """Externally observed checkpoints for one authorized operational intervention."""

    AUTHORIZATION_ACKNOWLEDGED = "AUTHORIZATION_ACKNOWLEDGED"
    INTERVENTION_APPLIED = "INTERVENTION_APPLIED"
    RESULTING_STATE_VERIFIED = "RESULTING_STATE_VERIFIED"
    CONTINUITY_CONTROL_CONFIRMED = "CONTINUITY_CONTROL_CONFIRMED"


NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_CHECKPOINT_ORDER = (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpoint.AUTHORIZATION_ACKNOWLEDGED,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpoint.INTERVENTION_APPLIED,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpoint.RESULTING_STATE_VERIFIED,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpoint.CONTINUITY_CONTROL_CONFIRMED,
)

REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_CHECKPOINTS = frozenset(
    NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_CHECKPOINT_ORDER
)


class NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus(str, Enum):
    """Observed result of one intervention checkpoint."""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    NOT_EXECUTED = "NOT_EXECUTED"


class NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus(str, Enum):
    """Derived overall result of one authorized operational intervention attempt."""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointResult:
    """Traceable externally observed result for one intervention checkpoint."""

    checkpoint: NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpoint
    status: NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus
    evidence_reference: str

    def __post_init__(self) -> None:
        if not self.evidence_reference.strip():
            raise ValueError(
                "NII audit operational intervention checkpoint evidence_reference is required"
            )


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionOperationalInterventionReceipt:
    """Immutable receipt for externally observed intervention execution results."""

    intervention_authorization: (
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorization
    )
    receipt_reference: str
    intervention_reference: str
    status: NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus
    checkpoint_results: tuple[
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointResult, ...
    ]

    def __post_init__(self) -> None:
        required_references = {
            "receipt_reference": self.receipt_reference,
            "intervention_reference": self.intervention_reference,
        }
        for name, value in required_references.items():
            if not value.strip():
                raise ValueError(f"NII audit operational intervention {name} is required")

        checkpoints = tuple(item.checkpoint for item in self.checkpoint_results)
        if len(checkpoints) != len(set(checkpoints)):
            raise ValueError("Duplicate NII audit operational intervention checkpoint result")
        if (
            frozenset(checkpoints)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_CHECKPOINTS
        ):
            raise ValueError(
                "NII audit operational intervention checkpoint results must cover every "
                "required checkpoint"
            )
        if (
            checkpoints
            != NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_CHECKPOINT_ORDER
        ):
            raise ValueError(
                "NII audit operational intervention checkpoint results must be canonicalized"
            )

        derived_status = (
            NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus.SUCCEEDED
            if all(
                result.status
                is NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus.SUCCEEDED
                for result in self.checkpoint_results
            )
            else NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus.FAILED
        )
        if self.status is not derived_status:
            raise ValueError(
                "NII audit operational intervention status must match checkpoint results"
            )

    @property
    def authorization_reference(self) -> str:
        return self.intervention_authorization.authorization_reference

    @property
    def action(self) -> NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction:
        return self.intervention_authorization.action

    @property
    def attestation_reference(self) -> str:
        return self.intervention_authorization.attestation_reference

    @property
    def operations_reference(self) -> str:
        return self.intervention_authorization.operations_reference

    @property
    def adapter_reference(self) -> str:
        return self.intervention_authorization.adapter_reference

    @property
    def environment_reference(self) -> str:
        return self.intervention_authorization.environment_reference

    @property
    def artifact_reference(self) -> str:
        return self.intervention_authorization.artifact_reference
