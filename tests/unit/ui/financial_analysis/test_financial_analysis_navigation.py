from __future__ import annotations

from aip.ui.shell.main_window import MainWindow


def test_main_window_opens_financial_analysis_workspace(qt_app) -> None:
    window = MainWindow()
    window.open_workspace("financial_analysis")

    titles = [window.workspace.tabText(index) for index in range(window.workspace.count())]
    assert "Análisis Financiero" in titles


def test_financial_analysis_is_available_in_ribbon_and_sidebar(qt_app) -> None:
    window = MainWindow()

    assert window._ribbon.action("Análisis Financiero").text() == "Análisis Financiero"
    labels = [window._sidebar._tree.item(index).text() for index in range(window._sidebar._tree.count())]
    assert "Análisis Financiero" in labels
