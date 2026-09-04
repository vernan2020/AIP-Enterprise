from __future__ import annotations

from aip.ui.modules.financial_analysis.viewmodels.financial_analysis_view_model import (
    FinancialAnalysisViewModel,
)
from aip.ui.modules.financial_analysis.views.financial_analysis_view import (
    FinancialAnalysisView,
)
from aip.ui.shell.main_window import MainWindow


class _Presenter:
    def build_view_model(self, **_kwargs) -> FinancialAnalysisViewModel:
        return FinancialAnalysisViewModel()


def test_main_window_opens_financial_analysis_workspace(qt_app) -> None:
    window = MainWindow()
    window.open_workspace("financial_analysis")

    titles = [window.workspace.tabText(index) for index in range(window.workspace.count())]
    assert "Análisis Financiero" in titles


def test_financial_analysis_is_available_in_ribbon_and_sidebar(qt_app) -> None:
    window = MainWindow()

    assert window._ribbon.action("Análisis Financiero").text() == "Análisis Financiero"
    labels = [
        window._sidebar._tree.item(index).text() for index in range(window._sidebar._tree.count())
    ]
    assert "Análisis Financiero" in labels


def test_financial_analysis_exposes_methodology_rating_tab(qt_app) -> None:
    view = FinancialAnalysisView(presenter=_Presenter())  # type: ignore[arg-type]

    titles = [view._tabs.tabText(index) for index in range(view._tabs.count())]

    assert "Calificación" in titles
    assert view._rating_heading.text() == "Calificación 08ME14-01 sobre datos SUGEF"
    assert view._rating_methodology.text() == "Metodología: 08ME14-01"
    assert view._rating_grade.text() == "Sin emitir"
    assert "Calificación oficial" not in view._rating_heading.text()
    assert view._cutoff.text().startswith("Corte SUGEF:")
    assert "corte general de AIP" in view._cutoff.toolTip()
