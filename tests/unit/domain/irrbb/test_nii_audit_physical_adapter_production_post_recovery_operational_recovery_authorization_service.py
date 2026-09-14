from __future__ import annotations

from typing import cast

import pytest

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_acceptance import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceEvidence,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_receipt import (
    NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_CHECKPOINT_ORDER,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointResult,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryEvidence,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_status_attestation import (
    NIIRunAuditPhysicalAdapterProductionOperationalStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_intervention_acceptance import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptance,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_intervention_receipt import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceipt,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_recovery_authorization import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAuthorization,
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAuthorizationError,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_post_recovery_operational_recovery_authorization_service import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAuthorizationService,
)


class _SuccessfulPostRecoveryInterventionReceiptStub:
    receipt_reference = "intervention-receipt:post-recovery:61"
    intervention_reference = "intervention-execution:post-recovery:61"
    authorization_reference = "intervention-auth:post-recovery:61"
    action = NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
    reattestation_reference = "status-reattestation:degraded:61"
    operational_status = NIIRunAuditPhysicalAdapterProductionOperationalStatus.DEGRADED
    epoch_reference = "steady-state:post-recovery:61"
    previous_operations_reference = "steady-state:pre-recovery:61"
    previous_attestation_reference = "status:pre-recovery:61"
    recovery_acceptance_reference = "recovery-acceptance:previous:61"
    recovery_receipt_reference = "recovery-receipt:previous:61"
    recovery_reference = "recovery-execution:previous:61"
    recovery_authorization_reference = "recovery-auth:previous:61"
    recovery_action = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME
    previous_intervention_authorization_reference = "intervention-auth:previous:61"
    previous_intervention_action = (
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
    )
    adapter_reference = "adapter-v1"
    environment_reference = "production-cr-primary"
    artifact_reference = "artifact:nii-audit-adapter-v1"
    status = NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus.SUCCEEDED
    checkpoint_results = tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointResult(
            checkpoint=checkpoint,
            status=(
                NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus.SUCCEEDED
            ),
            evidence_reference=f"observed:{checkpoint.value.lower()}:61",
        )
        for checkpoint in NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_CHECKPOINT_ORDER
    )


def _receipt(
    action: NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
) -> NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceipt:
    class _Receipt(_SuccessfulPostRecoveryInterventionReceiptStub):
        pass

    _Receipt.action = action
    return cast(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceipt,
        _Receipt(),
    )


def _accepted_intervention(
    action: NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
) -> NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptance:
    evidence = tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceEvidence(
            requirement=requirement,
            source_reference=f"acceptance:{requirement.value.lower()}:61",
        )
        for requirement in NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceRequirement
    )
    return NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptance(
        intervention_receipt=_receipt(action),
        acceptance_reference="intervention-acceptance:post-recovery:61",
        evidence=tuple(
            sorted(evidence, key=lambda item: (item.requirement.value, item.source_reference))
        ),
    )


def _recovery_evidence() -> (
    tuple[NIIRunAuditPhysicalAdapterProductionOperationalRecoveryEvidence, ...]
):
    return tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryEvidence(
            requirement=requirement,
            source_reference=f"post-recovery-recovery:{requirement.value.lower()}:61",
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
def test_authorization_preserves_exact_acceptance_and_full_post_recovery_chain(
    intervention_action: NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
    recovery_action: NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction,
) -> None:
    acceptance = _accepted_intervention(intervention_action)

    authorization = NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAuthorizationService.authorize(
        intervention_acceptance=acceptance,
        authorization_reference="recovery-auth:new-cycle:61",
        action=recovery_action,
        evidence=_recovery_evidence(),
    )

    assert authorization.intervention_acceptance is acceptance
    assert authorization.action is recovery_action
    assert authorization.intervention_action is intervention_action
    assert authorization.intervention_acceptance_reference == acceptance.acceptance_reference
    assert authorization.intervention_receipt_reference == acceptance.intervention_receipt_reference
    assert authorization.intervention_reference == acceptance.intervention_reference
    assert authorization.intervention_authorization_reference == acceptance.authorization_reference
    assert authorization.reattestation_reference == acceptance.reattestation_reference
    assert authorization.operational_status is acceptance.operational_status
    assert authorization.epoch_reference == acceptance.epoch_reference
    assert authorization.previous_operations_reference == acceptance.previous_operations_reference
    assert authorization.previous_attestation_reference == acceptance.previous_attestation_reference
    assert (
        authorization.previous_recovery_acceptance_reference
        == acceptance.recovery_acceptance_reference
    )
    assert (
        authorization.previous_recovery_receipt_reference == acceptance.recovery_receipt_reference
    )
    assert authorization.previous_recovery_reference == acceptance.recovery_reference
    assert (
        authorization.previous_recovery_authorization_reference
        == acceptance.recovery_authorization_reference
    )
    assert authorization.previous_recovery_action is acceptance.recovery_action
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
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAuthorizationError,
        match="must match",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAuthorizationService.authorize(
            intervention_acceptance=acceptance,
            authorization_reference="recovery-auth:mismatch:61",
            action=NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.REACTIVATE,
            evidence=_recovery_evidence(),
        )


def test_previous_recovery_authorization_reference_cannot_be_reused() -> None:
    acceptance = _accepted_intervention(
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
    )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAuthorizationError,
        match="cannot reuse",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAuthorizationService.authorize(
            intervention_acceptance=acceptance,
            authorization_reference=acceptance.recovery_authorization_reference,
            action=NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME,
            evidence=_recovery_evidence(),
        )


def test_blank_authorization_reference_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAuthorizationError,
        match="authorization_reference",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAuthorizationService.authorize(
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
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAuthorizationError,
        match="cover every required control",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAuthorizationService.authorize(
            intervention_acceptance=acceptance,
            authorization_reference="recovery-auth:missing:61",
            action=NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME,
            evidence=evidence[:-1],
        )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAuthorizationError,
        match="Duplicate",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAuthorizationService.authorize(
            intervention_acceptance=acceptance,
            authorization_reference="recovery-auth:duplicate:61",
            action=NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME,
            evidence=(*evidence, evidence[0]),
        )


def test_blank_evidence_source_reference_is_rejected() -> None:
    with pytest.raises(ValueError, match="source_reference"):
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryEvidence(
            requirement=(
                NIIRunAuditPhysicalAdapterProductionOperationalRecoveryRequirement.RECOVERY_POLICY_VERIFIED
            ),
            source_reference=" ",
        )


def test_direct_authorization_requires_canonical_evidence() -> None:
    with pytest.raises(ValueError, match="must be canonicalized"):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAuthorization(
            intervention_acceptance=_accepted_intervention(
                NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
            ),
            authorization_reference="recovery-auth:direct:61",
            action=NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME,
            evidence=_recovery_evidence(),
        )
