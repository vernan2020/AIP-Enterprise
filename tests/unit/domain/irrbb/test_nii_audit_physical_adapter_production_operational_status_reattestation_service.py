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
    NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationError,
    NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationEvidence,
    NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationRequirement,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_operational_status_reattestation_service import (
    NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationService,
)


class _ContinuityEpochStub:
    epoch_reference = "steady-state:post-recovery:57"
    previous_operations_reference = "steady-state:pre-recovery:57"
    attestation_reference = "status:pre-recovery:57"
    recovery_acceptance_reference = "recovery-acceptance:57"
    recovery_receipt_reference = "recovery-receipt:57"
    recovery_reference = "recovery-execution:57"
    recovery_authorization_reference = "recovery-auth:57"
    recovery_action = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME
    intervention_acceptance_reference = "intervention-acceptance:57"
    intervention_receipt_reference = "intervention-receipt:57"
    intervention_reference = "intervention-execution:57"
    intervention_authorization_reference = "intervention-auth:57"
    intervention_action = NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
    adapter_reference = "adapter-v1"
    environment_reference = "production-cr-primary"
    artifact_reference = "artifact:nii-audit-adapter-v1"


def _epoch() -> NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpoch:
    return cast(
        NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpoch,
        _ContinuityEpochStub(),
    )


def _evidence() -> tuple[
    NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationEvidence, ...
]:
    return tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationEvidence(
            requirement=requirement,
            source_reference=f"reattestation:{requirement.value.lower()}",
        )
        for requirement in reversed(
            tuple(
                NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationRequirement
            )
        )
    )


def test_healthy_reattestation_preserves_exact_epoch_and_chain_without_exceptions() -> None:
    epoch = _epoch()

    reattestation = (
        NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationService.attest(
            continuity_epoch=epoch,
            reattestation_reference="status-reattestation:healthy:57",
            status=NIIRunAuditPhysicalAdapterProductionOperationalStatus.HEALTHY,
            evidence=_evidence(),
        )
    )

    assert reattestation.continuity_epoch is epoch
    assert reattestation.status is NIIRunAuditPhysicalAdapterProductionOperationalStatus.HEALTHY
    assert reattestation.exception_references == ()
    assert reattestation.epoch_reference == epoch.epoch_reference
    assert reattestation.previous_operations_reference == epoch.previous_operations_reference
    assert reattestation.previous_attestation_reference == epoch.attestation_reference
    assert reattestation.recovery_acceptance_reference == epoch.recovery_acceptance_reference
    assert reattestation.recovery_receipt_reference == epoch.recovery_receipt_reference
    assert reattestation.recovery_reference == epoch.recovery_reference
    assert (
        reattestation.recovery_action
        is NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME
    )
    assert (
        reattestation.intervention_action
        is NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
    )
    assert reattestation.adapter_reference == epoch.adapter_reference
    assert reattestation.environment_reference == epoch.environment_reference
    assert reattestation.artifact_reference == epoch.artifact_reference
    assert tuple(item.requirement.value for item in reattestation.evidence) == tuple(
        sorted(
            requirement.value
            for requirement in NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationRequirement
        )
    )


def test_degraded_reattestation_requires_and_canonicalizes_exceptions() -> None:
    reattestation = (
        NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationService.attest(
            continuity_epoch=_epoch(),
            reattestation_reference="status-reattestation:degraded:57",
            status=NIIRunAuditPhysicalAdapterProductionOperationalStatus.DEGRADED,
            evidence=_evidence(),
            exception_references=("incident:002", "incident:001"),
        )
    )

    assert reattestation.exception_references == ("incident:001", "incident:002")


def test_unavailable_reattestation_requires_exception_reference() -> None:
    with pytest.raises(ValueError, match="requires at least one exception reference"):
        NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationService.attest(
            continuity_epoch=_epoch(),
            reattestation_reference="status-reattestation:unavailable:57",
            status=NIIRunAuditPhysicalAdapterProductionOperationalStatus.UNAVAILABLE,
            evidence=_evidence(),
        )


