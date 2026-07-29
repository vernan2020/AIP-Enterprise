from __future__ import annotations

from PySide6.QtWidgets import QLineEdit, QListWidget, QVBoxLayout, QWidget

from aip.ui.modules.portfolio.views.portfolio_view import PortfolioView
from aip.ui.navigation.navigation_manager import NavigationManager
from aip.ui.shell.workspace import Workspace


class Sidebar(QWidget):
    """Navigation, favorites, and recent modules panel."""

    def __init__(self, navigation: NavigationManager) -> None:
        super().__init__()
        self._navigation = navigation
        self._workspace: Workspace | None = None
        self._build_ui()

    def set_workspace(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search")
        self._tree = QListWidget()
        self._tree.addItems(["Home", "Portfolio", "Market", "Liquidity", "Treasury", "Reports"])
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._search)
        layout.addWidget(self._tree)

    def _on_item_double_clicked(self, item) -> None:
        if self._workspace is None:
            return
        route_id = item.text().lower()
        if route_id == "portfolio":
            self._workspace.open_tab("Portfolio", PortfolioView())
        else:
            self._workspace.open_tab(item.text(), QWidget())
