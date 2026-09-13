from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_receipt import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionReceipt,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus,
)


class NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceError(ValueError):
    """Raised when operational intervention acceptance cannot be issued safely."""


class NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceRequirement(str, Enum):
    """Evidence required before one successful intervention may be accepted."""

    INTERVENTION_RECEIPT_VERIFIED = "INTERVENTION_RECEIPT_VERIFIED"
    POST_INTERVENTION_VALIDATION_COMPLETED = "POST_INTERVENTION_VALIDATION_COMPLETED"
    RESULTING_STATE_STABILITY_CONFIRMED = "RESULTING_STATE_STABILITY_CONFIRMED"
    OBSERVABILITY_CONFIRMED = "OBSERVABILITY_CONFIRMED"
    OPERATIONS_OWNER_ACCEPTANCE_RECORDED = "OPERATIONS_OWNER_ACCEPTANCE_RECORDED"


REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_ACCEPTANCE_REQUIREMENTS = (
    frozenset(NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceRequirement)
)


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceEvidence:
    """Traceable evidence for one intervention-acceptance requirement."""

    requirement: NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceRequirement
    source_reference: str

    def __post_init__(self) -> None:
        if not self.source_reference.strip():
            raise ValueError(
                "NII audit operational intervention acceptance evidence source_reference is required"
            )


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptance:
    """Positive-only acceptance of one exact successful operational intervention receipt."""

    intervention_receipt: NIIRunAuditPhysicalAdapterProductionOperationalInterventionReceipt
    acceptance_reference: str
    evidence: tuple[
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceEvidence, ...
    ]

    def __post_init__(self) -> None:
        if (
            self.intervention_receipt.status
            is not NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus.SUCCEEDED
        ):
            raise ValueError(
                "NII audit operational intervention acceptance requires a successful receipt"
            )
        if not all(
            result.status
            is NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus.SUCCEEDED
            for result in self.intervention_receipt.checkpoint_results
        ):
            raise ValueError(
                "NII audit operational intervention acceptance requires every checkpoint to succeed"
            )
        if not self.acceptance_reference.strip():
            raise ValueError("NII audit operational intervention acceptance_reference is required")

        requirements = tuple(item.requirement for item in self.evidence)
        if len(requirements) != len(set(requirements)):
            raise ValueError(
                "Duplicate NII audit operational intervention acceptance evidence requirement"
            )
        if (
            frozenset(requirements)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_ACCEPTANCE_REQUIREMENTS
        ):
            raise ValueError(
                "NII audit operational intervention acceptance evidence must cover every required acceptance"
            )

        canonical_evidence = tuple(
            sorted(
                self.evidence,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        if self.evidence != canonical_evidence:
            raise ValueError(
                "NII audit operational intervention acceptance evidence must be canonicalized"
            )

    @property
    def intervention_receipt_reference(self) -> str:
        return self.intervention_receipt.receipt_reference

    @property
    def intervention_reference(self) -> str:
        return self.intervention_receipt.intervention_reference

    @property
    def authorization_reference(self) -> str:
        return self.intervention_receipt.authorization_reference

    @property
    def action(self) -> NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction:
        return self.intervention_receipt.action

    @property
    def attestation_reference(self) -> str:
        return self.intervention_receipt.attestation_reference

    @property
    def operations_reference(self) -> str:
        return self.intervention_receipt.operations_reference

    @property
    def adapter_reference(self) -> str:
        return self.intervention_receipt.adapter_reference

    @property
    def environment_reference(self) -> str:
        return self.intervention_receipt.environment_reference

    @property
    def artifact_reference(self) -> str:
        return self.intervention_receipt.artifact_reference
