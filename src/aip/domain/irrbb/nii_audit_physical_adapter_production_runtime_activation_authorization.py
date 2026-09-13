from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.domain.irrbb.nii_audit_physical_adapter_production_post_execution_acceptance import (
    NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptance,
)


class NIIRunAuditPhysicalAdapterProductionRuntimeActivationAuthorizationError(ValueError):
    """Raised when runtime activation authorization cannot be issued safely."""


class NIIRunAuditPhysicalAdapterProductionRuntimeActivationRequirement(str, Enum):
    """Governance evidence required before runtime activation may be authorized."""

    POST_EXECUTION_ACCEPTANCE_VERIFIED = "POST_EXECUTION_ACCEPTANCE_VERIFIED"
    RUNTIME_CONFIGURATION_APPROVED = "RUNTIME_CONFIGURATION_APPROVED"
    DEPENDENCY_WIRING_APPROVED = "DEPENDENCY_WIRING_APPROVED"
    STARTUP_SEQUENCE_APPROVED = "STARTUP_SEQUENCE_APPROVED"
    OPERATIONS_ACTIVATION_AUTHORITY_CONFIRMED = "OPERATIONS_ACTIVATION_AUTHORITY_CONFIRMED"


REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_REQUIREMENTS = frozenset(
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationRequirement
)


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionRuntimeActivationEvidence:
    """Traceable evidence for one runtime-activation authorization requirement."""

    requirement: NIIRunAuditPhysicalAdapterProductionRuntimeActivationRequirement
    source_reference: str

    def __post_init__(self) -> None:
        if not self.source_reference.strip():
            raise ValueError(
                "NII audit physical adapter production runtime activation evidence "
                "source_reference is required"
            )


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionRuntimeActivationAuthorization:
    """Positive-only authorization for future runtime activation of one accepted deployment."""

    post_execution_acceptance: NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptance
    activation_authorization_reference: str
    evidence: tuple[NIIRunAuditPhysicalAdapterProductionRuntimeActivationEvidence, ...]

    def __post_init__(self) -> None:
        if not self.activation_authorization_reference.strip():
            raise ValueError(
                "NII audit physical adapter production runtime activation "
                "authorization_reference is required"
            )

        evidence_requirements = tuple(item.requirement for item in self.evidence)
        if len(evidence_requirements) != len(set(evidence_requirements)):
            raise ValueError(
                "Duplicate NII audit physical adapter production runtime activation "
                "evidence requirement"
            )
        if (
            frozenset(evidence_requirements)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_REQUIREMENTS
        ):
            raise ValueError(
                "NII audit physical adapter production runtime activation evidence "
                "must cover every required authorization"
            )

        canonical_evidence = tuple(
            sorted(
                self.evidence,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        if self.evidence != canonical_evidence:
            raise ValueError(
                "NII audit physical adapter production runtime activation evidence "
                "must be canonicalized"
            )

    @property
    def acceptance_reference(self) -> str:
        return self.post_execution_acceptance.acceptance_reference

    @property
    def receipt_reference(self) -> str:
        return self.post_execution_acceptance.receipt_reference

    @property
    def execution_reference(self) -> str:
        return self.post_execution_acceptance.execution_reference

    @property
    def execution_authorization_reference(self) -> str:
        return self.post_execution_acceptance.execution_authorization_reference

    @property
    def plan_reference(self) -> str:
        return self.post_execution_acceptance.plan_reference

    @property
    def adapter_reference(self) -> str:
        return self.post_execution_acceptance.adapter_reference

    @property
    def environment_reference(self) -> str:
        return self.post_execution_acceptance.environment_reference

    @property
    def artifact_reference(self) -> str:
        return self.post_execution_acceptance.artifact_reference

    @property
    def planned_rollback_reference(self) -> str:
        return self.post_execution_acceptance.planned_rollback_reference
