from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from aip.ui.modules.treasury.presenters.treasury_presenter import TreasuryPresenter
from aip.ui.modules.treasury.viewmodels.treasury_view_model import TreasuryViewModel
from aip.ui.modules.treasury.widgets.treasury_filter_panel import TreasuryFilterPanel
from aip.ui.modules.treasury.widgets.treasury_status_badge import TreasuryStatusBadge


class TreasuryView(QWidget):
    def __init__(self, presenter: TreasuryPresenter | None = None) -> None:
        super().__init__()
        self._presenter = presenter or TreasuryPresenter()
        self._view_model = self._presenter.build_view_model()
        self._status_badge = TreasuryStatusBadge("Ready")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(TreasuryFilterPanel())

        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(content_splitter, 1)
        layout.addWidget(self._status_badge)

    def refresh(self) -> None:
        self._view_model = self._presenter.refresh()
        self.bind_view_model(self._view_model)

    def bind_view_model(self, view_model: TreasuryViewModel) -> None:
        self._view_model = view_model
        self._status_badge.setText(view_model.status)
        self._status_badge.setToolTip(view_model.error or "")

    def view_model(self) -> TreasuryViewModel:
        return self._view_model
