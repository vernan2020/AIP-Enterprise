from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_receipt import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceipt,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus,
)


class NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceError(ValueError):
    """Raised when operational recovery acceptance cannot be issued safely."""


class NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceRequirement(str, Enum):
    """Evidence required before one successful recovery may be accepted."""

    RECOVERY_RECEIPT_VERIFIED = "RECOVERY_RECEIPT_VERIFIED"
    POST_RECOVERY_VALIDATION_COMPLETED = "POST_RECOVERY_VALIDATION_COMPLETED"
    RETURN_TO_SERVICE_STABILITY_CONFIRMED = "RETURN_TO_SERVICE_STABILITY_CONFIRMED"
    OBSERVABILITY_CONFIRMED = "OBSERVABILITY_CONFIRMED"
    OPERATIONS_OWNER_ACCEPTANCE_RECORDED = "OPERATIONS_OWNER_ACCEPTANCE_RECORDED"


REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_ACCEPTANCE_REQUIREMENTS = (
    frozenset(NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceRequirement)
)


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceEvidence:
    """Traceable evidence for one operational recovery acceptance requirement."""

    requirement: NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceRequirement
    source_reference: str

    def __post_init__(self) -> None:
        if not self.source_reference.strip():
            raise ValueError(
                "NII audit operational recovery acceptance evidence source_reference is required"
            )


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptance:
    """Positive-only acceptance of one exact successful operational recovery receipt."""

    recovery_receipt: NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceipt
    acceptance_reference: str
    evidence: tuple[
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceEvidence, ...
    ]

    def __post_init__(self) -> None:
        if (
            self.recovery_receipt.status
            is not NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus.SUCCEEDED
        ):
            raise ValueError(
                "NII audit operational recovery acceptance requires a successful receipt"
            )
        if not all(
            result.status
            is NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus.SUCCEEDED
            for result in self.recovery_receipt.checkpoint_results
        ):
            raise ValueError(
                "NII audit operational recovery acceptance requires every checkpoint to succeed"
            )
        if not self.acceptance_reference.strip():
            raise ValueError("NII audit operational recovery acceptance_reference is required")

        requirements = tuple(item.requirement for item in self.evidence)
        if len(requirements) != len(set(requirements)):
            raise ValueError(
                "Duplicate NII audit operational recovery acceptance evidence requirement"
            )
        if (
            frozenset(requirements)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_ACCEPTANCE_REQUIREMENTS
        ):
            raise ValueError(
                "NII audit operational recovery acceptance evidence must cover every required acceptance"
            )

        canonical_evidence = tuple(
            sorted(
                self.evidence,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        if self.evidence != canonical_evidence:
            raise ValueError(
                "NII audit operational recovery acceptance evidence must be canonicalized"
            )

    @property
    def recovery_receipt_reference(self) -> str:
        return self.recovery_receipt.receipt_reference

    @property
    def recovery_reference(self) -> str:
        return self.recovery_receipt.recovery_reference

    @property
    def recovery_authorization_reference(self) -> str:
        return self.recovery_receipt.authorization_reference

    @property
    def recovery_action(self) -> NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction:
        return self.recovery_receipt.action

    @property
    def intervention_acceptance_reference(self) -> str:
        return self.recovery_receipt.intervention_acceptance_reference

    @property
    def intervention_receipt_reference(self) -> str:
        return self.recovery_receipt.intervention_receipt_reference

    @property
    def intervention_reference(self) -> str:
        return self.recovery_receipt.intervention_reference

    @property
    def intervention_authorization_reference(self) -> str:
        return self.recovery_receipt.intervention_authorization_reference

    @property
    def intervention_action(
        self,
    ) -> NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction:
        return self.recovery_receipt.intervention_action

    @property
    def attestation_reference(self) -> str:
        return self.recovery_receipt.attestation_reference

    @property
    def operations_reference(self) -> str:
        return self.recovery_receipt.operations_reference

    @property
    def adapter_reference(self) -> str:
        return self.recovery_receipt.adapter_reference

    @property
    def environment_reference(self) -> str:
        return self.recovery_receipt.environment_reference

    @property
    def artifact_reference(self) -> str:
        return self.recovery_receipt.artifact_reference
