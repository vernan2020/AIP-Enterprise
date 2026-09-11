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
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_readiness import (
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_REQUIREMENTS,
    NIIRunAuditPhysicalAdapterProductionEvidence,
    NIIRunAuditPhysicalAdapterProductionReadinessError,
    NIIRunAuditPhysicalAdapterProductionReadinessStatus,
    NIIRunAuditPhysicalAdapterProductionRequirement,
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
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_readiness_service import (
    NIIRunAuditPhysicalAdapterProductionReadinessService,
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


def _certification_bundle() -> NIIRunAuditPhysicalAdapterCertificationBundle:
    schema_contract = _schema_contract()
    readiness = NIIAuditPersistenceReadinessAssessment(
        adapter_reference="adapter-v1",
        status=NIIAuditPersistenceReadinessStatus.READY,
        certified_requirements=REQUIRED_NII_AUDIT_PERSISTENCE_REQUIREMENTS,
        missing_requirements=frozenset(),
        evidence=(
            NIIAuditPersistenceEvidence(
                requirement=NIIAuditPersistenceRequirement.ATOMIC_PUT_IF_ABSENT,
                source_reference="repo-conformance-report",
            ),
        ),
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
    activated = NIIRunAuditActivatedPhysicalPersistence(
        authorization=authorization,
        descriptor=NIIRunAuditPhysicalPersistenceDescriptor(
            adapter_reference="adapter-v1",
            schema_contract=schema_contract,
            codec_reference="codec-v1",
            integrity_reference="integrity-v1",
        ),
        repository=_Repository(),
    )
    return NIIRunAuditPhysicalAdapterCertificationService.certify(
        certification_reference="physical-adapter-cert-v1",
        activated_persistence=activated,
        evidence_references=("activation-policy", "repo-conformance-report"),
    )


def _production_evidence(
    requirement: NIIRunAuditPhysicalAdapterProductionRequirement,
) -> NIIRunAuditPhysicalAdapterProductionEvidence:
    return NIIRunAuditPhysicalAdapterProductionEvidence(
        requirement=requirement,
        source_reference=f"evidence:{requirement.value.lower()}",
    )


def test_complete_production_evidence_yields_ready_assessment() -> None:
    bundle = _certification_bundle()
    evidence = tuple(
        _production_evidence(requirement)
        for requirement in reversed(
            tuple(NIIRunAuditPhysicalAdapterProductionRequirement)
        )
    )

    assessment = NIIRunAuditPhysicalAdapterProductionReadinessService.assess(
        certification_bundle=bundle,
        environment_reference="production-cr-primary",
        evidence=evidence,
    )

    assert assessment.status is NIIRunAuditPhysicalAdapterProductionReadinessStatus.READY
    assert assessment.is_ready
    assert assessment.certification_bundle is bundle
    assert assessment.adapter_reference == "adapter-v1"
    assert (
        assessment.certified_requirements
        == REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_REQUIREMENTS
    )
    assert assessment.missing_requirements == frozenset()
    assert tuple(item.requirement.value for item in assessment.evidence) == tuple(
        sorted(requirement.value for requirement in NIIRunAuditPhysicalAdapterProductionRequirement)
    )


def test_missing_requirement_yields_blocked_assessment() -> None:
    bundle = _certification_bundle()
    omitted = NIIRunAuditPhysicalAdapterProductionRequirement.ROLLBACK_PATH_VALIDATED
    evidence = tuple(
        _production_evidence(requirement)
        for requirement in NIIRunAuditPhysicalAdapterProductionRequirement
        if requirement is not omitted
    )

    assessment = NIIRunAuditPhysicalAdapterProductionReadinessService.assess(
        certification_bundle=bundle,
        environment_reference="production-cr-primary",
        evidence=evidence,
    )

    assert assessment.status is NIIRunAuditPhysicalAdapterProductionReadinessStatus.BLOCKED
    assert not assessment.is_ready
    assert assessment.missing_requirements == frozenset({omitted})


def test_no_evidence_fails_closed_as_blocked() -> None:
    assessment = NIIRunAuditPhysicalAdapterProductionReadinessService.assess(
        certification_bundle=_certification_bundle(),
        environment_reference="production-cr-primary",
        evidence=(),
    )

    assert assessment.status is NIIRunAuditPhysicalAdapterProductionReadinessStatus.BLOCKED
    assert (
        assessment.missing_requirements
        == REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_REQUIREMENTS
    )


def test_duplicate_requirement_evidence_is_rejected() -> None:
    requirement = (
        NIIRunAuditPhysicalAdapterProductionRequirement.TARGET_ENVIRONMENT_IDENTIFIED
    )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionReadinessError,
        match="Duplicate",
    ):
        NIIRunAuditPhysicalAdapterProductionReadinessService.assess(
            certification_bundle=_certification_bundle(),
            environment_reference="production-cr-primary",
            evidence=(
                _production_evidence(requirement),
                NIIRunAuditPhysicalAdapterProductionEvidence(
                    requirement=requirement,
                    source_reference="second-environment-evidence",
                ),
            ),
        )


def test_blank_environment_reference_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionReadinessError,
        match="environment_reference",
    ):
        NIIRunAuditPhysicalAdapterProductionReadinessService.assess(
            certification_bundle=_certification_bundle(),
            environment_reference=" ",
            evidence=(),
        )
