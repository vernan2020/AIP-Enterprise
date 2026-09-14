from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.domain.irrbb.nii_audit_physical_adapter_production_runtime_activation_acceptance import (
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptance,
)


class NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsError(ValueError):
    """Raised when a steady-state operations record cannot be issued safely."""


class NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsRequirement(str, Enum):
    """Evidence required before steady-state operations may be recorded."""

    ACTIVATION_ACCEPTANCE_VERIFIED = "ACTIVATION_ACCEPTANCE_VERIFIED"
    SERVICE_OWNERSHIP_CONFIRMED = "SERVICE_OWNERSHIP_CONFIRMED"
    CONTINUOUS_OBSERVABILITY_OWNERSHIP_CONFIRMED = "CONTINUOUS_OBSERVABILITY_OWNERSHIP_CONFIRMED"
    INCIDENT_ESCALATION_OWNERSHIP_CONFIRMED = "INCIDENT_ESCALATION_OWNERSHIP_CONFIRMED"
    CONTINUITY_RECOVERY_OWNERSHIP_CONFIRMED = "CONTINUITY_RECOVERY_OWNERSHIP_CONFIRMED"
    CHANGE_MANAGEMENT_OWNERSHIP_CONFIRMED = "CHANGE_MANAGEMENT_OWNERSHIP_CONFIRMED"


REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_STEADY_STATE_OPERATIONS_REQUIREMENTS = frozenset(
    NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsRequirement
)


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsEvidence:
    """Traceable evidence for one steady-state operations requirement."""

    requirement: NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsRequirement
    source_reference: str

    def __post_init__(self) -> None:
        if not self.source_reference.strip():
            raise ValueError(
                "NII audit physical adapter production steady-state operations evidence "
                "source_reference is required"
            )


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionSteadyStateOperations:
    """Positive-only operations record for one exact accepted runtime activation."""

    activation_acceptance: NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptance
    operations_reference: str
    evidence: tuple[NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsEvidence, ...]

    def __post_init__(self) -> None:
        if not self.operations_reference.strip():
            raise ValueError(
                "NII audit physical adapter production steady-state operations_reference is required"
            )

        evidence_requirements = tuple(item.requirement for item in self.evidence)
        if len(evidence_requirements) != len(set(evidence_requirements)):
            raise ValueError(
                "Duplicate NII audit physical adapter production steady-state operations "
                "evidence requirement"
            )
        if (
            frozenset(evidence_requirements)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_STEADY_STATE_OPERATIONS_REQUIREMENTS
        ):
            raise ValueError(
                "NII audit physical adapter production steady-state operations evidence "
                "must cover every required operations control"
            )

        canonical_evidence = tuple(
            sorted(
                self.evidence,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        if self.evidence != canonical_evidence:
            raise ValueError(
                "NII audit physical adapter production steady-state operations evidence "
                "must be canonicalized"
            )

    @property
    def runtime_activation_acceptance_reference(self) -> str:
        return self.activation_acceptance.acceptance_reference

    @property
    def runtime_activation_receipt_reference(self) -> str:
        return self.activation_acceptance.runtime_activation_receipt_reference

    @property
    def activation_reference(self) -> str:
        return self.activation_acceptance.activation_reference

    @property
    def adapter_reference(self) -> str:
        return self.activation_acceptance.adapter_reference

    @property
    def environment_reference(self) -> str:
        return self.activation_acceptance.environment_reference

    @property
    def artifact_reference(self) -> str:
        return self.activation_acceptance.artifact_reference