def test_healthy_reattestation_rejects_exception_references() -> None:
    with pytest.raises(ValueError, match="HEALTHY"):
        NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationService.attest(
            continuity_epoch=_epoch(),
            reattestation_reference="status-reattestation:healthy-invalid:57",
            status=NIIRunAuditPhysicalAdapterProductionOperationalStatus.HEALTHY,
            evidence=_evidence(),
            exception_references=("incident:unexpected",),
        )


def test_blank_reattestation_reference_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationError,
        match="reattestation_reference",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationService.attest(
            continuity_epoch=_epoch(),
            reattestation_reference=" ",
            status=NIIRunAuditPhysicalAdapterProductionOperationalStatus.HEALTHY,
            evidence=_evidence(),
        )


def test_missing_or_duplicate_status_requirement_is_rejected() -> None:
    evidence = _evidence()

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationError,
        match="cover every required status control",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationService.attest(
            continuity_epoch=_epoch(),
            reattestation_reference="status-reattestation:missing:57",
            status=NIIRunAuditPhysicalAdapterProductionOperationalStatus.HEALTHY,
            evidence=evidence[:-1],
        )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationError,
        match="Duplicate",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationService.attest(
            continuity_epoch=_epoch(),
            reattestation_reference="status-reattestation:duplicate:57",
            status=NIIRunAuditPhysicalAdapterProductionOperationalStatus.HEALTHY,
            evidence=(*evidence, evidence[0]),
        )


def test_blank_evidence_or_exception_reference_is_rejected() -> None:
    with pytest.raises(ValueError, match="source_reference"):
        NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationEvidence(
            requirement=(
                NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationRequirement.CONTINUITY_EPOCH_VERIFIED
            ),
            source_reference=" ",
        )

    with pytest.raises(ValueError, match="exception reference must be nonblank"):
        NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationService.attest(
            continuity_epoch=_epoch(),
            reattestation_reference="status-reattestation:blank-exception:57",
            status=NIIRunAuditPhysicalAdapterProductionOperationalStatus.DEGRADED,
            evidence=_evidence(),
            exception_references=(" ",),
        )


def test_duplicate_exception_reference_is_rejected() -> None:
    with pytest.raises(ValueError, match="Duplicate.*exception reference"):
        NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationService.attest(
            continuity_epoch=_epoch(),
            reattestation_reference="status-reattestation:duplicate-exception:57",
            status=NIIRunAuditPhysicalAdapterProductionOperationalStatus.DEGRADED,
            evidence=_evidence(),
            exception_references=("incident:001", "incident:001"),
        )


def test_direct_reattestation_requires_canonical_evidence_and_exceptions() -> None:
    with pytest.raises(ValueError, match="evidence must be canonicalized"):
        NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestation(
            continuity_epoch=_epoch(),
            reattestation_reference="status-reattestation:direct-evidence:57",
            status=NIIRunAuditPhysicalAdapterProductionOperationalStatus.HEALTHY,
            evidence=_evidence(),
        )

    canonical_evidence = tuple(
        sorted(
            _evidence(),
            key=lambda item: (item.requirement.value, item.source_reference),
        )
    )
    with pytest.raises(ValueError, match="exception references must be canonicalized"):
        NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestation(
            continuity_epoch=_epoch(),
            reattestation_reference="status-reattestation:direct-exceptions:57",
            status=NIIRunAuditPhysicalAdapterProductionOperationalStatus.DEGRADED,
            evidence=canonical_evidence,
            exception_references=("incident:002", "incident:001"),
        )


def test_invalid_continuity_epoch_is_rejected_fail_closed() -> None:
    class _InvalidEpochStub(_ContinuityEpochStub):
        epoch_reference = "steady-state:pre-recovery:57"

    invalid_epoch = cast(
        NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpoch,
        _InvalidEpochStub(),
    )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationError,
        match="distinct continuity epoch",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationService.attest(
            continuity_epoch=invalid_epoch,
            reattestation_reference="status-reattestation:invalid-epoch:57",
            status=NIIRunAuditPhysicalAdapterProductionOperationalStatus.HEALTHY,
            evidence=_evidence(),
        )
