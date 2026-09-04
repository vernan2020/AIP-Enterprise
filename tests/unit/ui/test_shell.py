from __future__ import annotations

from datetime import timedelta

from PySide6.QtCore import QDate

from aip.ui.shell.main_window import MainWindow
from aip.ui.shell.status_bar import StatusBar
from aip.ui.shell.workspace import Workspace
from aip.ui.widgets.loading_widget import LoadingWidget


def test_shell_components_construct(qt_app) -> None:
    window = MainWindow()
    assert window.windowTitle() == "AIP Enterprise 1.0.0 RC1"

    workspace = Workspace()
    assert workspace.count() == 0

    status_bar = StatusBar()
    assert status_bar.isVisible() is False

    loading = LoadingWidget("Loading")
    assert loading.text() == "Loading"


def test_cutoff_change_updates_factory_and_shared_context(qt_app) -> None:
    window = MainWindow()
    target = window._valuation_context.valuation_date - timedelta(days=1)

    window._handle_qdate_changed(QDate(target.year, target.month, target.day))

    assert window._demo_factory.config.data_cutoff_date == target
    assert window._valuation_context.valuation_date == target
    assert window._date_edit.isEnabled()
    window.close()
