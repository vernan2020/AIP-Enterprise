from __future__ import annotations

from typing import cast

import pytest

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_acceptance import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceEvidence,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorization,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionEvidence,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_receipt import (
    NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_CHECKPOINT_ORDER,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointResult,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorization,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorizationError,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryEvidence,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_status_attestation import (
    NIIRunAuditPhysicalAdapterProductionOperationalStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestation,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_operational_intervention_acceptance_service import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceService,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_operational_intervention_receipt_service import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionReceiptService,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_operational_recovery_authorization_service import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorizationService,
)


class _StatusAttestationStub:
    status = NIIRunAuditPhysicalAdapterProductionOperationalStatus.DEGRADED
    attestation_reference = "status:degraded"
    operations_reference = "steady-state:2026-09-13"
    adapter_reference = "adapter-v1"
    environment_reference = "production-cr-primary"
    artifact_reference = "artifact:nii-audit-adapter-v1"


def _status_attestation() -> NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestation:
    return cast(
        NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestation,
        _StatusAttestationStub(),
    )


def _accepted_intervention(
    intervention_action: NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
):
    intervention_evidence = tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionEvidence(
            requirement=requirement,
            source_reference=f"intervention:{requirement.value.lower()}",
        )
        for requirement in NIIRunAuditPhysicalAdapterProductionOperationalInterventionRequirement
    )
    authorization = NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorization(
        operational_status_attestation=_status_attestation(),
        authorization_reference="intervention-auth:53",
        action=intervention_action,
        evidence=tuple(
            sorted(
                intervention_evidence,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        ),
    )
    checkpoint_results = tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointResult(
            checkpoint=checkpoint,
            status=NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus.SUCCEEDED,
            evidence_reference=f"observed:{checkpoint.value.lower()}",
        )
        for checkpoint in NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_CHECKPOINT_ORDER
    )
    receipt = NIIRunAuditPhysicalAdapterProductionOperationalInterventionReceiptService.record(
        intervention_authorization=authorization,
        receipt_reference="intervention-receipt:53",
        intervention_reference="intervention-execution:53",
        checkpoint_results=checkpoint_results,
    )
    acceptance_evidence = tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceEvidence(
            requirement=requirement,
            source_reference=f"acceptance:{requirement.value.lower()}",
        )
        for requirement in NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceRequirement
    )
    return NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceService.accept(
        intervention_receipt=receipt,
        acceptance_reference="intervention-acceptance:53",
        evidence=acceptance_evidence,
    )


def _recovery_evidence() -> (
    tuple[NIIRunAuditPhysicalAdapterProductionOperationalRecoveryEvidence, ...]
):
    return tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryEvidence(
            requirement=requirement,
            source_reference=f"recovery:{requirement.value.lower()}",
        )
        for requirement in reversed(
            tuple(NIIRunAuditPhysicalAdapterProductionOperationalRecoveryRequirement)
        )
    )


@pytest.mark.parametrize(
    ("intervention_action", "recovery_action"),
    [
        (
            NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND,
            NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME,
        ),
        (
            NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.DEACTIVATE,
            NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.REACTIVATE,
        ),
    ],
)
def test_authorization_preserves_exact_acceptance_and_valid_action_pair(
    intervention_action: NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
    recovery_action: NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction,
) -> None:
    acceptance = _accepted_intervention(intervention_action)

    authorization = (
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorizationService.authorize(
            intervention_acceptance=acceptance,
            authorization_reference="recovery-auth:53",
            action=recovery_action,
            evidence=_recovery_evidence(),
        )
    )

    assert authorization.intervention_acceptance is acceptance
    assert authorization.action is recovery_action
    assert authorization.intervention_action is intervention_action
    assert authorization.intervention_acceptance_reference == acceptance.acceptance_reference
    assert authorization.intervention_receipt_reference == acceptance.intervention_receipt_reference
    assert authorization.adapter_reference == acceptance.adapter_reference
    assert authorization.environment_reference == acceptance.environment_reference
    assert authorization.artifact_reference == acceptance.artifact_reference
    assert tuple(item.requirement.value for item in authorization.evidence) == tuple(
        sorted(
            requirement.value
            for requirement in NIIRunAuditPhysicalAdapterProductionOperationalRecoveryRequirement
        )
    )


def test_mismatched_recovery_action_is_rejected() -> None:
    acceptance = _accepted_intervention(
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
    )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorizationError,
        match="must match",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorizationService.authorize(
            intervention_acceptance=acceptance,
            authorization_reference="recovery-auth:invalid",
            action=NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.REACTIVATE,
            evidence=_recovery_evidence(),
        )


def test_blank_authorization_reference_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorizationError,
        match="authorization_reference",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorizationService.authorize(
            intervention_acceptance=_accepted_intervention(
                NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
            ),
            authorization_reference=" ",
            action=NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME,
            evidence=_recovery_evidence(),
        )


def test_missing_or_duplicate_recovery_requirement_is_rejected() -> None:
    acceptance = _accepted_intervention(
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
    )
    evidence = _recovery_evidence()

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorizationError,
        match="cover every required control",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorizationService.authorize(
            intervention_acceptance=acceptance,
            authorization_reference="recovery-auth:missing",
            action=NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME,
            evidence=evidence[:-1],
        )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorizationError,
        match="Duplicate",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorizationService.authorize(
            intervention_acceptance=acceptance,
            authorization_reference="recovery-auth:duplicate",
            action=NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME,
            evidence=(*evidence, evidence[0]),
        )


def test_blank_evidence_source_reference_is_rejected() -> None:
    with pytest.raises(ValueError, match="source_reference"):
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryEvidence(
            requirement=NIIRunAuditPhysicalAdapterProductionOperationalRecoveryRequirement.RECOVERY_POLICY_VERIFIED,
            source_reference=" ",
        )


def test_direct_authorization_requires_canonical_evidence() -> None:
    with pytest.raises(ValueError, match="must be canonicalized"):
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorization(
            intervention_acceptance=_accepted_intervention(
                NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
            ),
            authorization_reference="recovery-auth:direct",
            action=NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME,
            evidence=_recovery_evidence(),
        )
