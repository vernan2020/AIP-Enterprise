from __future__ import annotations

from PySide6.QtWidgets import QWidget

from aip.ui.shell.workspace import Workspace


class CloseTrackingPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.close_calls = 0

    def closeEvent(self, event) -> None:  # noqa: N802
        self.close_calls += 1
        super().closeEvent(event)


def test_clicking_tab_x_calls_page_close_and_removes_tab(qt_app) -> None:
    workspace = Workspace()
    page = CloseTrackingPage()
    workspace.add_tab("Riesgo de Precio", page)

    workspace.tabCloseRequested.emit(0)

    assert page.close_calls == 1
    assert workspace.count() == 0
    workspace.close()
    workspace.deleteLater()
    qt_app.processEvents()


def test_close_tab_api_uses_page_lifecycle(qt_app) -> None:
    workspace = Workspace()
    page = CloseTrackingPage()
    workspace.add_tab("Riesgo de Precio", page)

    workspace.close_tab("Riesgo de Precio")

    assert page.close_calls == 1
    assert workspace.count() == 0
    workspace.close()
    workspace.deleteLater()
    qt_app.processEvents()
