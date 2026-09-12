from __future__ import annotations

import pytest

from aip.domain.irrbb.nii_audit_persistence_activation import (
    NIIRunAuditPersistenceActivationAuthorization,
    NIIRunAuditPersistenceActivationConfiguration,
)
from aip.domain.irrbb.nii_audit_persistence_readiness import (
    REQUIRED_NII_AUDIT_PERSISTENCE_REQUIREMENTS,
    NIIAuditPersistenceEvidence,
    NIIAuditPersistenceReadinessAssessment,
    NIIAuditPersistenceReadinessStatus,
    NIIAuditPersistenceRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_certification import (
    NIIRunAuditPhysicalAdapterCertificationBundle,
    NIIRunAuditPhysicalAdapterCertificationError,
)
from aip.domain.irrbb.nii_audit_physical_persistence import (
    NIIRunAuditActivatedPhysicalPersistence,
    NIIRunAuditPhysicalPersistenceDescriptor,
)
from aip.domain.irrbb.nii_audit_schema_evolution import (
    NIIAuditSchemaEvolutionContract,
    NIIAuditSchemaVersion,
)
from aip.domain.irrbb.nii_audit_serialization_compatibility import (
    NIIAuditReadableSchemaCompatibility,
    NIIRunAuditSerializationCompatibilityCertificate,
)
from aip.domain.irrbb.nii_run_audit import NIIRunAuditRepositoryPutResult
from aip.domain.irrbb.services.nii_audit_physical_adapter_certification_service import (
    NIIRunAuditPhysicalAdapterCertificationService,
)


class _Repository:
    def get_by_run_reference(self, *, run_reference: str):
        return None

    def put_if_absent(self, *, record):
        return NIIRunAuditRepositoryPutResult(created=True, record=record)


def _schema_contract() -> NIIAuditSchemaEvolutionContract:
    version = NIIAuditSchemaVersion(schema_reference="nii-audit", version=1)
    return NIIAuditSchemaEvolutionContract(
        current_version=version,
        readable_versions=frozenset({version}),
        migration_steps=(),
        source_reference="schema-policy",
    )


def _readiness_evidence(*, complete: bool) -> tuple[NIIAuditPersistenceEvidence, ...]:
    requirements = (
        sorted(REQUIRED_NII_AUDIT_PERSISTENCE_REQUIREMENTS, key=lambda item: item.value)
        if complete
        else (NIIAuditPersistenceRequirement.ATOMIC_PUT_IF_ABSENT,)
    )
    return tuple(
        NIIAuditPersistenceEvidence(
            requirement=requirement,
            source_reference="repo-conformance-report",
        )
        for requirement in requirements
    )


def _activated(*, complete_readiness_evidence: bool = True) -> NIIRunAuditActivatedPhysicalPersistence:
    schema_contract = _schema_contract()
    readiness = NIIAuditPersistenceReadinessAssessment(
        adapter_reference="adapter-v1",
        status=NIIAuditPersistenceReadinessStatus.READY,
        certified_requirements=REQUIRED_NII_AUDIT_PERSISTENCE_REQUIREMENTS,
        missing_requirements=frozenset(),
        evidence=_readiness_evidence(complete=complete_readiness_evidence),
    )
    compatibility = NIIRunAuditSerializationCompatibilityCertificate(
        schema_contract=schema_contract,
        codec_reference="codec-v1",
        integrity_reference="integrity-v1",
        readable_schema_compatibility=(
            NIIAuditReadableSchemaCompatibility(
                source_version=schema_contract.current_version,
                migration_steps=(),
                transformer_references=(),
            ),
        ),
    )
    configuration = NIIRunAuditPersistenceActivationConfiguration(
        adapter_reference="adapter-v1",
        schema_contract=schema_contract,
        codec_reference="codec-v1",
        integrity_reference="integrity-v1",
        source_reference="activation-policy",
    )
    authorization = NIIRunAuditPersistenceActivationAuthorization(
        configuration=configuration,
        readiness=readiness,
        compatibility=compatibility,
    )
    descriptor = NIIRunAuditPhysicalPersistenceDescriptor(
        adapter_reference="adapter-v1",
        schema_contract=schema_contract,
        codec_reference="codec-v1",
        integrity_reference="integrity-v1",
    )
    return NIIRunAuditActivatedPhysicalPersistence(
        authorization=authorization,
        descriptor=descriptor,
        repository=_Repository(),
    )


def _complete_bundle_evidence() -> tuple[str, ...]:
    return (
        "activation-policy",
        "ci-certification-run",
        "repo-conformance-report",
        "schema-policy",
    )


def test_certification_bundle_preserves_exact_activated_chain() -> None:
    activated = _activated()

    bundle = NIIRunAuditPhysicalAdapterCertificationService.certify(
        certification_reference="physical-adapter-cert-2026-09",
        activated_persistence=activated,
        evidence_references=_complete_bundle_evidence(),
    )

    assert bundle.activated_persistence is activated
    assert bundle.authorization is activated.authorization
    assert bundle.readiness is activated.authorization.readiness
    assert bundle.compatibility is activated.authorization.compatibility
    assert bundle.descriptor is activated.descriptor
    assert bundle.repository is activated.repository
    assert bundle.evidence_references == _complete_bundle_evidence()


@pytest.mark.parametrize(
    "evidence_references",
    [
        ("activation-policy", "repo-conformance-report"),
        ("repo-conformance-report", "schema-policy"),
        ("activation-policy", "schema-policy"),
    ],
)
def test_missing_prerequisite_evidence_blocks_certification(
    evidence_references: tuple[str, ...],
) -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterCertificationError,
        match="missing prerequisite evidence",
    ):
        NIIRunAuditPhysicalAdapterCertificationService.certify(
            certification_reference="cert-v1",
            activated_persistence=_activated(),
            evidence_references=evidence_references,
        )


def test_ready_assessment_without_complete_capability_evidence_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterCertificationError,
        match="explicit evidence for every persistence capability",
    ):
        NIIRunAuditPhysicalAdapterCertificationService.certify(
            certification_reference="cert-v1",
            activated_persistence=_activated(complete_readiness_evidence=False),
            evidence_references=_complete_bundle_evidence(),
        )


def test_duplicate_evidence_reference_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterCertificationError,
        match="Duplicate",
    ):
        NIIRunAuditPhysicalAdapterCertificationService.certify(
            certification_reference="cert-v1",
            activated_persistence=_activated(),
            evidence_references=(
                "activation-policy",
                "repo-conformance-report",
                "repo-conformance-report",
                "schema-policy",
            ),
        )


def test_blank_certification_reference_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterCertificationError,
        match="certification_reference",
    ):
        NIIRunAuditPhysicalAdapterCertificationService.certify(
            certification_reference=" ",
            activated_persistence=_activated(),
            evidence_references=_complete_bundle_evidence(),
        )


def test_bundle_requires_canonical_evidence_order() -> None:
    activated = _activated()

    with pytest.raises(ValueError, match="canonicalized"):
        NIIRunAuditPhysicalAdapterCertificationBundle(
            certification_reference="cert-v1",
            activated_persistence=activated,
            evidence_references=(
                "schema-policy",
                "repo-conformance-report",
                "ci-certification-run",
                "activation-policy",
            ),
        )
