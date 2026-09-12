from __future__ import annotations

from typing import cast

import pytest

from aip.domain.irrbb.nii_audit_physical_adapter_production_runtime_activation_acceptance import (
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptance,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_steady_state_operations import (
    NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsError,
    NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsEvidence,
    NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsRequirement,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_steady_state_operations_service import (
    NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsService,
)


class _AcceptanceStub:
    acceptance_reference = "runtime-acceptance:2026-09-11"
    runtime_activation_receipt_reference = "runtime-receipt:2026-09-11"
    activation_reference = "runtime-activation:2026-09-11"
    adapter_reference = "adapter-v1"
    environment_reference = "production-cr-primary"
    artifact_reference = "artifact:nii-audit-adapter-v1"


def _acceptance() -> NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptance:
    return cast(
        NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptance,
        _AcceptanceStub(),
    )


def _evidence() -> tuple[NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsEvidence, ...]:
    return tuple(
        NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsEvidence(
            requirement=requirement,
            source_reference=f"operations:{requirement.value.lower()}",
        )
        for requirement in reversed(
            tuple(NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsRequirement)
        )
    )


def test_records_exact_phase47_acceptance_and_canonical_evidence() -> None:
    acceptance = _acceptance()

    record = NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsService.record(
        activation_acceptance=acceptance,
        operations_reference="steady-state:2026-09-11",
        evidence=_evidence(),
    )

    assert record.activation_acceptance is acceptance
    assert record.operations_reference == "steady-state:2026-09-11"
    assert tuple(item.requirement.value for item in record.evidence) == tuple(
        sorted(requirement.value for requirement in NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsRequirement)
    )
    assert record.runtime_activation_acceptance_reference == acceptance.acceptance_reference
    assert record.runtime_activation_receipt_reference == acceptance.runtime_activation_receipt_reference
    assert record.activation_reference == acceptance.activation_reference
    assert record.adapter_reference == acceptance.adapter_reference
    assert record.environment_reference == acceptance.environment_reference
    assert record.artifact_reference == acceptance.artifact_reference


def test_blank_operations_reference_fails_closed() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsError,
        match="operations_reference is required",
    ):
        NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsService.record(
            activation_acceptance=_acceptance(),
            operations_reference=" ",
            evidence=_evidence(),
        )


def test_missing_operations_control_fails_closed() -> None:
    evidence = _evidence()[:-1]

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsError,
        match="must cover every required operations control",
    ):
        NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsService.record(
            activation_acceptance=_acceptance(),
            operations_reference="steady-state:2026-09-11",
            evidence=evidence,
        )


def test_duplicate_operations_control_fails_closed() -> None:
    evidence = _evidence()

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsError,
        match="Duplicate",
    ):
        NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsService.record(
            activation_acceptance=_acceptance(),
            operations_reference="steady-state:2026-09-11",
            evidence=(*evidence, evidence[0]),
        )


def test_blank_evidence_source_reference_is_rejected() -> None:
    with pytest.raises(ValueError, match="source_reference is required"):
        NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsEvidence(
            requirement=(
                NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsRequirement.SERVICE_OWNERSHIP_CONFIRMED
            ),
            source_reference=" ",
        )
