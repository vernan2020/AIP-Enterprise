from __future__ import annotations

from aip.domain.irrbb.models import (
    BankingBookPosition,
    BankingBookSide,
    IRRBBInstrumentClass,
    RateType,
)
from aip.domain.irrbb.sugef_standard_gap import (
    SugefGapCounterpartyFamily,
    SugefGapFundingTermType,
    SugefGapReportLine,
    SugefGapRoutingMetadata,
    SugefGapRowClassification,
    SugefGapRowClassificationStatus,
)


class SugefGapRowClassifierService:
    """Map one normalized banking-book position into the visible SUGEF GAP row taxonomy.

    The service deliberately keeps SUGEF-specific counterparty and funding metadata
    outside ``BankingBookPosition``. Unsupported or ambiguous cases are surfaced as
    incomplete/pending classifications rather than forced into a report row.
    """

    _TERM_LINES = {
        (SugefGapCounterpartyFamily.PUBLIC, RateType.FIXED): SugefGapReportLine.PUBLIC_TERM_FIXED,
        (
            SugefGapCounterpartyFamily.PUBLIC,
            RateType.FLOATING,
        ): SugefGapReportLine.PUBLIC_TERM_VARIABLE_SEMIVARIABLE,
        (SugefGapCounterpartyFamily.BCCR, RateType.FIXED): SugefGapReportLine.BCCR_TERM_FIXED,
        (
            SugefGapCounterpartyFamily.BCCR,
            RateType.FLOATING,
        ): SugefGapReportLine.BCCR_TERM_VARIABLE_SEMIVARIABLE,
        (
            SugefGapCounterpartyFamily.FINANCIAL_ENTITY,
            RateType.FIXED,
        ): SugefGapReportLine.FINANCIAL_ENTITY_TERM_FIXED,
        (
            SugefGapCounterpartyFamily.FINANCIAL_ENTITY,
            RateType.FLOATING,
        ): SugefGapReportLine.FINANCIAL_ENTITY_TERM_VARIABLE_SEMIVARIABLE,
    }

    _SIGHT_LINES = {
        (
            SugefGapCounterpartyFamily.PUBLIC,
            True,
        ): SugefGapReportLine.PUBLIC_SIGHT_WITH_COST,
        (
            SugefGapCounterpartyFamily.PUBLIC,
            False,
        ): SugefGapReportLine.PUBLIC_SIGHT_WITHOUT_COST,
        (
            SugefGapCounterpartyFamily.BCCR,
            True,
        ): SugefGapReportLine.BCCR_SIGHT_WITH_COST,
        (
            SugefGapCounterpartyFamily.BCCR,
            False,
        ): SugefGapReportLine.BCCR_SIGHT_WITHOUT_COST,
        (
            SugefGapCounterpartyFamily.FINANCIAL_ENTITY,
            True,
        ): SugefGapReportLine.FINANCIAL_ENTITY_SIGHT_WITH_COST,
        (
            SugefGapCounterpartyFamily.FINANCIAL_ENTITY,
            False,
        ): SugefGapReportLine.FINANCIAL_ENTITY_SIGHT_WITHOUT_COST,
    }

    @classmethod
    def classify(
        cls,
        *,
        position: BankingBookPosition,
        routing: SugefGapRoutingMetadata | None = None,
    ) -> SugefGapRowClassification:
        if routing is not None and routing.position_id != position.position_id:
            raise ValueError("routing position_id must match banking-book position_id")

        if position.side is BankingBookSide.ASSET:
            return cls._classify_asset(position)
        if position.side is BankingBookSide.LIABILITY:
            return cls._classify_liability(position=position, routing=routing)
        return cls._pending(
            position.position_id,
            "The workbook requires interest-rate hedging derivatives but provides no explicit visible derivative row.",
        )

    @classmethod
    def _classify_asset(cls, position: BankingBookPosition) -> SugefGapRowClassification:
        if position.instrument_class is IRRBBInstrumentClass.INVESTMENT:
            line = (
                SugefGapReportLine.INVESTMENT_FIXED
                if position.rate_type is RateType.FIXED
                else SugefGapReportLine.INVESTMENT_VARIABLE_SEMIVARIABLE
            )
            return cls._mapped(position.position_id, line)

        if position.instrument_class is IRRBBInstrumentClass.CREDIT:
            line = (
                SugefGapReportLine.CREDIT_FIXED
                if position.rate_type is RateType.FIXED
                else SugefGapReportLine.CREDIT_VARIABLE_SEMIVARIABLE
            )
            return cls._mapped(position.position_id, line)

        return cls._not_applicable(
            position.position_id,
            "Asset instrument class is not represented by a visible asset row in the supplied SUGEF workbook.",
        )

    @classmethod
    def _classify_liability(
        cls,
        *,
        position: BankingBookPosition,
        routing: SugefGapRoutingMetadata | None,
    ) -> SugefGapRowClassification:
        if routing is None:
            return cls._incomplete(
                position.position_id,
                "SUGEF liability routing requires counterparty family and sight/term metadata.",
            )

        if routing.counterparty_family is SugefGapCounterpartyFamily.NON_FINANCIAL_ENTITY:
            return cls._pending(
                position.position_id,
                "Account/family for non-financial entities is in the workbook perimeter, but no dedicated visible row is defined.",
            )

        if routing.counterparty_family is SugefGapCounterpartyFamily.OTHER:
            return cls._incomplete(
                position.position_id,
                "Liability counterparty family is required to select the SUGEF report row.",
            )

        if routing.funding_term_type is SugefGapFundingTermType.UNKNOWN:
            return cls._incomplete(
                position.position_id,
                "Sight/term classification is required to select the SUGEF report row.",
            )

        if routing.funding_term_type is SugefGapFundingTermType.SIGHT:
            if routing.has_financial_cost is None:
                return cls._incomplete(
                    position.position_id,
                    "Sight obligations require with/without financial-cost classification.",
                )
            line = cls._SIGHT_LINES.get(
                (routing.counterparty_family, routing.has_financial_cost)
            )
            if line is None:
                return cls._pending(
                    position.position_id,
                    "The sight-obligation counterparty family has no visible SUGEF report row.",
                )
            return cls._mapped(position.position_id, line)

        line = cls._TERM_LINES.get((routing.counterparty_family, position.rate_type))
        if line is None:
            return cls._pending(
                position.position_id,
                "The term-obligation counterparty/rate combination has no visible SUGEF report row.",
            )
        return cls._mapped(position.position_id, line)

    @staticmethod
    def _mapped(position_id: str, line: SugefGapReportLine) -> SugefGapRowClassification:
        return SugefGapRowClassification(
            position_id=position_id,
            status=SugefGapRowClassificationStatus.MAPPED,
            report_line=line,
            reason="Position mapped to the visible SUGEF supervisory row taxonomy.",
        )

    @staticmethod
    def _incomplete(position_id: str, reason: str) -> SugefGapRowClassification:
        return SugefGapRowClassification(
            position_id=position_id,
            status=SugefGapRowClassificationStatus.INCOMPLETE,
            report_line=None,
            reason=reason,
        )

    @staticmethod
    def _pending(position_id: str, reason: str) -> SugefGapRowClassification:
        return SugefGapRowClassification(
            position_id=position_id,
            status=SugefGapRowClassificationStatus.MAPPING_PENDING,
            report_line=None,
            reason=reason,
        )

    @staticmethod
    def _not_applicable(position_id: str, reason: str) -> SugefGapRowClassification:
        return SugefGapRowClassification(
            position_id=position_id,
            status=SugefGapRowClassificationStatus.NOT_APPLICABLE,
            report_line=None,
            reason=reason,
        )
