from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class IRRBBSourcePerimeter(str, Enum):
    """Canonical RTILB perimeter used by source sufficiency requirements."""

    CREDIT = "CREDIT"
    LIABILITY = "LIABILITY"
    INVESTMENT = "INVESTMENT"
    COMMON = "COMMON"


class IRRBBSourceAvailabilityStatus(str, Enum):
    """Approved source-sufficiency classifications for one canonical requirement."""

    NATIVE_AVAILABLE = "NATIVE_AVAILABLE"
    DERIVABLE_WITH_DOCUMENTED_RULE = "DERIVABLE_WITH_DOCUMENTED_RULE"
    AVAILABLE_FROM_SUPPLEMENTARY_SOURCE = "AVAILABLE_FROM_SUPPLEMENTARY_SOURCE"
    MISSING_BLOCKING_GAP = "MISSING_BLOCKING_GAP"
    MISSING_BLOCKING_EVE = "MISSING_BLOCKING_EVE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_ASSESSED = "NOT_ASSESSED"


class IRRBBSourceCertificationStatus(str, Enum):
    """Aggregate readiness of a candidate source mapping specification."""

    READY = "READY"
    INCOMPLETE = "INCOMPLETE"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class IRRBBSourceRequirement:
    """Versioned requirement expressed only in canonical RTILB terminology."""

    requirement_id: str
    canonical_variable: str
    perimeter: IRRBBSourcePerimeter
    description: str

    def __post_init__(self) -> None:
        if not self.requirement_id.strip():
            raise ValueError("source requirement_id is required")
        if not self.canonical_variable.strip():
            raise ValueError("source canonical_variable is required")
        if not self.description.strip():
            raise ValueError("source requirement description is required")


@dataclass(frozen=True, slots=True)
class IRRBBSourceRequirementProfile:
    """Auditable, effective-dated set of canonical source requirements."""

    code: str
    version: str
    effective_from: date
    source_reference: str
    requirements: tuple[IRRBBSourceRequirement, ...]

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("source requirement profile code is required")
        if not self.version.strip():
            raise ValueError("source requirement profile version is required")
        if not self.source_reference.strip():
            raise ValueError("source requirement profile source_reference is required")
        if not self.requirements:
            raise ValueError("source requirement profile must contain at least one requirement")
        identifiers = tuple(item.requirement_id for item in self.requirements)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("source requirement profile ids must be unique")


@dataclass(frozen=True, slots=True)
class IRRBBSourceRequirementAssessment:
    """Evidence-backed assessment of one canonical requirement for a source candidate."""

    requirement_id: str
    status: IRRBBSourceAvailabilityStatus
    source_reference: str | None = None
    derivation_rule_reference: str | None = None
    supplementary_source_reference: str | None = None
    evidence_reference: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.requirement_id.strip():
            raise ValueError("source assessment requirement_id is required")
        self._validate_optional_text("source_reference", self.source_reference)
        self._validate_optional_text("derivation_rule_reference", self.derivation_rule_reference)
        self._validate_optional_text(
            "supplementary_source_reference",
            self.supplementary_source_reference,
        )
        self._validate_optional_text("evidence_reference", self.evidence_reference)
        self._validate_optional_text("notes", self.notes)

        if self.status is IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE:
            self._require("native source availability", "source_reference", self.source_reference)
            self._require("native source availability", "evidence_reference", self.evidence_reference)
        elif self.status is IRRBBSourceAvailabilityStatus.DERIVABLE_WITH_DOCUMENTED_RULE:
            self._require("derivable source availability", "source_reference", self.source_reference)
            self._require(
                "derivable source availability",
                "derivation_rule_reference",
                self.derivation_rule_reference,
            )
            self._require(
                "derivable source availability",
                "evidence_reference",
                self.evidence_reference,
            )
        elif self.status is IRRBBSourceAvailabilityStatus.AVAILABLE_FROM_SUPPLEMENTARY_SOURCE:
            self._require(
                "supplementary source availability",
                "supplementary_source_reference",
                self.supplementary_source_reference,
            )
            self._require(
                "supplementary source availability",
                "evidence_reference",
                self.evidence_reference,
            )
        elif self.status is IRRBBSourceAvailabilityStatus.NOT_APPLICABLE:
            self._require("not-applicable source assessment", "notes", self.notes)

    @staticmethod
    def _validate_optional_text(field_name: str, value: str | None) -> None:
        if value is not None and not value.strip():
            raise ValueError(f"{field_name} cannot be blank")

    @staticmethod
    def _require(context: str, field_name: str, value: str | None) -> None:
        if value is None:
            raise ValueError(f"{context} requires {field_name}")


@dataclass(frozen=True, slots=True)
class IRRBBSourceCertificationReport:
    """Deterministic source-sufficiency result with no physical adapter assumptions."""

    profile: IRRBBSourceRequirementProfile
    assessments: tuple[IRRBBSourceRequirementAssessment, ...]
    status: IRRBBSourceCertificationStatus
    blocking_requirement_ids: tuple[str, ...]
    not_assessed_requirement_ids: tuple[str, ...]

    @property
    def is_ready(self) -> bool:
        return self.status is IRRBBSourceCertificationStatus.READY


class IRRBBSourceCertificationService:
    """Certify source sufficiency against a versioned canonical requirement profile."""

    _BLOCKING_STATUSES = {
        IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_GAP,
        IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE,
    }

    @classmethod
    def certify(
        cls,
        *,
        profile: IRRBBSourceRequirementProfile,
        assessments: tuple[IRRBBSourceRequirementAssessment, ...],
    ) -> IRRBBSourceCertificationReport:
        supplied = {item.requirement_id: item for item in assessments}
        if len(supplied) != len(assessments):
            raise ValueError("source assessments must contain unique requirement_id values")

        known_ids = {item.requirement_id for item in profile.requirements}
        unknown = sorted(set(supplied) - known_ids)
        if unknown:
            raise ValueError(
                "source assessments contain unknown requirement ids: " + ", ".join(unknown)
            )

        normalized = tuple(
            supplied.get(
                requirement.requirement_id,
                IRRBBSourceRequirementAssessment(
                    requirement_id=requirement.requirement_id,
                    status=IRRBBSourceAvailabilityStatus.NOT_ASSESSED,
                ),
            )
            for requirement in profile.requirements
        )
        blocking_ids = tuple(
            item.requirement_id for item in normalized if item.status in cls._BLOCKING_STATUSES
        )
        not_assessed_ids = tuple(
            item.requirement_id
            for item in normalized
            if item.status is IRRBBSourceAvailabilityStatus.NOT_ASSESSED
        )

        status = IRRBBSourceCertificationStatus.READY
        if blocking_ids:
            status = IRRBBSourceCertificationStatus.BLOCKED
        elif not_assessed_ids:
            status = IRRBBSourceCertificationStatus.INCOMPLETE

        return IRRBBSourceCertificationReport(
            profile=profile,
            assessments=normalized,
            status=status,
            blocking_requirement_ids=blocking_ids,
            not_assessed_requirement_ids=not_assessed_ids,
        )
