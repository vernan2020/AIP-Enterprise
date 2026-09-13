from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_continuity_epoch import (
    NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpoch,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_status_attestation import (
    NIIRunAuditPhysicalAdapterProductionOperationalStatus,
)


class NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationError(ValueError):
    """Raised when a post-recovery operational status re-attestation is inconsistent."""


class NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationRequirement(str, Enum):
    """Evidence required for one status re-attestation of a continuity epoch."""

    CONTINUITY_EPOCH_VERIFIED = "CONTINUITY_EPOCH_VERIFIED"
    OBSERVABILITY_STATUS_VERIFIED = "OBSERVABILITY_STATUS_VERIFIED"
    INCIDENT_STATUS_VERIFIED = "INCIDENT_STATUS_VERIFIED"
    CONTINUITY_STATUS_VERIFIED = "CONTINUITY_STATUS_VERIFIED"
    CHANGE_STATUS_VERIFIED = "CHANGE_STATUS_VERIFIED"


REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_STATUS_REATTESTATION_REQUIREMENTS = (
    frozenset(NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationRequirement)
)


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationEvidence:
    """Traceable source-neutral evidence for one re-attestation requirement."""

    requirement: NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationRequirement
    source_reference: str

    def __post_init__(self) -> None:
        if not self.source_reference.strip():
            raise ValueError(
                "NII audit operational status re-attestation evidence source_reference is required"
            )


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestation:
    """Immutable status re-attestation bound to one exact Phase 56 continuity epoch."""

    continuity_epoch: NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpoch
    reattestation_reference: str
    status: NIIRunAuditPhysicalAdapterProductionOperationalStatus
    evidence: tuple[NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationEvidence, ...]
    exception_references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.continuity_epoch.epoch_reference.strip():
            raise ValueError(
                "NII audit operational status re-attestation requires a valid continuity epoch"
            )
        if (
            self.continuity_epoch.epoch_reference
            == self.continuity_epoch.previous_operations_reference
        ):
            raise ValueError(
                "NII audit operational status re-attestation requires a distinct continuity epoch"
            )
        if not self.reattestation_reference.strip():
            raise ValueError("NII audit operational status reattestation_reference is required")

        requirements = tuple(item.requirement for item in self.evidence)
        if len(requirements) != len(set(requirements)):
            raise ValueError(
                "Duplicate NII audit operational status re-attestation evidence requirement"
            )
        if (
            frozenset(requirements)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_STATUS_REATTESTATION_REQUIREMENTS
        ):
            raise ValueError(
                "NII audit operational status re-attestation evidence must cover every required "
                "status control"
            )

        canonical_evidence = tuple(
            sorted(
                self.evidence,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        if self.evidence != canonical_evidence:
            raise ValueError(
                "NII audit operational status re-attestation evidence must be canonicalized"
            )

        if any(not reference.strip() for reference in self.exception_references):
            raise ValueError(
                "NII audit operational status re-attestation exception reference must be nonblank"
            )
        if len(self.exception_references) != len(set(self.exception_references)):
            raise ValueError(
                "Duplicate NII audit operational status re-attestation exception reference"
            )
        if self.exception_references != tuple(sorted(self.exception_references)):
            raise ValueError(
                "NII audit operational status re-attestation exception references must be "
                "canonicalized"
            )

        if self.status is NIIRunAuditPhysicalAdapterProductionOperationalStatus.HEALTHY:
            if self.exception_references:
                raise ValueError(
                    "HEALTHY operational status re-attestation cannot contain exception references"
                )
        elif not self.exception_references:
            raise ValueError(
                "Non-HEALTHY operational status re-attestation requires at least one exception "
                "reference"
            )

    @property
    def epoch_reference(self) -> str:
        return self.continuity_epoch.epoch_reference

    @property
    def previous_operations_reference(self) -> str:
        return self.continuity_epoch.previous_operations_reference

    @property
    def previous_attestation_reference(self) -> str:
        return self.continuity_epoch.attestation_reference

    @property
    def recovery_acceptance_reference(self) -> str:
        return self.continuity_epoch.recovery_acceptance_reference

    @property
    def recovery_receipt_reference(self) -> str:
        return self.continuity_epoch.recovery_receipt_reference

    @property
    def recovery_reference(self) -> str:
        return self.continuity_epoch.recovery_reference

    @property
    def recovery_authorization_reference(self) -> str:
        return self.continuity_epoch.recovery_authorization_reference

    @property
    def recovery_action(self) -> NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction:
        return self.continuity_epoch.recovery_action

    @property
    def intervention_acceptance_reference(self) -> str:
        return self.continuity_epoch.intervention_acceptance_reference

    @property
    def intervention_receipt_reference(self) -> str:
        return self.continuity_epoch.intervention_receipt_reference

    @property
    def intervention_reference(self) -> str:
        return self.continuity_epoch.intervention_reference

    @property
    def intervention_authorization_reference(self) -> str:
        return self.continuity_epoch.intervention_authorization_reference

    @property
    def intervention_action(
        self,
    ) -> NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction:
        return self.continuity_epoch.intervention_action

    @property
    def adapter_reference(self) -> str:
        return self.continuity_epoch.adapter_reference

    @property
    def environment_reference(self) -> str:
        return self.continuity_epoch.environment_reference

    @property
    def artifact_reference(self) -> str:
        return self.continuity_epoch.artifact_reference
