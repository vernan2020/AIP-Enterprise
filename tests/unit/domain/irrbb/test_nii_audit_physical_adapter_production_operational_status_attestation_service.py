from __future__ import annotations

from typing import cast

import pytest

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_status_attestation import (
    NIIRunAuditPhysicalAdapterProductionOperationalStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestationError,
    NIIRunAuditPhysicalAdapterProductionOperationalStatusEvidence,
    NIIRunAuditPhysicalAdapterProductionOperationalStatusRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_steady_state_operations import (
    NIIRunAuditPhysicalAdapterProductionSteadyStateOperations,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_operational_status_attestation_service import (
    NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestationService,
)


class _SteadyStateOperationsStub:
    operations_reference = "steady-state:2026-09-11"
    runtime_activation_acceptance_reference = "runtime-acceptance:2026-09-11"
    adapter_reference = "adapter-v1"
    environment_reference = "production-cr-primary"
    artifact_reference = "artifact:nii-audit-adapter-v1"


def _operations() -> NIIRunAuditPhysicalAdapterProductionSteadyStateOperations:
    return cast(
        NIIRunAuditPhysicalAdapterProductionSteadyStateOperations,
        _SteadyStateOperationsStub(),
    )


def _evidence() -> tuple[NIIRunAuditPhysicalAdapterProductionOperationalStatusEvidence, ...]:
    return tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalStatusEvidence(
            requirement=requirement,
            source_reference=f"status:{requirement.value.lower()}",
        )
        for requirement in reversed(
            tuple(NIIRunAuditPhysicalAdapterProductionOperationalStatusRequirement)
        )
    )


def test_healthy_attestation_retains_exact_phase48_record_without_exceptions() -> None:
    operations = _operations()

    attestation = NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestationService.attest(
        steady_state_operations=operations,
        attestation_reference="status:2026-09-11T22:00",
        status=NIIRunAuditPhysicalAdapterProductionOperationalStatus.HEALTHY,
        evidence=_evidence(),
    )

    assert attestation.steady_state_operations is operations
    assert attestation.status is NIIRunAuditPhysicalAdapterProductionOperationalStatus.HEALTHY
    assert attestation.exception_references == ()
    assert attestation.operations_reference == operations.operations_reference
    assert attestation.adapter_reference == operations.adapter_reference
    assert tuple(item.requirement.value for item in attestation.evidence) == tuple(
        sorted(
            requirement.value
            for requirement in NIIRunAuditPhysicalAdapterProductionOperationalStatusRequirement
        )
    )


def test_degraded_attestation_requires_and_canonicalizes_exception_references() -> None:
    attestation = NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestationService.attest(
        steady_state_operations=_operations(),
        attestation_reference="status:degraded:001",
        status=NIIRunAuditPhysicalAdapterProductionOperationalStatus.DEGRADED,
        evidence=_evidence(),
        exception_references=("incident:002", "incident:001"),
    )

    assert attestation.exception_references == ("incident:001", "incident:002")


def test_healthy_attestation_rejects_exception_references() -> None:
    with pytest.raises(ValueError, match="HEALTHY"):
        NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestationService.attest(
            steady_state_operations=_operations(),
            attestation_reference="status:healthy:invalid",
            status=NIIRunAuditPhysicalAdapterProductionOperationalStatus.HEALTHY,
            evidence=_evidence(),
            exception_references=("incident:unexpected",),
        )


def test_non_healthy_attestation_requires_exception_reference() -> None:
    with pytest.raises(ValueError, match="requires at least one exception reference"):
        NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestationService.attest(
            steady_state_operations=_operations(),
            attestation_reference="status:unavailable:invalid",
            status=NIIRunAuditPhysicalAdapterProductionOperationalStatus.UNAVAILABLE,
            evidence=_evidence(),
        )


def test_missing_status_control_fails_closed() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestationError,
        match="must cover every required status control",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestationService.attest(
            steady_state_operations=_operations(),
            attestation_reference="status:missing-control",
            status=NIIRunAuditPhysicalAdapterProductionOperationalStatus.HEALTHY,
            evidence=_evidence()[:-1],
        )


def test_duplicate_exception_reference_fails_closed() -> None:
    with pytest.raises(ValueError, match="Duplicate.*exception reference"):
        NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestationService.attest(
            steady_state_operations=_operations(),
            attestation_reference="status:duplicate-exception",
            status=NIIRunAuditPhysicalAdapterProductionOperationalStatus.DEGRADED,
            evidence=_evidence(),
            exception_references=("incident:001", "incident:001"),
        )
