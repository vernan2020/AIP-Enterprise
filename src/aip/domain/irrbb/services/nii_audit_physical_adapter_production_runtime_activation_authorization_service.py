from __future__ import annotations

from collections.abc import Iterable

from aip.domain.irrbb.nii_audit_physical_adapter_production_post_execution_acceptance import (
    NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptance,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_runtime_activation_authorization import (
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_REQUIREMENTS,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationAuthorization,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationAuthorizationError,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationEvidence,
)


class NIIRunAuditPhysicalAdapterProductionRuntimeActivationAuthorizationService:
    """Authorize future runtime activation for one exact accepted deployment."""

    @classmethod
    def authorize(
        cls,
        *,
        post_execution_acceptance: NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptance,
        activation_authorization_reference: str,
        evidence: Iterable[NIIRunAuditPhysicalAdapterProductionRuntimeActivationEvidence],
    ) -> NIIRunAuditPhysicalAdapterProductionRuntimeActivationAuthorization:
        if not activation_authorization_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionRuntimeActivationAuthorizationError(
                "NII audit physical adapter production runtime activation "
                "authorization_reference is required"
            )

        evidence_items = tuple(evidence)
        evidence_by_requirement = {}
        for item in evidence_items:
            if item.requirement in evidence_by_requirement:
                raise NIIRunAuditPhysicalAdapterProductionRuntimeActivationAuthorizationError(
                    "Duplicate NII audit physical adapter production runtime activation "
                    "evidence requirement"
                )
            evidence_by_requirement[item.requirement] = item

        missing_requirements = (
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_REQUIREMENTS
            - set(evidence_by_requirement)
        )
        unexpected_requirements = set(evidence_by_requirement) - set(
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_REQUIREMENTS
        )
        if missing_requirements or unexpected_requirements:
            raise NIIRunAuditPhysicalAdapterProductionRuntimeActivationAuthorizationError(
                "NII audit physical adapter production runtime activation evidence "
                "must cover every required authorization"
            )

        canonical_evidence = tuple(
            sorted(
                evidence_items,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        return NIIRunAuditPhysicalAdapterProductionRuntimeActivationAuthorization(
            post_execution_acceptance=post_execution_acceptance,
            activation_authorization_reference=activation_authorization_reference,
            evidence=canonical_evidence,
        )
