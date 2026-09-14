from __future__ import annotations

from datetime import date

import pytest

from aip.application.irrbb import (
    IRRBBSourceAvailabilityStatus,
    IRRBBSourceCertificationService,
    IRRBBSourceCertificationStatus,
    IRRBBSourcePerimeter,
    IRRBBSourceRequirement,
    IRRBBSourceRequirementAssessment,
    IRRBBSourceRequirementProfile,
)


def _requirement(
    requirement_id: str,
    canonical_variable: str,
    perimeter: IRRBBSourcePerimeter = IRRBBSourcePerimeter.COMMON,
) -> IRRBBSourceRequirement:
    return IRRBBSourceRequirement(
        requirement_id=requirement_id,
        canonical_variable=canonical_variable,
        perimeter=perimeter,
        description=f"Requirement for {canonical_variable}",
    )


def _profile() -> IRRBBSourceRequirementProfile:
    return IRRBBSourceRequirementProfile(
        code="RTILB-SOURCE-REQ",
        version="2026.1",
        effective_from=date(2026, 1, 1),
        source_reference="DOC:IRRBB-SOURCE-MATRIX",
        requirements=(
            _requirement("REQ-CURRENCY", "currency"),
            _requirement("REQ-PRINCIPAL", "principal", IRRBBSourcePerimeter.CREDIT),
            _requirement("REQ-OPTIONALITY", "optionality", IRRBBSourcePerimeter.CREDIT),
        ),
    )


def test_requirement_profile_rejects_empty_requirement_set() -> None:
    with pytest.raises(ValueError, match="at least one requirement"):
        IRRBBSourceRequirementProfile(
            code="RTILB-SOURCE-REQ",
            version="2026.1",
            effective_from=date(2026, 1, 1),
            source_reference="DOC:IRRBB-SOURCE-MATRIX",
            requirements=(),
        )


def test_requirement_profile_rejects_duplicate_requirement_ids() -> None:
    duplicated = _requirement("REQ-CURRENCY", "currency")
    with pytest.raises(ValueError, match="profile ids must be unique"):
        IRRBBSourceRequirementProfile(
            code="RTILB-SOURCE-REQ",
            version="2026.1",
            effective_from=date(2026, 1, 1),
            source_reference="DOC:IRRBB-SOURCE-MATRIX",
            requirements=(duplicated, duplicated),
        )


def test_native_availability_requires_source_reference() -> None:
    with pytest.raises(
        ValueError,
        match="native source availability requires source_reference",
    ):
        IRRBBSourceRequirementAssessment(
            requirement_id="REQ-CURRENCY",
            status=IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE,
            evidence_reference="TEST:SOURCE-SCHEMA:CURRENCY",
        )


def test_native_availability_requires_evidence_reference() -> None:
    with pytest.raises(
        ValueError,
        match="native source availability requires evidence_reference",
    ):
        IRRBBSourceRequirementAssessment(
            requirement_id="REQ-CURRENCY",
            status=IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE,
            source_reference="SOURCE:CANDIDATE:CURRENCY",
        )


def test_derivable_availability_requires_documented_rule_and_evidence() -> None:
    with pytest.raises(
        ValueError,
        match="derivable source availability requires derivation_rule_reference",
    ):
        IRRBBSourceRequirementAssessment(
            requirement_id="REQ-PRINCIPAL",
            status=IRRBBSourceAvailabilityStatus.DERIVABLE_WITH_DOCUMENTED_RULE,
            source_reference="SOURCE:CANDIDATE:CONTRACT",
            evidence_reference="TEST:DERIVATION:PRINCIPAL",
        )

    with pytest.raises(
        ValueError,
        match="derivable source availability requires evidence_reference",
    ):
        IRRBBSourceRequirementAssessment(
            requirement_id="REQ-PRINCIPAL",
            status=IRRBBSourceAvailabilityStatus.DERIVABLE_WITH_DOCUMENTED_RULE,
            source_reference="SOURCE:CANDIDATE:CONTRACT",
            derivation_rule_reference="RULE:PRINCIPAL:2026.1",
        )


def test_supplementary_availability_requires_source_and_evidence() -> None:
    with pytest.raises(
        ValueError,
        match="supplementary source availability requires supplementary_source_reference",
    ):
        IRRBBSourceRequirementAssessment(
            requirement_id="REQ-CURRENCY",
            status=IRRBBSourceAvailabilityStatus.AVAILABLE_FROM_SUPPLEMENTARY_SOURCE,
            evidence_reference="TEST:SUPPLEMENTARY:CURRENCY",
        )

    with pytest.raises(
        ValueError,
        match="supplementary source availability requires evidence_reference",
    ):
        IRRBBSourceRequirementAssessment(
            requirement_id="REQ-CURRENCY",
            status=IRRBBSourceAvailabilityStatus.AVAILABLE_FROM_SUPPLEMENTARY_SOURCE,
            supplementary_source_reference="SOURCE:SUPPLEMENTARY:CURRENCY",
        )


