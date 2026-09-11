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
from aip.domain.irrbb.nii_audit_physical_adapter_production_deployment_execution_authorization import (
    NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorizationError,
    NIIRunAuditPhysicalAdapterProductionDeploymentExecutionEvidence,
    NIIRunAuditPhysicalAdapterProductionDeploymentExecutionRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_deployment_plan import (
    NIIRunAuditPhysicalAdapterProductionDeploymentStep,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_promotion import (
    NIIRunAuditPhysicalAdapterProductionPromotionEvidence,
    NIIRunAuditPhysicalAdapterProductionPromotionRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_readiness import (
    NIIRunAuditPhysicalAdapterProductionEvidence,
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
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_deployment_execution_authorization_service import (
    NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorizationService,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_deployment_plan_service import (
    NIIRunAuditPhysicalAdapterProductionDeploymentPlanService,
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
    activation = NIIRunAuditPersistenceActivationAuthorization(
        configuration=configuration,
        readiness=readiness,
        compatibility=compatibility,
    )
    activated = NIIRunAuditActivatedPhysicalPersistence(
        authorization=activation,
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


def _promotion_authorization():
    readiness = NIIRunAuditPhysicalAdapterProductionReadinessService.assess(
        certification_bundle=_certification_bundle(),
        environment_reference="production-cr-primary",
        evidence=tuple(
            NIIRunAuditPhysicalAdapterProductionEvidence(
                requirement=requirement,
                source_reference=f"readiness:{requirement.value.lower()}",
            )
            for requirement in NIIRunAuditPhysicalAdapterProductionRequirement
        ),
    )
    return NIIRunAuditPhysicalAdapterProductionPromotionService.authorize(
        readiness_assessment=readiness,
        authorization_reference="promotion-auth-2026-09-11",
        evidence=tuple(
            NIIRunAuditPhysicalAdapterProductionPromotionEvidence(
                requirement=requirement,
                source_reference=f"promotion:{requirement.value.lower()}",
            )
            for requirement in NIIRunAuditPhysicalAdapterProductionPromotionRequirement
        ),
    )


def _deployment_plan():
    return NIIRunAuditPhysicalAdapterProductionDeploymentPlanService.build(
        promotion_authorization=_promotion_authorization(),
        plan_reference="deployment-plan-2026-09-11",
        release_reference="release:nii-audit-v1",
        change_reference="change:chg-2026-0911",
        artifact_reference="artifact:nii-audit-adapter-v1",
        rollback_reference="runbook:nii-audit-rollback-v1",
        steps=(
            NIIRunAuditPhysicalAdapterProductionDeploymentStep(
                sequence=2,
                instruction_reference="runbook:post-deployment-validation",
            ),
            NIIRunAuditPhysicalAdapterProductionDeploymentStep(
                sequence=1,
                instruction_reference="runbook:deploy-authorized-artifact",
            ),
        ),
    )


def _evidence(requirement):
    return NIIRunAuditPhysicalAdapterProductionDeploymentExecutionEvidence(
        requirement=requirement,
        source_reference=f"execution:{requirement.value.lower()}",
    )


def test_complete_last_mile_evidence_authorizes_exact_deployment_plan() -> None:
    plan = _deployment_plan()
    requirements = tuple(
        NIIRunAuditPhysicalAdapterProductionDeploymentExecutionRequirement
    )

    authorization = (
        NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorizationService.authorize(
            deployment_plan=plan,
            execution_authorization_reference="execution-auth-2026-09-11",
            evidence=tuple(_evidence(requirement) for requirement in reversed(requirements)),
        )
    )

    assert authorization.deployment_plan is plan
    assert authorization.execution_authorization_reference == "execution-auth-2026-09-11"
    assert authorization.plan_reference == "deployment-plan-2026-09-11"
    assert authorization.adapter_reference == "adapter-v1"
    assert authorization.environment_reference == "production-cr-primary"
    assert authorization.promotion_authorization_reference == "promotion-auth-2026-09-11"
    assert authorization.artifact_reference == "artifact:nii-audit-adapter-v1"
    assert authorization.rollback_reference == "runbook:nii-audit-rollback-v1"
    assert tuple(item.requirement.value for item in authorization.evidence) == tuple(
        sorted(requirement.value for requirement in requirements)
    )


def test_missing_last_mile_evidence_is_rejected() -> None:
    omitted = (
        NIIRunAuditPhysicalAdapterProductionDeploymentExecutionRequirement.ROLLBACK_READINESS_CONFIRMED
    )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorizationError,
        match="ROLLBACK_READINESS_CONFIRMED",
    ):
        NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorizationService.authorize(
            deployment_plan=_deployment_plan(),
            execution_authorization_reference="execution-auth-2026-09-11",
            evidence=tuple(
                _evidence(requirement)
                for requirement in NIIRunAuditPhysicalAdapterProductionDeploymentExecutionRequirement
                if requirement is not omitted
            ),
        )


def test_duplicate_last_mile_evidence_is_rejected() -> None:
    requirement = (
        NIIRunAuditPhysicalAdapterProductionDeploymentExecutionRequirement.ARTIFACT_IDENTITY_VERIFIED
    )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorizationError,
        match="Duplicate.*ARTIFACT_IDENTITY_VERIFIED",
    ):
        NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorizationService.authorize(
            deployment_plan=_deployment_plan(),
            execution_authorization_reference="execution-auth-2026-09-11",
            evidence=tuple(
                _evidence(item)
                for item in NIIRunAuditPhysicalAdapterProductionDeploymentExecutionRequirement
            )
            + (_evidence(requirement),),
        )


def test_blank_execution_authorization_reference_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorizationError,
        match="authorization_reference",
    ):
        NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorizationService.authorize(
            deployment_plan=_deployment_plan(),
            execution_authorization_reference=" ",
            evidence=tuple(
                _evidence(requirement)
                for requirement in NIIRunAuditPhysicalAdapterProductionDeploymentExecutionRequirement
            ),
        )


def test_blank_evidence_source_reference_is_rejected() -> None:
    with pytest.raises(ValueError, match="source_reference"):
        NIIRunAuditPhysicalAdapterProductionDeploymentExecutionEvidence(
            requirement=NIIRunAuditPhysicalAdapterProductionDeploymentExecutionRequirement.DEPLOYMENT_WINDOW_ACTIVE,
            source_reference=" ",
        )
