from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtWidgets import QApplication

from aip.application.irrbb import (
    IRRBBAnalysisRequest,
    IRRBBAnalysisResult,
    IRRBBAnalysisStatus,
    IRRBBPositionSourceRecord,
    IRRBBSourceLoadResult,
    IRRBBSourceLoadStatus,
    IRRBBSourceSnapshot,
)
from aip.domain.irrbb.data_quality import IRRBBDataQualityStatus, IRRBBPositionAssessment
from aip.domain.irrbb.models import (
    BankingBookPosition,
    BankingBookSide,
    IRRBBInstrumentClass,
    IRRBBMethodologyProfile,
    IRRBBMethodologyStatus,
    IRRBBScenario,
    PaymentStructure,
    RateType,
)
from aip.shared.money import Currency, Money
from aip.ui.modules.rate_risk.presenters import RateRiskPresenter
from aip.ui.modules.rate_risk.views import RateRiskView

CUTOFF = date(2026, 8, 31)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _request() -> IRRBBAnalysisRequest:
    return IRRBBAnalysisRequest(
        cutoff_date=CUTOFF,
        reporting_currency=Currency.CRC,
        methodology=IRRBBMethodologyProfile(
            code="RTILB-SUGEF",
            version="2026.1",
            status=IRRBBMethodologyStatus.EFFECTIVE,
            source_reference="TEST:METHODOLOGY",
            effective_from=date(2026, 1, 1),
        ),
        required_scenarios=(IRRBBScenario.PARALLEL_UP,),
    )


def _position(
    position_id: str,
    instrument_class: IRRBBInstrumentClass,
    side: BankingBookSide,
    currency: Currency,
) -> IRRBBPositionSourceRecord:
    return IRRBBPositionSourceRecord(
        position=BankingBookPosition(
            position_id=position_id,
            product_type=instrument_class.value,
            side=side,
            currency=currency,
            principal=Money(Decimal("1000"), currency),
            rate_type=RateType.FIXED,
            maturity_date=date(2028, 8, 31),
            source_reference=f"TEST:{position_id}",
            contractual_rate=Decimal("0.05"),
            payment_frequency_months=1,
            instrument_class=instrument_class,
            payment_structure=PaymentStructure.BULLET,
        )
    )


def _blocked_multisource_result() -> IRRBBAnalysisResult:
    records = (
        _position("CR-CRC", IRRBBInstrumentClass.CREDIT, BankingBookSide.ASSET, Currency.CRC),
        _position("CR-USD", IRRBBInstrumentClass.CREDIT, BankingBookSide.ASSET, Currency.USD),
        _position(
            "CDP-CRC",
            IRRBBInstrumentClass.TERM_DEPOSIT,
            BankingBookSide.LIABILITY,
            Currency.CRC,
        ),
        _position(
            "OBL-USD",
            IRRBBInstrumentClass.BORROWING,
            BankingBookSide.LIABILITY,
            Currency.USD,
        ),
    )
    assessments = (
        IRRBBPositionAssessment("CR-CRC", IRRBBDataQualityStatus.READY, ()),
        IRRBBPositionAssessment("CR-USD", IRRBBDataQualityStatus.INCOMPLETE, ()),
        IRRBBPositionAssessment("CDP-CRC", IRRBBDataQualityStatus.READY, ()),
        IRRBBPositionAssessment("OBL-USD", IRRBBDataQualityStatus.EXCLUDED, ()),
    )
    return IRRBBAnalysisResult(
        status=IRRBBAnalysisStatus.BLOCKED,
        source_load=IRRBBSourceLoadResult(
            snapshot=IRRBBSourceSnapshot(cutoff_date=CUTOFF, position_records=records),
            assessments=assessments,
            status=IRRBBSourceLoadStatus.PARTIAL,
            ready_position_ids=("CR-CRC", "CDP-CRC"),
            incomplete_position_ids=("CR-USD",),
            excluded_position_ids=("OBL-USD",),
        ),
        evaluation=None,
        tier_one_capital=None,
        gap_classifications=(),
        gap_results=(),
        gap_issues=(),
        curve_points=(),
    )


def test_presenter_exposes_multisource_perimeter_without_cross_currency_amounts() -> None:
    read_model = RateRiskPresenter.build_from_analysis(
        request=_request(),
        result=_blocked_multisource_result(),
    )

    assert tuple(row.label for row in read_model.source_summary_rows) == (
        "Crédito",
        "Captaciones · Certificados",
        "Obligaciones con Entidades",
    )
    credit, deposits, borrowings = read_model.source_summary_rows
    assert credit.position_count == 2
    assert credit.ready_count == 1
    assert credit.incomplete_count == 1
    assert credit.excluded_count == 0
    assert credit.currencies == ("CRC", "USD")
    assert deposits.position_count == 1
    assert deposits.currencies == ("CRC",)
    assert borrowings.position_count == 1
    assert borrowings.excluded_count == 1
    assert borrowings.currencies == ("USD",)


def test_view_renders_credit_captaciones_and_obligaciones_source_summary() -> None:
    _app()
    read_model = RateRiskPresenter.build_from_analysis(
        request=_request(),
        result=_blocked_multisource_result(),
    )
    view = RateRiskView(read_model)

    table = view._source_summary_table
    assert table.objectName() == "rateRiskSourceSummary"
    assert table.rowCount() == 3
    assert table.item(0, 0).text() == "Crédito"
    assert table.item(0, 1).text() == "2"
    assert table.item(0, 5).text() == "CRC, USD"
    assert table.item(1, 0).text() == "Captaciones · Certificados"
    assert table.item(2, 0).text() == "Obligaciones con Entidades"
