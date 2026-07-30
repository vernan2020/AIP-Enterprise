from __future__ import annotations

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
