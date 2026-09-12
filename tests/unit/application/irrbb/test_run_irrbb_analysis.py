from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.application.irrbb import (
    IRRBBPositionSourceRecord,
    IRRBBSourceSnapshot,
    LoadIRRBBSourceSnapshot,
)
from aip.application.irrbb.analysis_contracts import (
    IRRBBAnalysisRequest,
    IRRBBAnalysisStatus,
    IRRBBGapCoverageIssueCode,
)
from aip.application.irrbb.run_analysis import RunIRRBBAnalysis
from aip.domain.irrbb.models import (
    BankingBookPosition,
    BankingBookSide,
    CashFlowDirection,
    IRRBBCashFlow,
    IRRBBInstrumentClass,
    IRRBBMethodologyProfile,
    IRRBBMethodologyStatus,
    IRRBBScenario,
    PaymentStructure,
    RateType,
)
from aip.domain.irrbb.services.scenario_evaluation_service import (
    IRRBBScenarioEvaluationService,
)
from aip.domain.irrbb.sugef_standard_gap import (
    SugefGapReportLine,
    SugefGapScheduleRecord,
)
from aip.shared.money import Currency, Money

CUTOFF = date(2026, 8, 31)
MATURITY = date(2028, 8, 31)


def _methodology() -> IRRBBMethodologyProfile:
    return IRRBBMethodologyProfile(
        code="RTILB-SUGEF",
        version="2026.1",
        status=IRRBBMethodologyStatus.EFFECTIVE,
        source_reference="TEST:METHODOLOGY",
        effective_from=date(2026, 1, 1),
    )


def _investment(position_id: str, currency: Currency) -> BankingBookPosition:
    return BankingBookPosition(
        position_id=position_id,
        product_type="BOND",
        side=BankingBookSide.ASSET,
        currency=currency,
        principal=Money(Decimal("1000"), currency),
        rate_type=RateType.FIXED,
        maturity_date=MATURITY,
        source_reference=f"TEST:{position_id}",
        contractual_rate=Decimal("0"),
        instrument_class=IRRBBInstrumentClass.INVESTMENT,
        payment_structure=PaymentStructure.BULLET,
    )


def _gap_schedule(position: BankingBookPosition) -> tuple[SugefGapScheduleRecord, ...]:
    return (
        SugefGapScheduleRecord(
            payment_date=MATURITY,
            amount=position.principal,
            direction=CashFlowDirection.RECEIVABLE,
            flow_type="PRINCIPAL",
            source_reference=f"TEST:GAP:{position.position_id}",
        ),
    )


class _Gateway:
    def __init__(self, snapshot: IRRBBSourceSnapshot) -> None:
        self.snapshot = snapshot

    def load_snapshot(self, *, cutoff_date: date) -> IRRBBSourceSnapshot:
        assert cutoff_date == self.snapshot.cutoff_date
        return self.snapshot


class _ScenarioCashflows:
    def cashflows_for(
        self,
        *,
        position: BankingBookPosition,
        scenario: IRRBBScenario,
        valuation_date: date,
    ) -> tuple[IRRBBCashFlow, ...]:
        assert scenario is not None
        assert valuation_date == CUTOFF
        maturity = position.maturity_date
        assert maturity is not None
        return (
            IRRBBCashFlow(
                position_id=position.position_id,
                side=position.side,
                direction=CashFlowDirection.RECEIVABLE,
                amount=position.principal,
                cashflow_date=maturity,
                risk_date=maturity,
                flow_type="PRINCIPAL",
                source_reference=f"TEST:FLOW:{position.position_id}",
            ),
        )


class _DiscountFactors:
    def discount_factor(
        self,
        *,
        currency: Currency,
        scenario: IRRBBScenario,
        valuation_date: date,
        payment_date: date,
    ) -> Decimal:
        assert currency in {Currency.CRC, Currency.USD}
        assert valuation_date == CUTOFF
        assert payment_date == MATURITY
        if scenario is IRRBBScenario.BASE:
            return Decimal("1")
        if scenario is IRRBBScenario.PARALLEL_UP:
            return Decimal("0.80")
        return Decimal("0.95")


class _ExchangeRates:
    def rate(
        self,
        *,
        from_currency: Currency,
        to_currency: Currency,
        valuation_date: date,
    ) -> Decimal:
        assert valuation_date == CUTOFF
        if from_currency is to_currency:
            return Decimal("1")
        if from_currency is Currency.USD and to_currency is Currency.CRC:
            return Decimal("500")
        raise ValueError("unsupported test FX pair")


class _TierOneCapital:
    def __init__(self) -> None:
        self.calls = 0

    def tier_one_capital(
        self,
        *,
        cutoff_date: date,
        reporting_currency: Currency,
    ) -> Money:
        self.calls += 1
        assert cutoff_date == CUTOFF
        assert reporting_currency is Currency.CRC
        return Money(Decimal("1000000"), Currency.CRC)


