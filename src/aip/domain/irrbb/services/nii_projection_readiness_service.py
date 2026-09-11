from __future__ import annotations

from aip.domain.irrbb.models import (
    BankingBookPosition,
    IRRBBInstrumentClass,
    PaymentStructure,
)
from aip.domain.irrbb.nii_readiness import (
    NIIProjectionCapabilityEvidence,
    NIIProjectionEvidenceKey,
    NIIProjectionReadinessAssessment,
    NIIProjectionReadinessFinding,
    NIIProjectionReadinessStatus,
    NIIProjectionRequirementProfile,
    NIIProjectionScopeStatus,
    POSITION_EVIDENCE_KEYS,
)


class NIIProjectionReadinessService:
    """Certify strategy evidence without inventing NII projection assumptions."""

    @classmethod
    def assess(
        cls,
        *,
        position: BankingBookPosition,
        profile: NIIProjectionRequirementProfile,
        capabilities: tuple[NIIProjectionCapabilityEvidence, ...] = (),
    ) -> NIIProjectionReadinessAssessment:
        if profile.scope_status is NIIProjectionScopeStatus.EXCLUDED:
            return NIIProjectionReadinessAssessment(
                position_id=position.position_id,
                strategy_reference=profile.strategy_reference,
                profile_source_reference=profile.source_reference,
                status=NIIProjectionReadinessStatus.EXCLUDED,
                findings=(),
                exclusion_reason=profile.exclusion_reason,
            )

        available = cls._available_position_evidence(position)
        capability_keys: set[NIIProjectionEvidenceKey] = set()
        for evidence in capabilities:
            if evidence.key in capability_keys:
                raise ValueError(f"duplicate NII projection capability evidence: {evidence.key.value}")
            capability_keys.add(evidence.key)
        available.update(capability_keys)

        findings: list[NIIProjectionReadinessFinding] = []
        for requirement in profile.requirements:
            if any(alternative.keys <= available for alternative in requirement.alternatives):
                continue

            missing_alternatives = tuple(
                tuple(sorted(alternative.keys - available, key=lambda key: key.value))
                for alternative in requirement.alternatives
            )
            findings.append(
                NIIProjectionReadinessFinding(
                    requirement_id=requirement.requirement_id,
                    message=requirement.message,
                    missing_alternatives=missing_alternatives,
                )
            )

        return NIIProjectionReadinessAssessment(
            position_id=position.position_id,
            strategy_reference=profile.strategy_reference,
            profile_source_reference=profile.source_reference,
            status=(
                NIIProjectionReadinessStatus.BLOCKED
                if findings
                else NIIProjectionReadinessStatus.READY
            ),
            findings=tuple(findings),
        )

    @staticmethod
    def _available_position_evidence(
        position: BankingBookPosition,
    ) -> set[NIIProjectionEvidenceKey]:
        available: set[NIIProjectionEvidenceKey] = set()

        value_presence = {
            NIIProjectionEvidenceKey.MATURITY_DATE: position.maturity_date is not None,
            NIIProjectionEvidenceKey.CONTRACTUAL_RATE: position.contractual_rate is not None,
            NIIProjectionEvidenceKey.REFERENCE_RATE: bool(
                position.reference_rate and position.reference_rate.strip()
            ),
            NIIProjectionEvidenceKey.SPREAD: position.spread is not None,
            NIIProjectionEvidenceKey.NEXT_REPRICING_DATE: position.next_repricing_date is not None,
            NIIProjectionEvidenceKey.REPRICING_FREQUENCY_MONTHS: (
                position.repricing_frequency_months is not None
            ),
            NIIProjectionEvidenceKey.PAYMENT_FREQUENCY_MONTHS: (
                position.payment_frequency_months is not None
            ),
            NIIProjectionEvidenceKey.LAST_INTEREST_PAYMENT_DATE: (
                position.last_interest_payment_date is not None
            ),
            NIIProjectionEvidenceKey.NEXT_PAYMENT_DATE: position.next_payment_date is not None,
            NIIProjectionEvidenceKey.RATE_FLOOR: position.rate_floor is not None,
            NIIProjectionEvidenceKey.RATE_CAP: position.rate_cap is not None,
            NIIProjectionEvidenceKey.PAYMENT_STRUCTURE_CLASSIFIED: (
                position.payment_structure is not PaymentStructure.OTHER
            ),
            NIIProjectionEvidenceKey.INSTRUMENT_CLASS_CLASSIFIED: (
                position.instrument_class is not IRRBBInstrumentClass.OTHER
            ),
        }
        available.update(key for key, present in value_presence.items() if present)

        if not available <= POSITION_EVIDENCE_KEYS:
            raise RuntimeError("NII readiness position evidence classification is inconsistent")
        return available
