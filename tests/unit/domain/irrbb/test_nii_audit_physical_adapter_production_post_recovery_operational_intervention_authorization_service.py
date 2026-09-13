from __future__ import annotations

from typing import cast

import pytest

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
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_status_reattestation import (
    NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestation,
    NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationEvidence,
    NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorization,
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationError,
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionEvidence,
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionRequirement,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_post_recovery_operational_intervention_authorization_service import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationService,
)


class _ContinuityEpochStub:
    epoch_reference = "steady-state:post-recovery:58"
    previous_operations_reference = "steady-state:pre-recovery:58"
    attestation_reference = "status:pre-recovery:58"
    recovery_acceptance_reference = "recovery-acceptance:58"
    recovery_receipt_reference = "recovery-receipt:58"
    recovery_reference = "recovery-execution:58"
    recovery_authorization_reference = "recovery-auth:58"
    recovery_action = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME
    intervention_acceptance_reference = "intervention-acceptance:58"
    intervention_receipt_reference = "intervention-receipt:58"
    intervention_reference = "intervention-execution:58"
    intervention_authorization_reference = "intervention-auth:previous:58"
    intervention_action = NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
    adapter_reference = "adapter-v1"
    environment_reference = "production-cr-primary"
    artifact_reference = "artifact:nii-audit-adapter-v1"


def _epoch() -> NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpoch:
    return cast(
        NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpoch,
        _ContinuityEpochStub(),
    )


def _reattestation(
    status: NIIRunAuditPhysicalAdapterProductionOperationalStatus,
) -> NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestation:
    evidence = tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationEvidence(
            requirement=requirement,
            source_reference=f"reattestation:{requirement.value.lower()}",
        )
        for requirement in NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationRequirement
    )
    return NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestation(
        continuity_epoch=_epoch(),
        reattestation_reference=f"status-reattestation:{status.value.lower()}:58",
        status=status,
        evidence=tuple(
            sorted(evidence, key=lambda item: (item.requirement.value, item.source_reference))
        ),
        exception_references=(
            ()
            if status is NIIRunAuditPhysicalAdapterProductionOperationalStatus.HEALTHY
            else ("incident:58",)
        ),
    )


def _intervention_evidence() -> (
    tuple[NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionEvidence, ...]
):
    return tuple(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionEvidence(
            requirement=requirement,
            source_reference=f"post-recovery-intervention:{requirement.value.lower()}",
        )
        for requirement in reversed(
            tuple(NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionRequirement)
        )
    )


@pytest.mark.parametrize(
    ("status", "action"),
    [
        (
            NIIRunAuditPhysicalAdapterProductionOperationalStatus.DEGRADED,
            NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND,
        ),
        (
            NIIRunAuditPhysicalAdapterProductionOperationalStatus.UNAVAILABLE,
            NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.DEACTIVATE,
        ),
    ],
)
def test_nonhealthy_reattestation_can_authorize_new_explicit_intervention(
    status: NIIRunAuditPhysicalAdapterProductionOperationalStatus,
    action: NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
) -> None:
    reattestation = _reattestation(status)

    authorization = NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationService.authorize(
        operational_status_reattestation=reattestation,
        authorization_reference="intervention-auth:post-recovery:58",
        action=action,
        evidence=_intervention_evidence(),
    )

    assert authorization.operational_status_reattestation is reattestation
    assert authorization.status is status
    assert authorization.action is action
    assert authorization.reattestation_reference == reattestation.reattestation_reference
    assert authorization.epoch_reference == reattestation.epoch_reference
    assert (
        authorization.previous_operations_reference == reattestation.previous_operations_reference
    )
    assert (
        authorization.previous_attestation_reference == reattestation.previous_attestation_reference
    )
    assert (
        authorization.recovery_acceptance_reference == reattestation.recovery_acceptance_reference
    )
    assert authorization.recovery_receipt_reference == reattestation.recovery_receipt_reference
    assert authorization.recovery_reference == reattestation.recovery_reference
    assert (
        authorization.previous_intervention_authorization_reference
        == reattestation.intervention_authorization_reference
    )
    assert authorization.adapter_reference == reattestation.adapter_reference
    assert authorization.environment_reference == reattestation.environment_reference
    assert authorization.artifact_reference == reattestation.artifact_reference
    assert tuple(item.requirement.value for item in authorization.evidence) == tuple(
        sorted(
            requirement.value
            for requirement in NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionRequirement
        )
    )


