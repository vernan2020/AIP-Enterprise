from __future__ import annotations

from typing import cast

import pytest

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_continuity_epoch import (
    NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpoch,
    NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochError,
    NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochEvidence,
    NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_acceptance import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptance,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceEvidence,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorization,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_receipt import (
    NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINT_ORDER,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointResult,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceipt,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_operational_continuity_epoch_service import (
    NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochService,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_operational_recovery_acceptance_service import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceService,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_operational_recovery_receipt_service import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceiptService,
)


class _RecoveryAuthorizationStub:
    authorization_reference = "recovery-auth:56"
    action = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME
    intervention_acceptance_reference = "intervention-acceptance:56"
    intervention_receipt_reference = "intervention-receipt:56"
    intervention_reference = "intervention-execution:56"
    intervention_authorization_reference = "intervention-auth:56"
    intervention_action = NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
    attestation_reference = "status:degraded:56"
    operations_reference = "steady-state:pre-recovery:56"
    adapter_reference = "adapter-v1"
    environment_reference = "production-cr-primary"
    artifact_reference = "artifact:nii-audit-adapter-v1"


def _recovery_authorization() -> (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorization
):
    return cast(
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorization,
        _RecoveryAuthorizationStub(),
    )


def _recovery_receipt(
    *,
    failed_index: int | None = None,
) -> NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceipt:
    results = []
    for index, checkpoint in enumerate(
        NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINT_ORDER
    ):
        status = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus.SUCCEEDED
        if index == failed_index:
            status = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus.FAILED
        results.append(
            NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointResult(
                checkpoint=checkpoint,
                status=status,
                evidence_reference=f"recovery-observed:{checkpoint.value.lower()}",
            )
        )
    return NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceiptService.record(
        recovery_authorization=_recovery_authorization(),
        receipt_reference="recovery-receipt:56",
        recovery_reference="recovery-execution:56",
        checkpoint_results=results,
    )


def _recovery_acceptance(
    *,
    receipt: NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceipt | None = None,
) -> NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptance:
    recovery_receipt = receipt or _recovery_receipt()
    evidence = tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceEvidence(
            requirement=requirement,
            source_reference=f"recovery-acceptance:{requirement.value.lower()}",
        )
        for requirement in NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceRequirement
    )
    return NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceService.accept(
        recovery_receipt=recovery_receipt,
        acceptance_reference="recovery-acceptance:56",
        evidence=evidence,
    )


def _epoch_evidence() -> tuple[
    NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochEvidence, ...
]:
    return tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochEvidence(
            requirement=requirement,
            source_reference=f"continuity:{requirement.value.lower()}",
        )
        for requirement in reversed(
            tuple(NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochRequirement)
        )
    )


def test_valid_epoch_preserves_exact_acceptance_and_chain_identity() -> None:
    acceptance = _recovery_acceptance()

    epoch = NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochService.record(
        recovery_acceptance=acceptance,
        epoch_reference="steady-state:post-recovery:56",
        evidence=_epoch_evidence(),
    )

    assert epoch.recovery_acceptance is acceptance
    assert epoch.recovery_acceptance_reference == acceptance.acceptance_reference
    assert epoch.recovery_receipt_reference == acceptance.recovery_receipt_reference
    assert epoch.recovery_reference == acceptance.recovery_reference
    assert epoch.recovery_authorization_reference == acceptance.recovery_authorization_reference
    assert epoch.recovery_action is NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME
    assert epoch.intervention_acceptance_reference == acceptance.intervention_acceptance_reference
    assert epoch.intervention_receipt_reference == acceptance.intervention_receipt_reference
    assert (
        epoch.intervention_action
        is NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
    )
    assert epoch.attestation_reference == acceptance.attestation_reference
    assert epoch.previous_operations_reference == acceptance.operations_reference
    assert epoch.adapter_reference == acceptance.adapter_reference
    assert epoch.environment_reference == acceptance.environment_reference
    assert epoch.artifact_reference == acceptance.artifact_reference
    assert epoch.epoch_reference != epoch.previous_operations_reference
    assert tuple(item.requirement.value for item in epoch.evidence) == tuple(
        sorted(
            requirement.value
            for requirement in NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochRequirement
        )
    )


def test_blank_epoch_reference_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochError,
        match="epoch_reference",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochService.record(
            recovery_acceptance=_recovery_acceptance(),
            epoch_reference=" ",
            evidence=_epoch_evidence(),
        )


def test_previous_operations_reference_cannot_be_reused_as_epoch_reference() -> None:
    acceptance = _recovery_acceptance()

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochError,
        match="must differ",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochService.record(
            recovery_acceptance=acceptance,
            epoch_reference=acceptance.operations_reference,
            evidence=_epoch_evidence(),
        )


def test_missing_or_duplicate_epoch_requirement_is_rejected() -> None:
    acceptance = _recovery_acceptance()
    evidence = _epoch_evidence()

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochError,
        match="cover every required control",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochService.record(
            recovery_acceptance=acceptance,
            epoch_reference="steady-state:post-recovery:missing",
            evidence=evidence[:-1],
        )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochError,
        match="Duplicate",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochService.record(
            recovery_acceptance=acceptance,
            epoch_reference="steady-state:post-recovery:duplicate",
            evidence=(*evidence, evidence[0]),
        )


def test_blank_evidence_source_reference_is_rejected() -> None:
    with pytest.raises(ValueError, match="source_reference"):
        NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochEvidence(
            requirement=(
                NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochRequirement.RECOVERY_ACCEPTANCE_VERIFIED
            ),
            source_reference=" ",
        )


def test_direct_epoch_requires_canonical_evidence() -> None:
    with pytest.raises(ValueError, match="must be canonicalized"):
        NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpoch(
            recovery_acceptance=_recovery_acceptance(),
            epoch_reference="steady-state:post-recovery:direct",
            evidence=_epoch_evidence(),
        )


def test_tampered_recovery_acceptance_is_rejected_fail_closed() -> None:
    successful_acceptance = _recovery_acceptance()
    failed_receipt = _recovery_receipt(failed_index=1)
    tampered_acceptance = cast(
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptance,
        object.__new__(NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptance),
    )
    object.__setattr__(tampered_acceptance, "recovery_receipt", failed_receipt)
    object.__setattr__(
        tampered_acceptance,
        "acceptance_reference",
        successful_acceptance.acceptance_reference,
    )
    object.__setattr__(tampered_acceptance, "evidence", successful_acceptance.evidence)

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochError,
        match="successful recovery receipt",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochService.record(
            recovery_acceptance=tampered_acceptance,
            epoch_reference="steady-state:post-recovery:tampered",
            evidence=_epoch_evidence(),
        )
