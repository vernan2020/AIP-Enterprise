from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.domain.irrbb.nii_audit_physical_adapter_production_deployment_plan import (
    NIIRunAuditPhysicalAdapterProductionDeploymentPlan,
)


class NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorizationError(ValueError):
    """Raised when deployment execution authorization cannot be issued safely."""


class NIIRunAuditPhysicalAdapterProductionDeploymentExecutionRequirement(str, Enum):
    """Last-mile evidence required before an approved plan may be executed."""

    ARTIFACT_IDENTITY_VERIFIED = "ARTIFACT_IDENTITY_VERIFIED"
    DEPLOYMENT_WINDOW_ACTIVE = "DEPLOYMENT_WINDOW_ACTIVE"
    EXECUTION_AUTHORITY_CONFIRMED = "EXECUTION_AUTHORITY_CONFIRMED"
    ROLLBACK_READINESS_CONFIRMED = "ROLLBACK_READINESS_CONFIRMED"
    PRE_DEPLOYMENT_CHECKPOINT_CONFIRMED = "PRE_DEPLOYMENT_CHECKPOINT_CONFIRMED"


REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_DEPLOYMENT_EXECUTION_REQUIREMENTS = frozenset(
    NIIRunAuditPhysicalAdapterProductionDeploymentExecutionRequirement
)


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionDeploymentExecutionEvidence:
    """Traceable evidence for one deployment-execution authorization requirement."""

    requirement: NIIRunAuditPhysicalAdapterProductionDeploymentExecutionRequirement
    source_reference: str

    def __post_init__(self) -> None:
        if not self.source_reference.strip():
            raise ValueError(
                "NII audit physical adapter production deployment execution evidence source_reference is required"
            )


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorization:
    """Positive-only authorization to execute one exact immutable deployment plan."""

    deployment_plan: NIIRunAuditPhysicalAdapterProductionDeploymentPlan
    execution_authorization_reference: str
    evidence: tuple[NIIRunAuditPhysicalAdapterProductionDeploymentExecutionEvidence, ...]

    def __post_init__(self) -> None:
        if not self.execution_authorization_reference.strip():
            raise ValueError(
                "NII audit physical adapter production deployment execution authorization_reference is required"
            )

        evidence_requirements = tuple(item.requirement for item in self.evidence)
        if len(evidence_requirements) != len(set(evidence_requirements)):
            raise ValueError(
                "Duplicate NII audit physical adapter production deployment execution evidence requirement"
            )
        if (
            frozenset(evidence_requirements)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_DEPLOYMENT_EXECUTION_REQUIREMENTS
        ):
            raise ValueError(
                "NII audit physical adapter production deployment execution evidence must cover every required authorization"
            )

        canonical_evidence = tuple(
            sorted(
                self.evidence,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        if self.evidence != canonical_evidence:
            raise ValueError(
                "NII audit physical adapter production deployment execution evidence must be canonicalized"
            )

    @property
    def plan_reference(self) -> str:
        return self.deployment_plan.plan_reference

    @property
    def adapter_reference(self) -> str:
        return self.deployment_plan.adapter_reference

    @property
    def environment_reference(self) -> str:
        return self.deployment_plan.environment_reference

    @property
    def promotion_authorization_reference(self) -> str:
        return self.deployment_plan.authorization_reference

    @property
    def artifact_reference(self) -> str:
        return self.deployment_plan.artifact_reference

    @property
    def rollback_reference(self) -> str:
        return self.deployment_plan.rollback_reference