def test_healthy_reattestation_cannot_authorize_intervention() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationError,
        match="HEALTHY",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationService.authorize(
            operational_status_reattestation=_reattestation(
                NIIRunAuditPhysicalAdapterProductionOperationalStatus.HEALTHY
            ),
            authorization_reference="intervention-auth:post-recovery:healthy:58",
            action=NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND,
            evidence=_intervention_evidence(),
        )


def test_previous_authorization_reference_cannot_be_reused() -> None:
    reattestation = _reattestation(NIIRunAuditPhysicalAdapterProductionOperationalStatus.DEGRADED)

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationError,
        match="cannot reuse",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationService.authorize(
            operational_status_reattestation=reattestation,
            authorization_reference=reattestation.intervention_authorization_reference,
            action=NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND,
            evidence=_intervention_evidence(),
        )


def test_missing_or_duplicate_intervention_evidence_fails_closed() -> None:
    reattestation = _reattestation(NIIRunAuditPhysicalAdapterProductionOperationalStatus.DEGRADED)
    evidence = _intervention_evidence()

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationError,
        match="every required control",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationService.authorize(
            operational_status_reattestation=reattestation,
            authorization_reference="intervention-auth:post-recovery:missing:58",
            action=NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND,
            evidence=evidence[:-1],
        )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationError,
        match="Duplicate",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationService.authorize(
            operational_status_reattestation=reattestation,
            authorization_reference="intervention-auth:post-recovery:duplicate:58",
            action=NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND,
            evidence=(*evidence, evidence[0]),
        )


def test_blank_authorization_or_evidence_reference_is_rejected() -> None:
    reattestation = _reattestation(NIIRunAuditPhysicalAdapterProductionOperationalStatus.DEGRADED)

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationError,
        match="authorization_reference",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationService.authorize(
            operational_status_reattestation=reattestation,
            authorization_reference=" ",
            action=NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND,
            evidence=_intervention_evidence(),
        )

    with pytest.raises(ValueError, match="source_reference"):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionEvidence(
            requirement=(
                NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionRequirement.STATUS_REATTESTATION_VERIFIED
            ),
            source_reference=" ",
        )


def test_direct_authorization_requires_canonical_evidence() -> None:
    with pytest.raises(ValueError, match="evidence must be canonicalized"):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorization(
            operational_status_reattestation=_reattestation(
                NIIRunAuditPhysicalAdapterProductionOperationalStatus.DEGRADED
            ),
            authorization_reference="intervention-auth:post-recovery:direct:58",
            action=NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND,
            evidence=_intervention_evidence(),
        )


def test_malformed_upstream_reattestation_fails_closed() -> None:
    class _MalformedReattestation:
        reattestation_reference = "status-reattestation:malformed:58"
        status = NIIRunAuditPhysicalAdapterProductionOperationalStatus.DEGRADED
        exception_references = ("incident:58",)
        epoch_reference = "steady-state:same:58"
        previous_operations_reference = "steady-state:same:58"
        intervention_authorization_reference = "intervention-auth:previous:58"

    malformed = cast(
        NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestation,
        _MalformedReattestation(),
    )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationError,
        match="distinct continuity epoch",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationService.authorize(
            operational_status_reattestation=malformed,
            authorization_reference="intervention-auth:post-recovery:malformed:58",
            action=NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND,
            evidence=_intervention_evidence(),
        )


def test_nonhealthy_reattestation_without_exceptions_fails_closed() -> None:
    class _MalformedReattestation:
        reattestation_reference = "status-reattestation:no-exception:58"
        status = NIIRunAuditPhysicalAdapterProductionOperationalStatus.DEGRADED
        exception_references: tuple[str, ...] = ()
        epoch_reference = "steady-state:post-recovery:58"
        previous_operations_reference = "steady-state:pre-recovery:58"
        intervention_authorization_reference = "intervention-auth:previous:58"

    malformed = cast(
        NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestation,
        _MalformedReattestation(),
    )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationError,
        match="requires exceptions",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationService.authorize(
            operational_status_reattestation=malformed,
            authorization_reference="intervention-auth:post-recovery:no-exception:58",
            action=NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND,
            evidence=_intervention_evidence(),
        )
