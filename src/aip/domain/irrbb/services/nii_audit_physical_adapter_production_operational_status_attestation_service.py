from __future__ import annotations

from collections.abc import Iterable

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_status_attestation import (
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_STATUS_REQUIREMENTS,
    NIIRunAuditPhysicalAdapterProductionOperationalStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestation,
    NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestationError,
    NIIRunAuditPhysicalAdapterProductionOperationalStatusEvidence,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_steady_state_operations import (
    NIIRunAuditPhysicalAdapterProductionSteadyStateOperations,
)


class NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestationService:
    """Create one immutable status attestation for an exact steady-state operations record."""

    @classmethod
    def attest(
        cls,
        *,
        steady_state_operations: NIIRunAuditPhysicalAdapterProductionSteadyStateOperations,
        attestation_reference: str,
        status: NIIRunAuditPhysicalAdapterProductionOperationalStatus,
        evidence: Iterable[NIIRunAuditPhysicalAdapterProductionOperationalStatusEvidence],
        exception_references: Iterable[str] = (),
    ) -> NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestation:
        if not attestation_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestationError(
                "NII audit physical adapter production operational status "
                "attestation_reference is required"
            )

        evidence_items = tuple(evidence)
        evidence_by_requirement = {}
        for item in evidence_items:
            if item.requirement in evidence_by_requirement:
                raise NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestationError(
                    "Duplicate NII audit physical adapter production operational status "
                    "evidence requirement"
                )
            evidence_by_requirement[item.requirement] = item

        if (
            frozenset(evidence_by_requirement)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_STATUS_REQUIREMENTS
        ):
            raise NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestationError(
                "NII audit physical adapter production operational status evidence "
                "must cover every required status control"
            )

        canonical_evidence = tuple(
            sorted(
                evidence_items,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        canonical_exceptions = tuple(sorted(exception_references))
        return NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestation(
            steady_state_operations=steady_state_operations,
            attestation_reference=attestation_reference,
            status=status,
            evidence=canonical_evidence,
            exception_references=canonical_exceptions,
        )
