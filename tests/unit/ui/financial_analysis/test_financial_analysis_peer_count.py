from __future__ import annotations

from decimal import Decimal

from aip.ui.modules.financial_analysis.presenters.financial_analysis_presenter import (
    FinancialAnalysisPresenter,
)
from aip.ui.modules.financial_analysis.viewmodels.financial_analysis_view_model import (
    FinancialAnalysisViewModel,
    RatingIndicatorRow,
)
from aip.ui.modules.financial_analysis.views.financial_analysis_view import (
    FinancialAnalysisView,
)


class _Presenter:
    def build_view_model(self, **_kwargs) -> FinancialAnalysisViewModel:
        return FinancialAnalysisViewModel(
            rating_indicators=(
                RatingIndicatorRow(
                    indicator="ROE",
                    dimension="Rentabilidad",
                    value="5.735%",
                    peer_count="2",
                    percentile_15="-",
                    midpoint="-",
                    percentile_85="-",
                    direction="Mayor es mejor",
                    level="Sin datos",
                    contribution="-",
                    source_account="ROE · SUGEF",
                ),
            )
        )


def test_rating_table_exposes_comparable_peer_count(qt_app) -> None:
    view = FinancialAnalysisView(presenter=_Presenter())  # type: ignore[arg-type]

    assert view._rating_indicator_table.horizontalHeaderItem(3).text() == "Pares"
    assert view._rating_indicator_table.item(0, 3).text() == "2"


def test_statement_value_formats_only_true_binary_methodology_indicators() -> None:
    assert (
        FinancialAnalysisPresenter._statement_value(
            Decimal("0.035"),
            "INDICATORS",
            "EQUITY_COMMITMENT",
        )
        == "3.500%"
    )
    assert (
        FinancialAnalysisPresenter._statement_value(
            Decimal("1"),
            "INDICATORS",
            "STATE_GUARANTEE",
        )
        == "Sí"
    )
