from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class NIIProjectionEvidenceKey(str, Enum):
    """Canonical evidence keys that an approved NII strategy may require."""

    MATURITY_DATE = "MATURITY_DATE"
    CONTRACTUAL_RATE = "CONTRACTUAL_RATE"
    REFERENCE_RATE = "REFERENCE_RATE"
    SPREAD = "SPREAD"
    NEXT_REPRICING_DATE = "NEXT_REPRICING_DATE"
    REPRICING_FREQUENCY_MONTHS = "REPRICING_FREQUENCY_MONTHS"
    PAYMENT_FREQUENCY_MONTHS = "PAYMENT_FREQUENCY_MONTHS"
    LAST_INTEREST_PAYMENT_DATE = "LAST_INTEREST_PAYMENT_DATE"
    NEXT_PAYMENT_DATE = "NEXT_PAYMENT_DATE"
    RATE_FLOOR = "RATE_FLOOR"
    RATE_CAP = "RATE_CAP"
    PAYMENT_STRUCTURE_CLASSIFIED = "PAYMENT_STRUCTURE_CLASSIFIED"
    INSTRUMENT_CLASS_CLASSIFIED = "INSTRUMENT_CLASS_CLASSIFIED"

    EXPLICIT_CONTRACTUAL_SCHEDULE = "EXPLICIT_CONTRACTUAL_SCHEDULE"
    FORWARD_REFERENCE_RATE_CURVE = "FORWARD_REFERENCE_RATE_CURVE"
    BEHAVIORAL_EARNINGS_MODEL = "BEHAVIORAL_EARNINGS_MODEL"
    OPTIONALITY_EARNINGS_MODEL = "OPTIONALITY_EARNINGS_MODEL"
    CONSTANT_BALANCE_REPLACEMENT_POLICY = "CONSTANT_BALANCE_REPLACEMENT_POLICY"
    DYNAMIC_BALANCE_SHEET_POLICY = "DYNAMIC_BALANCE_SHEET_POLICY"
    DAY_COUNT_CONVENTION = "DAY_COUNT_CONVENTION"
    BUSINESS_DAY_CONVENTION = "BUSINESS_DAY_CONVENTION"


POSITION_EVIDENCE_KEYS = frozenset(
    {
        NIIProjectionEvidenceKey.MATURITY_DATE,
        NIIProjectionEvidenceKey.CONTRACTUAL_RATE,
        NIIProjectionEvidenceKey.REFERENCE_RATE,
        NIIProjectionEvidenceKey.SPREAD,
        NIIProjectionEvidenceKey.NEXT_REPRICING_DATE,
        NIIProjectionEvidenceKey.REPRICING_FREQUENCY_MONTHS,
        NIIProjectionEvidenceKey.PAYMENT_FREQUENCY_MONTHS,
        NIIProjectionEvidenceKey.LAST_INTEREST_PAYMENT_DATE,
        NIIProjectionEvidenceKey.NEXT_PAYMENT_DATE,
        NIIProjectionEvidenceKey.RATE_FLOOR,
        NIIProjectionEvidenceKey.RATE_CAP,
        NIIProjectionEvidenceKey.PAYMENT_STRUCTURE_CLASSIFIED,
        NIIProjectionEvidenceKey.INSTRUMENT_CLASS_CLASSIFIED,
    }
)


class NIIProjectionScopeStatus(str, Enum):
    """Whether an approved strategy profile includes the position in NII scope."""

    INCLUDED = "INCLUDED"
    EXCLUDED = "EXCLUDED"


class NIIProjectionReadinessStatus(str, Enum):
    """Certification result for one position under one strategy requirement profile."""

    READY = "READY"
    BLOCKED = "BLOCKED"
    EXCLUDED = "EXCLUDED"


@dataclass(frozen=True, slots=True)
class NIIProjectionEvidenceAlternative:
    """One all-of evidence set that can satisfy a strategy requirement."""

    keys: frozenset[NIIProjectionEvidenceKey]

    def __post_init__(self) -> None:
        if not self.keys:
            raise ValueError("NII projection evidence alternative cannot be empty")


