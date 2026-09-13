from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import (
    EntityRatingSummary,
    FinancialAnalysisSnapshot,
    FinancialEntity,
)
from aip.ui.modules.financial_analysis.presenters.financial_analysis_presenter import (
    FinancialAnalysisPresenter,
)
from aip.ui.modules.financial_analysis.viewmodels.financial_analysis_view_model import (
    FinancialAnalysisViewModel,
)
from aip.ui.modules.financial_analysis.views.financial_analysis_view import (
    FinancialAnalysisView,
)


class _Presenter:
    def __init__(self, view_model: FinancialAnalysisViewModel) -> None:
        self._view_model = view_model

    def build_view_model(self, **_kwargs: object) -> FinancialAnalysisViewModel:
        return self._view_model


def _snapshot() -> FinancialAnalysisSnapshot:
    cutoff = date(2026, 7, 31)
    selected = FinancialEntity("7", "Coopealianza R.L.", "Cooperativas")
    peer = FinancialEntity("8", "Entidad B", "Cooperativas")
    incomplete = FinancialEntity("9", "Entidad C", "Bancos")
    return FinancialAnalysisSnapshot(
        status="AVAILABLE",
        cutoff_date=cutoff,
        selected_entity=selected,
        entities=(selected, peer, incomplete),
        available_dates=(cutoff,),
        peer_ratings=(
            EntityRatingSummary(
                entity=selected,
                statement_date=cutoff,
                status="COMPLETE",
                score=Decimal("80.250"),
                grade="AA",
                coverage_percent=Decimal("100.00"),
                available_indicators=13,
                total_indicators=13,
            ),
            EntityRatingSummary(
                entity=peer,
                statement_date=cutoff,
                status="COMPLETE",
                score=Decimal("70.000"),
                grade="A",
                coverage_percent=Decimal("100.00"),
                available_indicators=13,
                total_indicators=13,
            ),
            EntityRatingSummary(
                entity=incomplete,
                statement_date=cutoff,
                status="INCOMPLETE",
                score=None,
                grade=None,
                coverage_percent=Decimal("84.62"),
                available_indicators=11,
                total_indicators=13,
            ),
        ),
    )


def test_presenter_builds_ranked_all_entity_rating_rows() -> None:
    view_model = FinancialAnalysisPresenter._from_snapshot(_snapshot())

    rows = view_model.peer_rating_rows
    assert [row.position for row in rows] == ["1", "2", "N/D"]
    assert [row.entity_name for row in rows] == [
        "Coopealianza R.L.",
        "Entidad B",
        "Entidad C",
    ]
    assert rows[0].score == "80.250"
    assert rows[0].grade == "AA"
    assert rows[0].selected is True
    assert rows[2].score == "-"
    assert rows[2].grade == "Sin emitir"
    assert rows[2].coverage == "84.62%"
    assert rows[2].indicators == "11/13"
    assert rows[2].status == "Incompleta"


def test_rating_view_binds_all_entity_table(qt_app) -> None:
    view_model = FinancialAnalysisPresenter._from_snapshot(_snapshot())
    view = FinancialAnalysisView(presenter=_Presenter(view_model))  # type: ignore[arg-type]

    assert view._peer_rating_table.rowCount() == 3
    assert view._peer_rating_table.item(0, 0).text() == "1"
    assert view._peer_rating_table.item(0, 1).text() == "Coopealianza R.L."
    assert view._peer_rating_table.item(0, 4).text() == "AA"
    assert view._peer_rating_table.item(2, 0).text() == "N/D"
    assert view._peer_rating_table.item(2, 4).text() == "Sin emitir"
    assert view._peer_rating_summary.text() == "2 emitidas · 3 entidades"
