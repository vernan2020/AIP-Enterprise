from __future__ import annotations

from datetime import date

import pytest

from aip.application.irrbb import (
    IRRBBSourceAvailabilityStatus,
    IRRBBSourceCertificationService,
    IRRBBSourceExclusion,
    IRRBBSourcePerimeter,
    IRRBBSourceRequirement,
    IRRBBSourceRequirementAssessment,
    IRRBBSourceRequirementProfile,
)
from aip.product.configured.irrbb.source_acl import (
    IRRBBSourceRecordEnvelope,
    IRRBBSourceSnapshotAssembler,
)

CUTOFF = date(2026, 8, 31)


def _ready_certification():
    profile = IRRBBSourceRequirementProfile(
        code="TEST-SOURCE",
        version="1",
        effective_from=CUTOFF,
        source_reference="TEST:PROFILE",
        requirements=(
            IRRBBSourceRequirement(
                requirement_id="TEST-1",
                canonical_variable="test",
                perimeter=IRRBBSourcePerimeter.CREDIT,
                description="Test requirement.",
            ),
        ),
    )
    return IRRBBSourceCertificationService.certify(
        profile=profile,
        assessments=(
            IRRBBSourceRequirementAssessment(
                requirement_id="TEST-1",
                status=IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE,
                source_reference="TEST:SOURCE",
                evidence_reference="TEST:EVIDENCE",
            ),
        ),
    )


class _ExclusionMapper:
    def map_record(self, record: IRRBBSourceRecordEnvelope[dict[str, str]]):
        return IRRBBSourceExclusion(
            source_record_id=record.source_record_id,
            source_reference=record.source_reference,
            reason_code="TEST_EXCLUDED",
            message="Explicit test exclusion.",
            rule_reference="TEST:RULE",
        )


class _BadLineageExclusionMapper:
    def map_record(self, record: IRRBBSourceRecordEnvelope[dict[str, str]]):
        return IRRBBSourceExclusion(
            source_record_id="OTHER",
            source_reference=record.source_reference,
            reason_code="TEST_EXCLUDED",
            message="Explicit test exclusion.",
            rule_reference="TEST:RULE",
        )


def test_snapshot_assembler_preserves_explicit_source_exclusion() -> None:
    source = IRRBBSourceRecordEnvelope(
        source_record_id="ROW-1",
        source_reference="XML:CREDIT:ROW-1",
        payload={"account": "133"},
    )

    snapshot = IRRBBSourceSnapshotAssembler(_ExclusionMapper()).assemble(
        cutoff_date=CUTOFF,
        source_records=(source,),
        source_certification=_ready_certification(),
    )

    assert snapshot.position_records == ()
    assert snapshot.mapping_failures == ()
    assert len(snapshot.source_exclusions) == 1
    assert snapshot.source_exclusions[0].source_record_id == "ROW-1"
    assert snapshot.source_exclusions[0].reason_code == "TEST_EXCLUDED"


def test_snapshot_assembler_rejects_exclusion_lineage_substitution() -> None:
    source = IRRBBSourceRecordEnvelope(
        source_record_id="ROW-1",
        source_reference="XML:CREDIT:ROW-1",
        payload={},
    )

    with pytest.raises(ValueError, match="mapper changed source_record_id"):
        IRRBBSourceSnapshotAssembler(_BadLineageExclusionMapper()).assemble(
            cutoff_date=CUTOFF,
            source_records=(source,),
            source_certification=_ready_certification(),
        )
