from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLineEdit, QListWidget, QVBoxLayout, QWidget

from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.ui.navigation.navigation_manager import NavigationManager
from aip.ui.shell.workspace import Workspace


class Sidebar(QWidget):
    """Passive module navigator for AIP Enterprise."""

    route_requested = Signal(str)

    _ITEMS = (
        ("Inicio", "home"),
        ("Ejecutivo", "executive"),
        ("Portafolio", "portfolio"),
        ("Mercado", "market"),
        ("Riesgo de Precio", "price_risk"),
        ("Macro Intelligence", "macro_intelligence"),
        ("Liquidez", "liquidity"),
        ("Tesorería", "treasury"),
        ("Reportes", "reports"),
    )

    def __init__(
        self,
        navigation: NavigationManager,
        application_factory: DemoApplicationFactory | None = None,
    ) -> None:
        super().__init__()
        self.setObjectName("navigationSidebar")
        self.setMinimumWidth(150)
        self.setMaximumWidth(185)
        self._navigation = navigation
        self._application_factory = application_factory
        self._workspace: Workspace | None = None
        self._route_by_label = dict(self._ITEMS)
        self._build_ui()
        self._apply_local_style()

    def set_workspace(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(7, 9, 7, 9)
        layout.setSpacing(8)

        self._search = QLineEdit()
        self._search.setObjectName("moduleSearch")
        self._search.setPlaceholderText("Buscar módulo...")
        self._search.textChanged.connect(self._apply_filter)

        self._tree = QListWidget()
        self._tree.setObjectName("moduleList")
        self._tree.addItems([label for label, _route in self._ITEMS])
        self._tree.setSpacing(2)
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.itemDoubleClicked.connect(self._on_item_clicked)

        layout.addWidget(self._search)
        layout.addWidget(self._tree, 1)

    def _apply_local_style(self) -> None:
        self.setStyleSheet(
            "QWidget#navigationSidebar {background:#F6F8FA; border-right:1px solid #D7E0E8;}"
            "QLineEdit#moduleSearch {background:#FFFFFF; border:1px solid #CDD8E1; border-radius:6px; "
            "padding:7px 8px; color:#243746;}"
            "QLineEdit#moduleSearch:focus {border-color:#6F9ABA;}"
            "QListWidget#moduleList {background:transparent; border:none; outline:none;}"
            "QListWidget#moduleList::item {padding:8px 9px; margin:1px 0; border-radius:6px; color:#354B5E;}"
            "QListWidget#moduleList::item:hover {background:#E8F0F6; color:#174E78;}"
            "QListWidget#moduleList::item:selected {background:#DCE9F5; color:#174E78; "
            "font-weight:700; border-left:3px solid #1F5A8A;}"
        )

    def _apply_filter(self, value: str) -> None:
        needle = value.strip().casefold()
        for index in range(self._tree.count()):
            item = self._tree.item(index)
            item.setHidden(bool(needle) and needle not in item.text().casefold())

    def _on_item_clicked(self, item) -> None:
        route_id = self._route_by_label.get(item.text())
        if route_id is None:
            return
        try:
            self._navigation.navigate(route_id)
        except Exception:
            pass
        self.route_requested.emit(route_id)
