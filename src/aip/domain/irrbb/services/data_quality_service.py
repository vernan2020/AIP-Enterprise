from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.irrbb.data_quality import (
    IRRBBDataIssueCode,
    IRRBBDataQualityIssue,
    IRRBBDataQualitySeverity,
    IRRBBDataQualityStatus,
    IRRBBPositionAssessment,
    IRRBBValidationContext,
)
from aip.domain.irrbb.models import (
    BankingBookPosition,
    IRRBBInstrumentClass,
    OptionalityType,
    PaymentStructure,
    RateType,
)


class IRRBBPositionDataQualityService:
    """Assess whether one position is ready for the IRRBB EVE workflow.

    The service separates missing source data from missing approved calculation
    capabilities. It never imputes dates, rates, schedules or behavioral assumptions.
    """

    _SUPPORTED_INVESTMENT_PAYMENT_MONTHS = frozenset({1, 2, 3, 4, 6, 12})

    @classmethod
    def assess(
        cls,
        *,
        position: BankingBookPosition,
        valuation_date: date,
        context: IRRBBValidationContext | None = None,
    ) -> IRRBBPositionAssessment:
        context = context or IRRBBValidationContext()

        if position.principal.amount == Decimal("0"):
            return cls._excluded(
                position,
                IRRBBDataIssueCode.ZERO_PRINCIPAL,
                "principal",
                "Zero-principal position has no current IRRBB notional exposure.",
            )

        if (
            position.instrument_class is not IRRBBInstrumentClass.NON_MATURITY_DEPOSIT
            and position.maturity_date is not None
            and position.maturity_date <= valuation_date
        ):
            return cls._excluded(
                position,
                IRRBBDataIssueCode.MATURED_POSITION,
                "maturity_date",
                "Position is contractually matured at the valuation date.",
            )

        issues: list[IRRBBDataQualityIssue] = []

        if position.origination_date is not None and position.origination_date > valuation_date:
            issues.append(
                cls._error(
                    IRRBBDataIssueCode.ORIGINATION_AFTER_VALUATION,
                    "origination_date",
                    "Origination date is after the valuation date.",
                )
            )

        if (
            position.instrument_class is not IRRBBInstrumentClass.NON_MATURITY_DEPOSIT
            and position.maturity_date is None
        ):
            issues.append(
                cls._error(
                    IRRBBDataIssueCode.MATURITY_MISSING,
                    "maturity_date",
                    "Contractual maturity is required for this instrument class.",
                )
            )

        cls._assess_schedule_requirements(position, context, issues)
        cls._assess_rate_requirements(position, context, valuation_date, issues)
        cls._assess_behavioral_requirements(position, context, issues)
        cls._assess_investment_schedule_compatibility(position, context, issues)

        status = (
            IRRBBDataQualityStatus.INCOMPLETE
            if any(issue.severity is IRRBBDataQualitySeverity.ERROR for issue in issues)
            else IRRBBDataQualityStatus.READY
        )
        return IRRBBPositionAssessment(
            position_id=position.position_id,
            status=status,
            issues=tuple(issues),
        )

    @classmethod
    def _assess_schedule_requirements(
        cls,
        position: BankingBookPosition,
        context: IRRBBValidationContext,
        issues: list[IRRBBDataQualityIssue],
    ) -> None:
        if position.instrument_class is IRRBBInstrumentClass.NON_MATURITY_DEPOSIT:
            return

        if (
            position.payment_structure is PaymentStructure.OTHER
            and position.instrument_class is not IRRBBInstrumentClass.INVESTMENT
            and not context.explicit_schedule_available
        ):
            issues.append(
                cls._error(
                    IRRBBDataIssueCode.PAYMENT_STRUCTURE_MISSING,
                    "payment_structure",
                    "Payment structure is required when no explicit schedule is available.",
                )
            )

        requires_explicit_schedule = (
            position.payment_structure
            in {PaymentStructure.AMORTIZING, PaymentStructure.EXPLICIT_SCHEDULE}
            or position.instrument_class is IRRBBInstrumentClass.OFF_BALANCE
        )
        if requires_explicit_schedule and not context.explicit_schedule_available:
            issues.append(
                cls._error(
                    IRRBBDataIssueCode.EXPLICIT_SCHEDULE_REQUIRED,
                    "contractual_schedule",
                    "An explicit normalized contractual cash-flow schedule is required.",
                )
            )

    @classmethod
    def _assess_rate_requirements(
        cls,
        position: BankingBookPosition,
        context: IRRBBValidationContext,
        valuation_date: date,
        issues: list[IRRBBDataQualityIssue],
    ) -> None:
        if position.instrument_class is IRRBBInstrumentClass.NON_MATURITY_DEPOSIT:
            return

        if position.rate_type is RateType.FIXED:
            if not context.explicit_schedule_available and position.contractual_rate is None:
                issues.append(
                    cls._error(
                        IRRBBDataIssueCode.CONTRACTUAL_RATE_MISSING,
                        "contractual_rate",
                        "Fixed-rate position requires an explicit contractual rate or schedule.",
                    )
                )
            if (
                not context.explicit_schedule_available
                and position.contractual_rate not in (None, Decimal("0"))
                and position.payment_frequency_months is None
            ):
                issues.append(
                    cls._error(
                        IRRBBDataIssueCode.PAYMENT_FREQUENCY_MISSING,
                        "payment_frequency_months",
                        "Interest-bearing fixed position requires payment frequency or schedule.",
                    )
                )
            return

        if position.next_repricing_date is None:
            issues.append(
                cls._error(
                    IRRBBDataIssueCode.NEXT_REPRICING_MISSING,
                    "next_repricing_date",
                    "Floating-rate position requires the next contractual repricing date.",
                )
            )
        else:
            if position.next_repricing_date < valuation_date:
                issues.append(
                    cls._error(
                        IRRBBDataIssueCode.NEXT_REPRICING_BEFORE_VALUATION,
                        "next_repricing_date",
                        "Next repricing date is before the valuation date.",
                    )
                )
            if (
                position.maturity_date is not None
                and position.next_repricing_date > position.maturity_date
            ):
                issues.append(
                    cls._error(
                        IRRBBDataIssueCode.NEXT_REPRICING_AFTER_MATURITY,
                        "next_repricing_date",
                        "Next repricing date cannot be after contractual maturity.",
                    )
                )

        if position.repricing_frequency_months is None:
            issues.append(
                cls._error(
                    IRRBBDataIssueCode.REPRICING_FREQUENCY_MISSING,
                    "repricing_frequency_months",
                    "Floating-rate position requires a contractual repricing frequency.",
                )
            )

        has_current_rate = position.contractual_rate is not None
        has_reference_basis = bool(position.reference_rate) and position.spread is not None
        if not has_current_rate and not has_reference_basis:
            issues.append(
                cls._error(
                    IRRBBDataIssueCode.FLOATING_RATE_BASIS_MISSING,
                    "contractual_rate/reference_rate/spread",
                    "Floating-rate position requires current rate or reference-rate basis.",
                )
            )

        if not context.scenario_repricing_model_available:
            issues.append(
                cls._error(
                    IRRBBDataIssueCode.SCENARIO_REPRICING_MODEL_REQUIRED,
                    None,
                    "Stressed EVE requires an approved scenario-aware floating-rate projector.",
                )
            )

    @classmethod
    def _assess_behavioral_requirements(
        cls,
        position: BankingBookPosition,
        context: IRRBBValidationContext,
        issues: list[IRRBBDataQualityIssue],
    ) -> None:
        is_nmd = (
            position.instrument_class is IRRBBInstrumentClass.NON_MATURITY_DEPOSIT
            or position.payment_structure is PaymentStructure.NON_MATURITY
            or position.optionality is OptionalityType.NON_MATURITY_DEPOSIT
        )
        if is_nmd and not context.behavioral_model_available:
            issues.append(
                cls._error(
                    IRRBBDataIssueCode.BEHAVIORAL_MODEL_REQUIRED,
                    None,
                    "Non-maturity deposits require an approved behavioral cash-flow model.",
                )
            )
            return

        if position.optionality is not OptionalityType.NONE and not context.behavioral_model_available:
            issues.append(
                cls._error(
                    IRRBBDataIssueCode.OPTIONALITY_MODEL_REQUIRED,
                    "optionality",
                    "Material contractual optionality requires an approved behavioral model.",
                )
            )

    @classmethod
    def _assess_investment_schedule_compatibility(
        cls,
        position: BankingBookPosition,
        context: IRRBBValidationContext,
        issues: list[IRRBBDataQualityIssue],
    ) -> None:
        if (
            position.instrument_class is not IRRBBInstrumentClass.INVESTMENT
            or context.explicit_schedule_available
            or position.contractual_rate in (None, Decimal("0"))
        ):
            return

        if position.payment_frequency_months is None:
            return
        if position.payment_frequency_months not in cls._SUPPORTED_INVESTMENT_PAYMENT_MONTHS:
            issues.append(
                cls._error(
                    IRRBBDataIssueCode.UNSUPPORTED_INVESTMENT_PAYMENT_FREQUENCY,
                    "payment_frequency_months",
                    "Investment payment frequency is not supported by the canonical portfolio schedule.",
                )
            )

    @staticmethod
    def _error(
        code: IRRBBDataIssueCode,
        field_name: str | None,
        message: str,
    ) -> IRRBBDataQualityIssue:
        return IRRBBDataQualityIssue(
            code=code,
            field_name=field_name,
            message=message,
            severity=IRRBBDataQualitySeverity.ERROR,
        )

    @staticmethod
    def _excluded(
        position: BankingBookPosition,
        code: IRRBBDataIssueCode,
        field_name: str | None,
        message: str,
    ) -> IRRBBPositionAssessment:
        return IRRBBPositionAssessment(
            position_id=position.position_id,
            status=IRRBBDataQualityStatus.EXCLUDED,
            issues=(
                IRRBBDataQualityIssue(
                    code=code,
                    field_name=field_name,
                    message=message,
                    severity=IRRBBDataQualitySeverity.INFO,
                ),
            ),
        )
