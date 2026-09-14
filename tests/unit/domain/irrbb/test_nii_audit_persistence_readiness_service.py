from __future__ import annotations

import pytest

from aip.domain.irrbb.nii_audit_persistence_readiness import (
    REQUIRED_NII_AUDIT_PERSISTENCE_REQUIREMENTS,
    NIIAuditPersistenceEvidence,
    NIIAuditPersistenceReadinessStatus,
)
from aip.domain.irrbb.services.nii_audit_persistence_readiness_service import (
    NIIAuditPersistenceReadinessService,
)


def _evidence_for_all_requirements() -> tuple[NIIAuditPersistenceEvidence, ...]:
    return tuple(
        NIIAuditPersistenceEvidence(
            requirement=requirement,
            source_reference=f"certification:{requirement.value}:2026-09-11",
        )
        for requirement in REQUIRED_NII_AUDIT_PERSISTENCE_REQUIREMENTS
    )


def test_all_required_capabilities_are_ready() -> None:
    evidence = _evidence_for_all_requirements()

    assessment = NIIAuditPersistenceReadinessService.assess(
        adapter_reference="adapter:audit-store:v1",
        evidence=evidence,
    )

    assert assessment.status is NIIAuditPersistenceReadinessStatus.READY
    assert assessment.is_ready is True
    assert assessment.certified_requirements == REQUIRED_NII_AUDIT_PERSISTENCE_REQUIREMENTS
    assert assessment.missing_requirements == frozenset()
    assert assessment.evidence == evidence


def test_missing_capability_blocks_with_exact_requirement() -> None:
    evidence = _evidence_for_all_requirements()[:-1]
    expected_missing = REQUIRED_NII_AUDIT_PERSISTENCE_REQUIREMENTS - {
        item.requirement for item in evidence
    }

    assessment = NIIAuditPersistenceReadinessService.assess(
        adapter_reference="adapter:audit-store:v1",
        evidence=evidence,
    )

    assert assessment.status is NIIAuditPersistenceReadinessStatus.BLOCKED
    assert assessment.is_ready is False
    assert assessment.missing_requirements == expected_missing


def test_duplicate_certification_evidence_fails_closed() -> None:
    first = _evidence_for_all_requirements()[0]

    with pytest.raises(ValueError, match="Duplicate NII audit persistence evidence"):
        NIIAuditPersistenceReadinessService.assess(
            adapter_reference="adapter:audit-store:v1",
            evidence=(first, first),
        )


def test_blank_adapter_reference_is_rejected() -> None:
    with pytest.raises(ValueError, match="adapter_reference is required"):
        NIIAuditPersistenceReadinessService.assess(
            adapter_reference=" ",
            evidence=(),
        )


def test_blank_evidence_source_reference_is_rejected() -> None:
    requirement = next(iter(REQUIRED_NII_AUDIT_PERSISTENCE_REQUIREMENTS))

    with pytest.raises(ValueError, match="source_reference is required"):
        NIIAuditPersistenceEvidence(
            requirement=requirement,
            source_reference=" ",
        )
