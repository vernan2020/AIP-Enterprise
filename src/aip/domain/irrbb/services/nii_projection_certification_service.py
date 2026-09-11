from __future__ import annotations

from aip.domain.irrbb.models import BankingBookPosition, IRRBBScenario
from aip.domain.irrbb.nii import NIIProjectionBasis
from aip.domain.irrbb.nii_certification import (
    NIIProjectionCertificationResult,
    NIIProjectionCertificationStatus,
)
from aip.domain.irrbb.nii_readiness import NIIProjectionReadinessStatus
from aip.domain.irrbb.ports import (
    NIIProjectionCapabilityEvidenceProvider,
    NIIProjectionRequirementProfileProvider,
    NIIProjectionStrategyResolver,
)
from aip.domain.irrbb.services.nii_projection_readiness_service import (
    NIIProjectionReadinessService,
)
from aip.domain.irrbb.services.nii_projection_service import NIIProjectionService


class NIIProjectionCertificationService:
    """Certify all positions before allowing any NII projection strategy to run."""

    @classmethod
    def project_certified(
        cls,
        *,
        positions: tuple[BankingBookPosition, ...],
        basis: NIIProjectionBasis,
        scenario: IRRBBScenario,
        profile_provider: NIIProjectionRequirementProfileProvider,
        capability_provider: NIIProjectionCapabilityEvidenceProvider,
        strategy_resolver: NIIProjectionStrategyResolver,
    ) -> NIIProjectionCertificationResult:
        if not positions:
            raise ValueError("NII projection certification requires at least one position")

        position_ids = tuple(position.position_id for position in positions)
        if len(set(position_ids)) != len(position_ids):
            raise ValueError("duplicate NII projection certification position_id")

        assessments = []
        ready_positions = []
        for position in positions:
            profile = profile_provider.profile_for(position=position)
            capabilities = ()
            if profile.scope_status.value == "INCLUDED":
                capabilities = capability_provider.evidence_for(
                    position=position,
                    profile=profile,
                    basis=basis,
                    scenario=scenario,
                )

            assessment = NIIProjectionReadinessService.assess(
                position=position,
                profile=profile,
                capabilities=capabilities,
            )
            assessments.append(assessment)
            if assessment.status is NIIProjectionReadinessStatus.READY:
                ready_positions.append(position)

        assessment_tuple = tuple(assessments)
        if any(
            item.status is NIIProjectionReadinessStatus.BLOCKED
            for item in assessment_tuple
        ):
            return NIIProjectionCertificationResult(
                basis=basis,
                scenario=scenario,
                status=NIIProjectionCertificationStatus.BLOCKED,
                assessments=assessment_tuple,
            )

        if not ready_positions:
            return NIIProjectionCertificationResult(
                basis=basis,
                scenario=scenario,
                status=NIIProjectionCertificationStatus.NO_INCLUDED_POSITIONS,
                assessments=assessment_tuple,
            )

        projection_batch = NIIProjectionService.project(
            positions=tuple(ready_positions),
            basis=basis,
            scenario=scenario,
            resolver=strategy_resolver,
        )
        return NIIProjectionCertificationResult(
            basis=basis,
            scenario=scenario,
            status=NIIProjectionCertificationStatus.PROJECTED,
            assessments=assessment_tuple,
            projection_batch=projection_batch,
        )
