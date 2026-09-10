from __future__ import annotations

from datetime import date

from aip.application.irrbb.source_certification import (
    IRRBBSourcePerimeter,
    IRRBBSourceRequirement,
    IRRBBSourceRequirementProfile,
)


INVESTMENT_SOURCE_REQUIREMENT_PROFILE_CODE = "RTILB-INVESTMENT-SOURCE"
INVESTMENT_SOURCE_REQUIREMENT_PROFILE_VERSION = "2026.09.10"
INVESTMENT_SOURCE_REQUIREMENT_PROFILE_REFERENCE = (
    "docs/architecture/IRRBB_PHASE12_INVESTMENT_SOURCE_EVIDENCE.md"
)


def investment_source_requirement_profile() -> IRRBBSourceRequirementProfile:
    """Return the versioned canonical requirements for an investment-position source.

    The profile deliberately describes RTILB concepts only. Physical workbook,
    database or API field names belong to adapter-owned evidence assessors.
    """

    requirements = (
        _requirement(
            "INV-CUTOFF-DATE",
            "cutoff_date",
            "Valuation cutoff must be traceable to the source snapshot.",
        ),
        _requirement(
            "INV-POSITION-ID",
            "position_id",
            "Each investment position requires a stable and reproducible identifier.",
        ),
        _requirement(
            "INV-SOURCE-REFERENCE",
            "source_reference",
            "Each investment position requires auditable source lineage.",
        ),
        _requirement(
            "INV-PRODUCT-TYPE",
            "product_type",
            "Institutional product identity is required before canonical classification.",
        ),
        _requirement(
            "INV-INSTRUMENT-CLASS",
            "instrument_class",
            "Investment instrument class requires an approved deterministic mapping.",
        ),
        _requirement(
            "INV-SIDE",
            "side",
            "Balance-sheet side requires an approved deterministic mapping.",
        ),
        _requirement(
            "INV-CURRENCY",
            "currency",
            "Contractual currency is required and must not be silently defaulted.",
        ),
        _requirement(
            "INV-PRINCIPAL",
            "principal",
            "Outstanding contractual principal or nominal is required.",
        ),
        _requirement(
            "INV-CARRYING-AMOUNT",
            "carrying_amount",
            "Carrying amount is required for source-to-accounting reconciliation.",
        ),
        _requirement(
            "INV-RATE-TYPE",
            "rate_type",
            "Fixed versus floating rate behavior must be explicitly classifiable.",
        ),
        _requirement(
            "INV-CONTRACTUAL-RATE",
            "contractual_rate",
            "Current contractual/facial rate is required when no sufficient schedule exists.",
        ),
        _requirement(
            "INV-MATURITY-DATE",
            "maturity_date",
            "Contractual maturity is required for term investments.",
        ),
        _requirement(
            "INV-NEXT-REPRICING-DATE",
            "next_repricing_date",
            "Floating investments require the next contractual reset date.",
        ),
        _requirement(
            "INV-REPRICING-FREQUENCY",
            "repricing_frequency_months",
            "Floating investments require contractual repricing frequency.",
        ),
        _requirement(
            "INV-PAYMENT-FREQUENCY",
            "payment_frequency_months",
            "Coupon-bearing investments require payment frequency or an explicit schedule.",
        ),
        _requirement(
            "INV-PAYMENT-STRUCTURE",
            "payment_structure",
            "Payment structure must be explicitly mapped before RTILB cash-flow construction.",
        ),
        _requirement(
            "INV-CONTRACTUAL-SCHEDULE",
            "contractual_cashflow_schedule",
            "Contractual investment cash-flow dates and amounts must be source-provided or deterministically derivable.",
        ),
        _requirement(
            "INV-OPTIONALITY",
            "optionality",
            "Material embedded optionality must be explicitly classified and never inferred as absent.",
        ),
    )
    return IRRBBSourceRequirementProfile(
        code=INVESTMENT_SOURCE_REQUIREMENT_PROFILE_CODE,
        version=INVESTMENT_SOURCE_REQUIREMENT_PROFILE_VERSION,
        effective_from=date(2026, 9, 10),
        source_reference=INVESTMENT_SOURCE_REQUIREMENT_PROFILE_REFERENCE,
        requirements=requirements,
    )


def _requirement(
    requirement_id: str,
    canonical_variable: str,
    description: str,
) -> IRRBBSourceRequirement:
    return IRRBBSourceRequirement(
        requirement_id=requirement_id,
        canonical_variable=canonical_variable,
        perimeter=IRRBBSourcePerimeter.INVESTMENT,
        description=description,
    )