def test_not_applicable_requires_explicit_rationale() -> None:
    with pytest.raises(
        ValueError,
        match="not-applicable source assessment requires notes",
    ):
        IRRBBSourceRequirementAssessment(
            requirement_id="REQ-OPTIONALITY",
            status=IRRBBSourceAvailabilityStatus.NOT_APPLICABLE,
        )


def test_missing_assessment_is_normalized_to_not_assessed_and_incomplete() -> None:
    profile = _profile()
    report = IRRBBSourceCertificationService.certify(
        profile=profile,
        assessments=(
            IRRBBSourceRequirementAssessment(
                requirement_id="REQ-CURRENCY",
                status=IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE,
                source_reference="SOURCE:CANDIDATE:CURRENCY",
                evidence_reference="TEST:SOURCE-SCHEMA:CURRENCY",
            ),
        ),
    )

    assert report.status is IRRBBSourceCertificationStatus.INCOMPLETE
    assert report.is_ready is False
    assert report.blocking_requirement_ids == ()
    assert report.not_assessed_requirement_ids == (
        "REQ-PRINCIPAL",
        "REQ-OPTIONALITY",
    )
    assert tuple(item.requirement_id for item in report.assessments) == tuple(
        item.requirement_id for item in profile.requirements
    )


def test_blocking_gap_takes_precedence_over_not_assessed() -> None:
    report = IRRBBSourceCertificationService.certify(
        profile=_profile(),
        assessments=(
            IRRBBSourceRequirementAssessment(
                requirement_id="REQ-CURRENCY",
                status=IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_GAP,
                notes="Required repricing GAP input is absent.",
            ),
        ),
    )

    assert report.status is IRRBBSourceCertificationStatus.BLOCKED
    assert report.blocking_requirement_ids == ("REQ-CURRENCY",)
    assert report.not_assessed_requirement_ids == (
        "REQ-PRINCIPAL",
        "REQ-OPTIONALITY",
    )


def test_all_requirements_with_traceable_assessments_are_ready() -> None:
    report = IRRBBSourceCertificationService.certify(
        profile=_profile(),
        assessments=(
            IRRBBSourceRequirementAssessment(
                requirement_id="REQ-CURRENCY",
                status=IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE,
                source_reference="SOURCE:CANDIDATE:CURRENCY",
                evidence_reference="TEST:SOURCE-SCHEMA:CURRENCY",
            ),
            IRRBBSourceRequirementAssessment(
                requirement_id="REQ-PRINCIPAL",
                status=IRRBBSourceAvailabilityStatus.DERIVABLE_WITH_DOCUMENTED_RULE,
                source_reference="SOURCE:CANDIDATE:CONTRACT",
                derivation_rule_reference="RULE:PRINCIPAL:2026.1",
                evidence_reference="TEST:DERIVATION:PRINCIPAL",
            ),
            IRRBBSourceRequirementAssessment(
                requirement_id="REQ-OPTIONALITY",
                status=IRRBBSourceAvailabilityStatus.NOT_APPLICABLE,
                notes="Candidate perimeter contains no optional credit products.",
            ),
        ),
    )

    assert report.status is IRRBBSourceCertificationStatus.READY
    assert report.is_ready is True
    assert report.blocking_requirement_ids == ()
    assert report.not_assessed_requirement_ids == ()


def test_certification_rejects_duplicate_and_unknown_requirement_ids() -> None:
    profile = _profile()
    assessment = IRRBBSourceRequirementAssessment(
        requirement_id="REQ-CURRENCY",
        status=IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE,
        source_reference="SOURCE:CANDIDATE:CURRENCY",
        evidence_reference="TEST:SOURCE-SCHEMA:CURRENCY",
    )

    with pytest.raises(ValueError, match="unique requirement_id"):
        IRRBBSourceCertificationService.certify(
            profile=profile,
            assessments=(assessment, assessment),
        )

    with pytest.raises(ValueError, match="unknown requirement ids: REQ-UNKNOWN"):
        IRRBBSourceCertificationService.certify(
            profile=profile,
            assessments=(
                IRRBBSourceRequirementAssessment(
                    requirement_id="REQ-UNKNOWN",
                    status=IRRBBSourceAvailabilityStatus.NOT_ASSESSED,
                ),
            ),
        )
