from __future__ import annotations

from collections.abc import Iterable

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_continuity_epoch import (
    NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpoch,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_status_attestation import (
    NIIRunAuditPhysicalAdapterProductionOperationalStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_status_reattestation import (
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_STATUS_REATTESTATION_REQUIREMENTS,
    NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestation,
    NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationError,
    NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationEvidence,
)


class NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationService:
    """Attest operational status for one exact post-recovery continuity epoch."""

    @classmethod
    def attest(
        cls,
        *,
        continuity_epoch: NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpoch,
        reattestation_reference: str,
        status: NIIRunAuditPhysicalAdapterProductionOperationalStatus,
        evidence: Iterable[
            NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationEvidence
        ],
        exception_references: Iterable[str] = (),
    ) -> NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestation:
        if not continuity_epoch.epoch_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationError(
                "NII audit operational status re-attestation requires a valid continuity epoch"
            )
        if continuity_epoch.epoch_reference == continuity_epoch.previous_operations_reference:
            raise NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationError(
                "NII audit operational status re-attestation requires a distinct continuity epoch"
            )
        if not reattestation_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationError(
                "NII audit operational status reattestation_reference is required"
            )

        evidence_items = tuple(evidence)
        evidence_by_requirement = {}
        for item in evidence_items:
            if item.requirement in evidence_by_requirement:
                raise NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationError(
                    "Duplicate NII audit operational status re-attestation evidence requirement"
                )
            evidence_by_requirement[item.requirement] = item

        if (
            frozenset(evidence_by_requirement)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_STATUS_REATTESTATION_REQUIREMENTS
        ):
            raise NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationError(
                "NII audit operational status re-attestation evidence must cover every required "
                "status control"
            )

        canonical_evidence = tuple(
            sorted(
                evidence_items,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        canonical_exceptions = tuple(sorted(exception_references))
        return NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestation(
            continuity_epoch=continuity_epoch,
            reattestation_reference=reattestation_reference,
            status=status,
            evidence=canonical_evidence,
            exception_references=canonical_exceptions,
        )
