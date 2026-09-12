from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.domain.irrbb.nii_audit_physical_adapter_production_steady_state_operations import (
    NIIRunAuditPhysicalAdapterProductionSteadyStateOperations,
)


class NIIRunAuditPhysicalAdapterProductionOperationalStatus(str, Enum):
    """Attested operating state for one exact steady-state service identity."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


class NIIRunAuditPhysicalAdapterProductionOperationalStatusRequirement(str, Enum):
    """Evidence required for one operational status attestation."""

    STEADY_STATE_OPERATIONS_VERIFIED = "STEADY_STATE_OPERATIONS_VERIFIED"
    OBSERVABILITY_STATUS_VERIFIED = "OBSERVABILITY_STATUS_VERIFIED"
    INCIDENT_STATUS_VERIFIED = "INCIDENT_STATUS_VERIFIED"
    CONTINUITY_STATUS_VERIFIED = "CONTINUITY_STATUS_VERIFIED"
    CHANGE_STATUS_VERIFIED = "CHANGE_STATUS_VERIFIED"


REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_STATUS_REQUIREMENTS = frozenset(
    NIIRunAuditPhysicalAdapterProductionOperationalStatusRequirement
)


class NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestationError(ValueError):
    """Raised when an operational status attestation is internally inconsistent."""


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionOperationalStatusEvidence:
    """Traceable source-neutral evidence for one operational status requirement."""

    requirement: NIIRunAuditPhysicalAdapterProductionOperationalStatusRequirement
    source_reference: str

    def __post_init__(self) -> None:
        if not self.source_reference.strip():
            raise ValueError(
                "NII audit physical adapter production operational status evidence "
                "source_reference is required"
            )


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestation:
    """Immutable status observation bound to one exact Phase 48 operations record."""

    steady_state_operations: NIIRunAuditPhysicalAdapterProductionSteadyStateOperations
    attestation_reference: str
    status: NIIRunAuditPhysicalAdapterProductionOperationalStatus
    evidence: tuple[NIIRunAuditPhysicalAdapterProductionOperationalStatusEvidence, ...]
    exception_references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.attestation_reference.strip():
            raise ValueError(
                "NII audit physical adapter production operational status "
                "attestation_reference is required"
            )

        evidence_requirements = tuple(item.requirement for item in self.evidence)
        if len(evidence_requirements) != len(set(evidence_requirements)):
            raise ValueError(
                "Duplicate NII audit physical adapter production operational status "
                "evidence requirement"
            )
        if (
            frozenset(evidence_requirements)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_STATUS_REQUIREMENTS
        ):
            raise ValueError(
                "NII audit physical adapter production operational status evidence "
                "must cover every required status control"
            )
        canonical_evidence = tuple(
            sorted(
                self.evidence,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        if self.evidence != canonical_evidence:
            raise ValueError(
                "NII audit physical adapter production operational status evidence "
                "must be canonicalized"
            )

        if any(not reference.strip() for reference in self.exception_references):
            raise ValueError(
                "NII audit physical adapter production operational status exception reference "
                "must be nonblank"
            )
        if len(self.exception_references) != len(set(self.exception_references)):
            raise ValueError(
                "Duplicate NII audit physical adapter production operational status "
                "exception reference"
            )
        if self.exception_references != tuple(sorted(self.exception_references)):
            raise ValueError(
                "NII audit physical adapter production operational status exception references "
                "must be canonicalized"
            )
        if self.status is NIIRunAuditPhysicalAdapterProductionOperationalStatus.HEALTHY:
            if self.exception_references:
                raise ValueError("HEALTHY operational status cannot contain exception references")
        elif not self.exception_references:
            raise ValueError(
                "Non-HEALTHY operational status requires at least one exception reference"
            )

    @property
    def operations_reference(self) -> str:
        return self.steady_state_operations.operations_reference

    @property
    def runtime_activation_acceptance_reference(self) -> str:
        return self.steady_state_operations.runtime_activation_acceptance_reference

    @property
    def adapter_reference(self) -> str:
        return self.steady_state_operations.adapter_reference

    @property
    def environment_reference(self) -> str:
        return self.steady_state_operations.environment_reference

    @property
    def artifact_reference(self) -> str:
        return self.steady_state_operations.artifact_reference
