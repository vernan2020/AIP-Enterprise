from __future__ import annotations

from dataclasses import dataclass

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_authorization import (
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_REQUIREMENTS,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryEvidence,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_status_attestation import (
    NIIRunAuditPhysicalAdapterProductionOperationalStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_intervention_acceptance import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptance,
)


class NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAuthorizationError(
    ValueError
):
    """Raised when post-recovery operational recovery cannot be authorized safely."""


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAuthorization:
    """Positive-only recovery authorization for one exact Phase 60 acceptance."""

    intervention_acceptance: (
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptance
    )
    authorization_reference: str
    action: NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction
    evidence: tuple[NIIRunAuditPhysicalAdapterProductionOperationalRecoveryEvidence, ...]

    def __post_init__(self) -> None:
        if not self.authorization_reference.strip():
            raise ValueError(
                "NII audit post-recovery operational recovery authorization_reference is required"
            )
        if not self.intervention_acceptance.acceptance_reference.strip():
            raise ValueError(
                "NII audit post-recovery operational recovery requires a valid intervention acceptance"
            )
        if (
            self.authorization_reference
            == self.intervention_acceptance.recovery_authorization_reference
        ):
            raise ValueError(
                "NII audit post-recovery operational recovery cannot reuse the previous "
                "recovery authorization_reference"
            )

        expected_action = {
            NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND: (
                NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME
            ),
            NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.DEACTIVATE: (
                NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.REACTIVATE
            ),
        }[self.intervention_acceptance.action]
        if self.action is not expected_action:
            raise ValueError(
                "NII audit post-recovery operational recovery action must match the accepted "
                "intervention action"
            )

        requirements = tuple(item.requirement for item in self.evidence)
        if len(requirements) != len(set(requirements)):
            raise ValueError(
                "Duplicate NII audit post-recovery operational recovery evidence requirement"
            )
        if (
            frozenset(requirements)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_REQUIREMENTS
        ):
            raise ValueError(
                "NII audit post-recovery operational recovery evidence must cover every "
                "required control"
            )

        canonical_evidence = tuple(
            sorted(
                self.evidence,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        if self.evidence != canonical_evidence:
            raise ValueError(
                "NII audit post-recovery operational recovery evidence must be canonicalized"
            )

    @property
    def intervention_acceptance_reference(self) -> str:
        return self.intervention_acceptance.acceptance_reference

    @property
    def intervention_receipt_reference(self) -> str:
        return self.intervention_acceptance.intervention_receipt_reference

    @property
    def intervention_reference(self) -> str:
        return self.intervention_acceptance.intervention_reference

    @property
    def intervention_authorization_reference(self) -> str:
        return self.intervention_acceptance.authorization_reference

    @property
    def intervention_action(
        self,
    ) -> NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction:
        return self.intervention_acceptance.action

    @property
    def reattestation_reference(self) -> str:
        return self.intervention_acceptance.reattestation_reference

    @property
    def operational_status(self) -> NIIRunAuditPhysicalAdapterProductionOperationalStatus:
        return self.intervention_acceptance.operational_status

    @property
    def epoch_reference(self) -> str:
        return self.intervention_acceptance.epoch_reference

    @property
    def previous_operations_reference(self) -> str:
        return self.intervention_acceptance.previous_operations_reference

    @property
    def previous_attestation_reference(self) -> str:
        return self.intervention_acceptance.previous_attestation_reference

    @property
    def previous_recovery_acceptance_reference(self) -> str:
        return self.intervention_acceptance.recovery_acceptance_reference

    @property
    def previous_recovery_receipt_reference(self) -> str:
        return self.intervention_acceptance.recovery_receipt_reference

    @property
    def previous_recovery_reference(self) -> str:
        return self.intervention_acceptance.recovery_reference

    @property
    def previous_recovery_authorization_reference(self) -> str:
        return self.intervention_acceptance.recovery_authorization_reference

    @property
    def previous_recovery_action(self) -> NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction:
        return self.intervention_acceptance.recovery_action

    @property
    def previous_intervention_authorization_reference(self) -> str:
        return self.intervention_acceptance.previous_intervention_authorization_reference

    @property
    def previous_intervention_action(
        self,
    ) -> NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction:
        return self.intervention_acceptance.previous_intervention_action

    @property
    def adapter_reference(self) -> str:
        return self.intervention_acceptance.adapter_reference

    @property
    def environment_reference(self) -> str:
        return self.intervention_acceptance.environment_reference

    @property
    def artifact_reference(self) -> str:
        return self.intervention_acceptance.artifact_reference