def _analysis(snapshot: IRRBBSourceSnapshot, capital: _TierOneCapital) -> RunIRRBBAnalysis:
    source_loader = LoadIRRBBSourceSnapshot(_Gateway(snapshot))
    scenario_evaluation = IRRBBScenarioEvaluationService(
        scenario_cashflows=_ScenarioCashflows(),
        discount_factors=_DiscountFactors(),
        exchange_rates=_ExchangeRates(),
    )
    return RunIRRBBAnalysis(
        source_loader=source_loader,
        scenario_evaluation=scenario_evaluation,
        tier_one_capital=capital,
    )


def _request() -> IRRBBAnalysisRequest:
    return IRRBBAnalysisRequest(
        cutoff_date=CUTOFF,
        reporting_currency=Currency.CRC,
        methodology=_methodology(),
    )


def test_run_analysis_calculates_eve_and_mapped_gap_for_ready_position() -> None:
    position = _investment("INV-1", Currency.CRC)
    snapshot = IRRBBSourceSnapshot(
        cutoff_date=CUTOFF,
        position_records=(
            IRRBBPositionSourceRecord(
                position=position,
                gap_schedule=_gap_schedule(position),
            ),
        ),
    )
    capital = _TierOneCapital()

    result = _analysis(snapshot, capital).execute(_request())

    assert result.status is IRRBBAnalysisStatus.CALCULATED
    assert result.evaluation is not None
    assert result.evaluation.position_count == 1
    assert result.evaluation.exposure.worst_scenario is IRRBBScenario.PARALLEL_UP
    assert capital.calls == 1
    assert result.gap_issues == ()
    assert len(result.gap_results) == 1
    assert result.gap_results[0].currency is Currency.CRC
    assert result.gap_results[0].included_position_ids == ("INV-1",)
    assert result.gap_results[0].matrix_cells[0].report_line is (
        SugefGapReportLine.INVESTMENT_FIXED
    )


def test_missing_gap_schedule_is_explicit_and_does_not_block_eve() -> None:
    position = _investment("INV-1", Currency.CRC)
    snapshot = IRRBBSourceSnapshot(
        cutoff_date=CUTOFF,
        position_records=(IRRBBPositionSourceRecord(position=position),),
    )
    capital = _TierOneCapital()

    result = _analysis(snapshot, capital).execute(_request())

    assert result.status is IRRBBAnalysisStatus.CALCULATED_WITH_DATA_GAPS
    assert result.evaluation is not None
    assert result.gap_results == ()
    assert len(result.gap_issues) == 1
    assert result.gap_issues[0].code is IRRBBGapCoverageIssueCode.SCHEDULE_MISSING
    assert "No zero exposure was assumed" in result.gap_issues[0].message


def test_no_ready_positions_blocks_eve_and_does_not_request_capital() -> None:
    incomplete = BankingBookPosition(
        position_id="LOAN-1",
        product_type="CREDIT",
        side=BankingBookSide.ASSET,
        currency=Currency.CRC,
        principal=Money(Decimal("500"), Currency.CRC),
        rate_type=RateType.FLOATING,
        maturity_date=date(2030, 8, 31),
        source_reference="TEST:LOAN-1",
        reference_rate="TBP",
        spread=Decimal("0.02"),
        instrument_class=IRRBBInstrumentClass.CREDIT,
        payment_structure=PaymentStructure.AMORTIZING,
    )
    snapshot = IRRBBSourceSnapshot(
        cutoff_date=CUTOFF,
        position_records=(IRRBBPositionSourceRecord(position=incomplete),),
    )
    capital = _TierOneCapital()

    result = _analysis(snapshot, capital).execute(_request())

    assert result.status is IRRBBAnalysisStatus.BLOCKED
    assert result.evaluation is None
    assert result.tier_one_capital is None
    assert capital.calls == 0


def test_sugef_gap_keeps_crc_and_usd_in_separate_native_currency_results() -> None:
    crc = _investment("CRC-1", Currency.CRC)
    usd = _investment("USD-1", Currency.USD)
    snapshot = IRRBBSourceSnapshot(
        cutoff_date=CUTOFF,
        position_records=(
            IRRBBPositionSourceRecord(position=crc, gap_schedule=_gap_schedule(crc)),
            IRRBBPositionSourceRecord(position=usd, gap_schedule=_gap_schedule(usd)),
        ),
    )
    capital = _TierOneCapital()

    result = _analysis(snapshot, capital).execute(_request())

    assert result.status is IRRBBAnalysisStatus.CALCULATED
    assert result.evaluation is not None
    assert tuple(item.currency for item in result.gap_results) == (
        Currency.CRC,
        Currency.USD,
    )
    assert result.gap_results[0].bucket_totals[0].amount.currency is Currency.CRC
    assert result.gap_results[1].bucket_totals[0].amount.currency is Currency.USD
