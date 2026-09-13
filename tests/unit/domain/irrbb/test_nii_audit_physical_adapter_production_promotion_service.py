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
from aip.domain.irrbb.nii_audit_physical_adapter_production_promotion import (
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_PROMOTION_REQUIREMENTS,
    NIIRunAuditPhysicalAdapterProductionPromotionError,
    NIIRunAuditPhysicalAdapterProductionPromotionEvidence,
    NIIRunAuditPhysicalAdapterProductionPromotionRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_readiness import (
    NIIRunAuditPhysicalAdapterProductionEvidence,
    NIIRunAuditPhysicalAdapterProductionReadinessAssessment,
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
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_promotion_service import (
    NIIRunAuditPhysicalAdapterProductionPromotionService,
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


def _production_readiness_evidence(
    requirement: NIIRunAuditPhysicalAdapterProductionRequirement,
) -> NIIRunAuditPhysicalAdapterProductionEvidence:
    return NIIRunAuditPhysicalAdapterProductionEvidence(
        requirement=requirement,
        source_reference=f"readiness:{requirement.value.lower()}",
    )


def _ready_assessment() -> NIIRunAuditPhysicalAdapterProductionReadinessAssessment:
    return NIIRunAuditPhysicalAdapterProductionReadinessService.assess(
        certification_bundle=_certification_bundle(),
        environment_reference="production-cr-primary",
        evidence=tuple(
            _production_readiness_evidence(requirement)
            for requirement in NIIRunAuditPhysicalAdapterProductionRequirement
        ),
    )


def _blocked_assessment() -> NIIRunAuditPhysicalAdapterProductionReadinessAssessment:
    return NIIRunAuditPhysicalAdapterProductionReadinessService.assess(
        certification_bundle=_certification_bundle(),
        environment_reference="production-cr-primary",
        evidence=(),
    )


def _promotion_evidence(
    requirement: NIIRunAuditPhysicalAdapterProductionPromotionRequirement,
) -> NIIRunAuditPhysicalAdapterProductionPromotionEvidence:
    return NIIRunAuditPhysicalAdapterProductionPromotionEvidence(
        requirement=requirement,
        source_reference=f"authorization:{requirement.value.lower()}",
    )


def test_complete_governance_evidence_yields_authorization() -> None:
    readiness = _ready_assessment()
    evidence = tuple(
        _promotion_evidence(requirement)
        for requirement in reversed(tuple(NIIRunAuditPhysicalAdapterProductionPromotionRequirement))
    )

    authorization = NIIRunAuditPhysicalAdapterProductionPromotionService.authorize(
        readiness_assessment=readiness,
        authorization_reference="promotion-auth-2026-09-11",
        evidence=evidence,
    )

    assert authorization.readiness_assessment is readiness
    assert authorization.authorization_reference == "promotion-auth-2026-09-11"
    assert authorization.adapter_reference == "adapter-v1"
    assert authorization.environment_reference == "production-cr-primary"
    assert frozenset(item.requirement for item in authorization.evidence) == (
        REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_PROMOTION_REQUIREMENTS
    )
    assert tuple(item.requirement.value for item in authorization.evidence) == tuple(
        sorted(
            requirement.value
            for requirement in NIIRunAuditPhysicalAdapterProductionPromotionRequirement
        )
    )


def test_blocked_production_readiness_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPromotionError,
        match="READY assessment",
    ):
        NIIRunAuditPhysicalAdapterProductionPromotionService.authorize(
            readiness_assessment=_blocked_assessment(),
            authorization_reference="promotion-auth-2026-09-11",
            evidence=tuple(
                _promotion_evidence(requirement)
                for requirement in NIIRunAuditPhysicalAdapterProductionPromotionRequirement
            ),
        )


def test_missing_governance_evidence_is_rejected() -> None:
    omitted = NIIRunAuditPhysicalAdapterProductionPromotionRequirement.ROLLBACK_AUTHORITY_CONFIRMED
    evidence = tuple(
        _promotion_evidence(requirement)
        for requirement in NIIRunAuditPhysicalAdapterProductionPromotionRequirement
        if requirement is not omitted
    )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPromotionError,
        match="ROLLBACK_AUTHORITY_CONFIRMED",
    ):
        NIIRunAuditPhysicalAdapterProductionPromotionService.authorize(
            readiness_assessment=_ready_assessment(),
            authorization_reference="promotion-auth-2026-09-11",
            evidence=evidence,
        )


def test_duplicate_governance_evidence_is_rejected() -> None:
    requirement = (
        NIIRunAuditPhysicalAdapterProductionPromotionRequirement.CHANGE_AUTHORIZATION_RECORDED
    )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPromotionError,
        match="Duplicate",
    ):
        NIIRunAuditPhysicalAdapterProductionPromotionService.authorize(
            readiness_assessment=_ready_assessment(),
            authorization_reference="promotion-auth-2026-09-11",
            evidence=(
                _promotion_evidence(requirement),
                NIIRunAuditPhysicalAdapterProductionPromotionEvidence(
                    requirement=requirement,
                    source_reference="authorization:duplicate-change-approval",
                ),
            ),
        )


def test_blank_authorization_reference_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPromotionError,
        match="authorization_reference",
    ):
        NIIRunAuditPhysicalAdapterProductionPromotionService.authorize(
            readiness_assessment=_ready_assessment(),
            authorization_reference=" ",
            evidence=(),
        )
