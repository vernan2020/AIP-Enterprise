from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_status_attestation import (
    NIIRunAuditPhysicalAdapterProductionOperationalStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestation,
)


class NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction(str, Enum):
    """Explicit governed action that may be authorized for a non-healthy service."""

    SUSPEND = "SUSPEND"
    DEACTIVATE = "DEACTIVATE"


class NIIRunAuditPhysicalAdapterProductionOperationalInterventionRequirement(str, Enum):
    """Evidence required before an operational intervention may be authorized."""

    STATUS_ATTESTATION_VERIFIED = "STATUS_ATTESTATION_VERIFIED"
    INTERVENTION_POLICY_VERIFIED = "INTERVENTION_POLICY_VERIFIED"
    OPERATIONAL_APPROVAL_VERIFIED = "OPERATIONAL_APPROVAL_VERIFIED"
    CONTINUITY_IMPACT_VERIFIED = "CONTINUITY_IMPACT_VERIFIED"


REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_REQUIREMENTS = frozenset(
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionRequirement
)


class NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorizationError(ValueError):
    """Raised when an operational intervention authorization is inconsistent."""


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionOperationalInterventionEvidence:
    """Traceable source-neutral evidence for one intervention requirement."""

    requirement: NIIRunAuditPhysicalAdapterProductionOperationalInterventionRequirement
    source_reference: str

    def __post_init__(self) -> None:
        if not self.source_reference.strip():
            raise ValueError(
                "NII audit operational intervention evidence source_reference is required"
            )


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorization:
    """Positive-only authorization bound to one exact non-healthy status attestation."""

    operational_status_attestation: NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestation
    authorization_reference: str
    action: NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction
    evidence: tuple[NIIRunAuditPhysicalAdapterProductionOperationalInterventionEvidence, ...]

    def __post_init__(self) -> None:
        if not self.authorization_reference.strip():
            raise ValueError(
                "NII audit operational intervention authorization_reference is required"
            )
        if (
            self.operational_status_attestation.status
            is NIIRunAuditPhysicalAdapterProductionOperationalStatus.HEALTHY
        ):
            raise ValueError("HEALTHY NII audit operational status cannot authorize intervention")

        evidence_requirements = tuple(item.requirement for item in self.evidence)
        if len(evidence_requirements) != len(set(evidence_requirements)):
            raise ValueError("Duplicate NII audit operational intervention evidence requirement")
        if (
            frozenset(evidence_requirements)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_REQUIREMENTS
        ):
            raise ValueError(
                "NII audit operational intervention evidence must cover every required control"
            )
        canonical_evidence = tuple(
            sorted(
                self.evidence,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        if self.evidence != canonical_evidence:
            raise ValueError("NII audit operational intervention evidence must be canonicalized")

    @property
    def attestation_reference(self) -> str:
        return self.operational_status_attestation.attestation_reference

    @property
    def status(self) -> NIIRunAuditPhysicalAdapterProductionOperationalStatus:
        return self.operational_status_attestation.status

    @property
    def operations_reference(self) -> str:
        return self.operational_status_attestation.operations_reference

    @property
    def adapter_reference(self) -> str:
        return self.operational_status_attestation.adapter_reference

    @property
    def environment_reference(self) -> str:
        return self.operational_status_attestation.environment_reference

    @property
    def artifact_reference(self) -> str:
        return self.operational_status_attestation.artifact_reference