@dataclass(frozen=True, slots=True)
class NIIProjectionRequirement:
    """One named requirement satisfied when any declared alternative is complete."""

    requirement_id: str
    alternatives: tuple[NIIProjectionEvidenceAlternative, ...]
    message: str

    def __post_init__(self) -> None:
        if not self.requirement_id.strip():
            raise ValueError("NII projection requirement_id is required")
        if not self.alternatives:
            raise ValueError("NII projection requirement requires at least one alternative")
        if len(set(self.alternatives)) != len(self.alternatives):
            raise ValueError("duplicate NII projection evidence alternatives are not allowed")
        if not self.message.strip():
            raise ValueError("NII projection requirement message is required")


@dataclass(frozen=True, slots=True)
class NIIProjectionRequirementProfile:
    """Versioned, strategy-owned declaration of evidence required before projection."""

    strategy_reference: str
    source_reference: str
    scope_status: NIIProjectionScopeStatus
    requirements: tuple[NIIProjectionRequirement, ...] = ()
    exclusion_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.strategy_reference.strip():
            raise ValueError("NII projection profile strategy_reference is required")
        if not self.source_reference.strip():
            raise ValueError("NII projection profile source_reference is required")

        ids = tuple(item.requirement_id for item in self.requirements)
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate NII projection requirement_id is not allowed")

        if self.scope_status is NIIProjectionScopeStatus.EXCLUDED:
            if self.requirements:
                raise ValueError("excluded NII projection profile cannot declare requirements")
            if self.exclusion_reason is None or not self.exclusion_reason.strip():
                raise ValueError("excluded NII projection profile requires exclusion_reason")
        elif self.exclusion_reason is not None:
            raise ValueError("included NII projection profile cannot declare exclusion_reason")


@dataclass(frozen=True, slots=True)
class NIIProjectionCapabilityEvidence:
    """Approved non-position evidence available to an NII projection strategy."""

    key: NIIProjectionEvidenceKey
    source_reference: str

    def __post_init__(self) -> None:
        if self.key in POSITION_EVIDENCE_KEYS:
            raise ValueError("position evidence cannot be supplied as external NII capability")
        if not self.source_reference.strip():
            raise ValueError("NII projection capability source_reference is required")


@dataclass(frozen=True, slots=True)
class NIIProjectionReadinessFinding:
    """One unsatisfied strategy requirement with every permitted alternative exposed."""

    requirement_id: str
    message: str
    missing_alternatives: tuple[tuple[NIIProjectionEvidenceKey, ...], ...]

    def __post_init__(self) -> None:
        if not self.requirement_id.strip():
            raise ValueError("NII readiness finding requirement_id is required")
        if not self.message.strip():
            raise ValueError("NII readiness finding message is required")
        if not self.missing_alternatives:
            raise ValueError("NII readiness finding requires missing alternatives")
        if any(not alternative for alternative in self.missing_alternatives):
            raise ValueError("NII readiness missing alternative cannot be empty")


@dataclass(frozen=True, slots=True)
class NIIProjectionReadinessAssessment:
    """Auditable readiness decision for one position and one strategy profile."""

    position_id: str
    strategy_reference: str
    profile_source_reference: str
    status: NIIProjectionReadinessStatus
    findings: tuple[NIIProjectionReadinessFinding, ...]
    exclusion_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.position_id.strip():
            raise ValueError("NII readiness position_id is required")
        if not self.strategy_reference.strip():
            raise ValueError("NII readiness strategy_reference is required")
        if not self.profile_source_reference.strip():
            raise ValueError("NII readiness profile_source_reference is required")

        if self.status is NIIProjectionReadinessStatus.READY and self.findings:
            raise ValueError("READY NII readiness assessment cannot contain findings")
        if self.status is NIIProjectionReadinessStatus.BLOCKED and not self.findings:
            raise ValueError("BLOCKED NII readiness assessment requires findings")
        if self.status is NIIProjectionReadinessStatus.EXCLUDED:
            if self.findings:
                raise ValueError("EXCLUDED NII readiness assessment cannot contain findings")
            if self.exclusion_reason is None or not self.exclusion_reason.strip():
                raise ValueError("EXCLUDED NII readiness assessment requires exclusion_reason")
        elif self.exclusion_reason is not None:
            raise ValueError("non-excluded NII readiness assessment cannot have exclusion_reason")

    @property
    def is_ready(self) -> bool:
        return self.status is NIIProjectionReadinessStatus.READY
