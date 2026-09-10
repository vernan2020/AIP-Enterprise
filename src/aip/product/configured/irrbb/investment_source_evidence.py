from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from aip.application.irrbb.investment_source_requirements import (
    investment_source_requirement_profile,
)
from aip.application.irrbb.source_certification import (
    IRRBBSourceAvailabilityStatus,
    IRRBBSourceCertificationReport,
    IRRBBSourceCertificationService,
    IRRBBSourceRequirementAssessment,
)
from aip.domain.irrbb.models import RateType
from aip.product.configured.irrbb.investment_source_rules import (
    InvestmentMasterSourceRules,
)
from aip.product.configured.readers.institutional_portfolio_master_reader import (
    InstitutionalPortfolioMasterReadResult,
)


class InvestmentMasterSourceEvidenceAssessor:
    """Assess the institutional investment master against canonical RTILB needs.

    This service certifies evidence only. It does not map positions into the IRRBB
    runtime and never consumes the dashboard payload that defaults missing values
    to zero.
    """

    SOURCE_REFERENCE = "SOURCE:INSTITUTIONAL-PORTFOLIO-MASTER"

    @classmethod
    def assess(
        cls,
        result: InstitutionalPortfolioMasterReadResult,
    ) -> IRRBBSourceCertificationReport:
        mapping = result.detected_column_mapping
        positions = tuple(result.normalized_positions)
        rate_types = tuple(
            InvestmentMasterSourceRules.rate_type(position.get("variable_rate_flag"))
            for position in positions
        )
        rate_type_assessed = bool(positions) and all(item is not None for item in rate_types)
        has_floating = rate_type_assessed and any(item is RateType.FLOATING for item in rate_types)

        assessments = (
            cls._not_assessed(
                "INV-CUTOFF-DATE",
                "The reader exposes a valuation date, but the current contract does not prove that the cutoff is native to the workbook rather than inferred or supplied by the adapter.",
            ),
            cls._position_id_assessment(result),
            cls._source_reference_assessment(result),
            cls._native_column(
                "INV-PRODUCT-TYPE",
                "product_code",
                mapping,
                blocking=False,
            ),
            cls._not_assessed(
                "INV-INSTRUMENT-CLASS",
                "No approved RTILB product-to-instrument-class mapping is attached to this source candidate.",
            ),
            cls._not_assessed(
                "INV-SIDE",
                "No approved source classification rule has yet been attached to derive BankingBookSide.",
            ),
            cls._native_column(
                "INV-CURRENCY",
                "currency",
                mapping,
                blocking=True,
                missing_message="Contractual currency is not evidenced by a detected source column; the existing portfolio reader default to CRC is not acceptable for RTILB certification.",
            ),
            cls._principal_assessment(mapping),
            cls._native_column(
                "INV-CARRYING-AMOUNT",
                "book_value",
                mapping,
                blocking=False,
            ),
            cls._rate_type_assessment(result, rate_types),
            cls._native_column(
                "INV-CONTRACTUAL-RATE",
                "nominal_rate",
                mapping,
                blocking=False,
            ),
            cls._native_column(
                "INV-MATURITY-DATE",
                "maturity_date",
                mapping,
                blocking=True,
            ),
            cls._repricing_assessment(
                requirement_id="INV-NEXT-REPRICING-DATE",
                rate_type_assessed=rate_type_assessed,
                has_floating=has_floating,
                message=(
                    "Floating investment positions are present, but the institutional master has no certified native next-reset date. The current portfolio duration service derives a next coupon date; that proxy is not certified as a contractual repricing date for RTILB."
                ),
            ),
            cls._repricing_assessment(
                requirement_id="INV-REPRICING-FREQUENCY",
                rate_type_assessed=rate_type_assessed,
                has_floating=has_floating,
                message=(
                    "Floating investment positions are present, but coupon periodicity has not been approved as equivalent to contractual repricing frequency."
                ),
            ),
            cls._payment_frequency_assessment(result),
            cls._not_assessed(
                "INV-PAYMENT-STRUCTURE",
                "No native payment-structure field or approved product mapping has been certified for the institutional master.",
            ),
            cls._cashflow_schedule_assessment(result),
            cls._not_assessed(
                "INV-OPTIONALITY",
                "The institutional master exposes no certified optionality classification; absence of a field cannot be interpreted as OptionalityType.NONE.",
            ),
        )
        return IRRBBSourceCertificationService.certify(
            profile=investment_source_requirement_profile(),
            assessments=assessments,
        )

    @classmethod
    def _position_id_assessment(
        cls,
        result: InstitutionalPortfolioMasterReadResult,
    ) -> IRRBBSourceRequirementAssessment:
        mapping = result.detected_column_mapping
        has_source_components = "contract_number" in mapping and (
            "isin" in mapping or "series" in mapping
        )
        if not has_source_components or not result.normalized_positions:
            return cls._blocking(
                "INV-POSITION-ID",
                "A stable position identifier cannot be certified from the detected source columns. RTILB does not permit the current row-number fallback as a stable cross-cutoff identity.",
            )

        identities = tuple(
            InvestmentMasterSourceRules.stable_position_id(
                contract_number=position.get("contract_number"),
                isin=position.get("isin"),
                series=position.get("series"),
            )
            for position in result.normalized_positions
        )
        if any(identity is None for identity in identities) or len(set(identities)) != len(
            identities
        ):
            return cls._blocking(
                "INV-POSITION-ID",
                "At least one accepted source row cannot produce a unique stable position identifier without using row position.",
            )

        return IRRBBSourceRequirementAssessment(
            requirement_id="INV-POSITION-ID",
            status=IRRBBSourceAvailabilityStatus.DERIVABLE_WITH_DOCUMENTED_RULE,
            source_reference=cls.SOURCE_REFERENCE,
            derivation_rule_reference=InvestmentMasterSourceRules.POSITION_ID_RULE_REFERENCE,
            evidence_reference=cls._column_evidence(
                result,
                tuple(name for name in ("contract_number", "isin", "series") if name in mapping),
            ),
            notes="Stable ID requires contract number plus ISIN, or contract number plus series; row number is never used.",
        )

    @classmethod
    def _source_reference_assessment(
        cls,
        result: InstitutionalPortfolioMasterReadResult,
    ) -> IRRBBSourceRequirementAssessment:
        file_name = Path(result.source_file).name if result.source_file else ""
        if not file_name:
            return cls._not_assessed(
                "INV-SOURCE-REFERENCE",
                "No source-file reference is available from the reader result.",
            )
        return IRRBBSourceRequirementAssessment(
            requirement_id="INV-SOURCE-REFERENCE",
            status=IRRBBSourceAvailabilityStatus.AVAILABLE_FROM_SUPPLEMENTARY_SOURCE,
            supplementary_source_reference=cls.SOURCE_REFERENCE,
            evidence_reference=f"EVIDENCE:PORTFOLIO-MASTER:FILE:{file_name}",
            notes="Source lineage is supplied by adapter metadata and must be copied unchanged to each canonical record.",
        )

    @classmethod
    def _principal_assessment(
        cls,
        mapping: dict[str, str],
    ) -> IRRBBSourceRequirementAssessment:
        available = tuple(
            field for field in ("principal_balance", "traded_balance") if field in mapping
        )
        if not available:
            return cls._blocking(
                "INV-PRINCIPAL",
                "Neither outstanding principal balance nor traded nominal balance is evidenced by the detected source columns.",
            )
        headers = ",".join(mapping[field] for field in available)
        return IRRBBSourceRequirementAssessment(
            requirement_id="INV-PRINCIPAL",
            status=IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE,
            source_reference=cls.SOURCE_REFERENCE,
            evidence_reference=f"EVIDENCE:PORTFOLIO-MASTER:COLUMNS:{headers}",
            notes="The RTILB mapper must preserve missing source amounts as missing; it must not reuse dashboard zero defaults.",
        )

    @classmethod
    def _rate_type_assessment(
        cls,
        result: InstitutionalPortfolioMasterReadResult,
        rate_types: tuple[RateType | None, ...],
    ) -> IRRBBSourceRequirementAssessment:
        mapping = result.detected_column_mapping
        if "variable_rate_flag" not in mapping or not result.normalized_positions:
            return cls._blocking(
                "INV-RATE-TYPE",
                "The source candidate does not provide enough evidence to classify fixed versus floating positions.",
            )
        if any(item is None for item in rate_types):
            return cls._blocking(
                "INV-RATE-TYPE",
                "At least one accepted row contains a variable-rate flag outside the strict approved mapping set.",
            )
        return IRRBBSourceRequirementAssessment(
            requirement_id="INV-RATE-TYPE",
            status=IRRBBSourceAvailabilityStatus.DERIVABLE_WITH_DOCUMENTED_RULE,
            source_reference=cls.SOURCE_REFERENCE,
            derivation_rule_reference=InvestmentMasterSourceRules.RATE_TYPE_RULE_REFERENCE,
            evidence_reference=cls._column_evidence(result, ("variable_rate_flag",)),
        )

    @classmethod
    def _repricing_assessment(
        cls,
        *,
        requirement_id: str,
        rate_type_assessed: bool,
        has_floating: bool,
        message: str,
    ) -> IRRBBSourceRequirementAssessment:
        if not rate_type_assessed:
            return cls._not_assessed(
                requirement_id,
                "Applicability cannot be determined until rate type is fully classifiable.",
            )
        if not has_floating:
            return IRRBBSourceRequirementAssessment(
                requirement_id=requirement_id,
                status=IRRBBSourceAvailabilityStatus.NOT_APPLICABLE,
                notes="No floating-rate investment positions are present in the assessed source snapshot.",
            )
        return cls._blocking(requirement_id, message)

    @classmethod
    def _payment_frequency_assessment(
        cls,
        result: InstitutionalPortfolioMasterReadResult,
    ) -> IRRBBSourceRequirementAssessment:
        coupon_positions = tuple(
            position
            for position in result.normalized_positions
            if (cls._decimal(position.get("nominal_rate")) or Decimal("0")) > 0
        )
        if not coupon_positions:
            return IRRBBSourceRequirementAssessment(
                requirement_id="INV-PAYMENT-FREQUENCY",
                status=IRRBBSourceAvailabilityStatus.NOT_APPLICABLE,
                notes="No positive-coupon investment positions are present in the assessed source snapshot.",
            )
        if "periodicity" not in result.detected_column_mapping:
            return cls._blocking(
                "INV-PAYMENT-FREQUENCY",
                "Coupon-bearing positions are present but no coupon periodicity column was detected.",
            )
        if any(
            InvestmentMasterSourceRules.payment_frequency_months(position.get("periodicity"))
            is None
            for position in coupon_positions
        ):
            return cls._blocking(
                "INV-PAYMENT-FREQUENCY",
                "At least one coupon-bearing position contains an unsupported or missing periodicity.",
            )
        return IRRBBSourceRequirementAssessment(
            requirement_id="INV-PAYMENT-FREQUENCY",
            status=IRRBBSourceAvailabilityStatus.DERIVABLE_WITH_DOCUMENTED_RULE,
            source_reference=cls.SOURCE_REFERENCE,
            derivation_rule_reference=InvestmentMasterSourceRules.PAYMENT_FREQUENCY_RULE_REFERENCE,
            evidence_reference=cls._column_evidence(result, ("periodicity",)),
        )

    @classmethod
    def _cashflow_schedule_assessment(
        cls,
        result: InstitutionalPortfolioMasterReadResult,
    ) -> IRRBBSourceRequirementAssessment:
        if not result.normalized_positions:
            return cls._not_assessed(
                "INV-CONTRACTUAL-SCHEDULE",
                "No accepted investment rows are available to verify cash-flow derivation prerequisites.",
            )

        for position in result.normalized_positions:
            principal = cls._decimal(position.get("principal_balance"))
            if principal is None or principal <= 0:
                principal = cls._decimal(position.get("traded_balance"))
            if principal is None or principal <= 0 or position.get("maturity_date") is None:
                return cls._not_assessed(
                    "INV-CONTRACTUAL-SCHEDULE",
                    "At least one accepted row lacks positive principal/nominal or contractual maturity required by the existing investment cash-flow builder.",
                )
            coupon_rate = cls._decimal(position.get("nominal_rate"))
            if coupon_rate is not None and coupon_rate > 0:
                months = InvestmentMasterSourceRules.payment_frequency_months(
                    position.get("periodicity")
                )
                if months is None:
                    return cls._not_assessed(
                        "INV-CONTRACTUAL-SCHEDULE",
                        "At least one coupon-bearing row lacks a supported payment periodicity for deterministic cash-flow dates.",
                    )

        return IRRBBSourceRequirementAssessment(
            requirement_id="INV-CONTRACTUAL-SCHEDULE",
            status=IRRBBSourceAvailabilityStatus.DERIVABLE_WITH_DOCUMENTED_RULE,
            source_reference=cls.SOURCE_REFERENCE,
            derivation_rule_reference=InvestmentMasterSourceRules.CASHFLOW_RULE_REFERENCE,
            evidence_reference=(
                "EVIDENCE:CODE:PortfolioContractualCashFlowService+"
                + cls._column_evidence(
                    result,
                    tuple(
                        name
                        for name in (
                            "principal_balance",
                            "traded_balance",
                            "maturity_date",
                            "nominal_rate",
                            "periodicity",
                            "last_interest_payment_date",
                        )
                        if name in result.detected_column_mapping
                    ),
                )
            ),
            notes="Variable-rate coupon amounts produced by the existing builder remain projected-current-rate flows; stressed repricing is a separate IRRBB strategy concern.",
        )

    @classmethod
    def _native_column(
        cls,
        requirement_id: str,
        canonical_column: str,
        mapping: dict[str, str],
        *,
        blocking: bool,
        missing_message: str | None = None,
    ) -> IRRBBSourceRequirementAssessment:
        header = mapping.get(canonical_column)
        if header and str(header).strip():
            return IRRBBSourceRequirementAssessment(
                requirement_id=requirement_id,
                status=IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE,
                source_reference=cls.SOURCE_REFERENCE,
                evidence_reference=f"EVIDENCE:PORTFOLIO-MASTER:COLUMN:{header}",
            )
        message = missing_message or f"No detected source column supports {canonical_column}."
        return (
            cls._blocking(requirement_id, message)
            if blocking
            else cls._not_assessed(requirement_id, message)
        )

    @classmethod
    def _blocking(
        cls,
        requirement_id: str,
        message: str,
    ) -> IRRBBSourceRequirementAssessment:
        return IRRBBSourceRequirementAssessment(
            requirement_id=requirement_id,
            status=IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE,
            evidence_reference="EVIDENCE:PORTFOLIO-MASTER:ASSESSMENT",
            notes=message,
        )

    @classmethod
    def _not_assessed(
        cls,
        requirement_id: str,
        message: str,
    ) -> IRRBBSourceRequirementAssessment:
        return IRRBBSourceRequirementAssessment(
            requirement_id=requirement_id,
            status=IRRBBSourceAvailabilityStatus.NOT_ASSESSED,
            evidence_reference="EVIDENCE:PORTFOLIO-MASTER:ASSESSMENT",
            notes=message,
        )

    @classmethod
    def _column_evidence(
        cls,
        result: InstitutionalPortfolioMasterReadResult,
        canonical_columns: tuple[str, ...],
    ) -> str:
        file_name = Path(result.source_file).name if result.source_file else "UNKNOWN"
        headers = tuple(
            result.detected_column_mapping[column]
            for column in canonical_columns
            if column in result.detected_column_mapping
        )
        return f"EVIDENCE:PORTFOLIO-MASTER:{file_name}:COLUMNS:{'|'.join(headers)}"

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value in (None, "") or isinstance(value, bool):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None
