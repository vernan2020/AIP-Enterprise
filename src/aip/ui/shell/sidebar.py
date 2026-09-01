from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLineEdit, QListWidget, QVBoxLayout, QWidget

from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.ui.navigation.navigation_manager import NavigationManager
from aip.ui.shell.workspace import Workspace


class Sidebar(QWidget):
    """Passive module navigator for AIP Enterprise.

    The sidebar deliberately does not construct presenters, providers or
    workspaces.  It only emits a stable route id; MainWindow owns all view
    construction so every module receives the same application factory and
    dependency container.
    """

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
        self.setMinimumWidth(140)
        self.setMaximumWidth(175)
        self._navigation = navigation
        # Retained only for backwards constructor compatibility.  It is never
        # used to create child modules.
        self._application_factory = application_factory
        self._workspace: Workspace | None = None
        self._route_by_label = dict(self._ITEMS)
        self._build_ui()

    def set_workspace(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Buscar módulo")
        self._search.textChanged.connect(self._apply_filter)

        self._tree = QListWidget()
        self._tree.addItems([label for label, _route in self._ITEMS])
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.itemDoubleClicked.connect(self._on_item_clicked)

        layout.addWidget(self._search)
        layout.addWidget(self._tree)

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
            # Navigation history is ancillary; workspace activation must still
            # work if a route manager implementation is more restrictive.
            pass
        self.route_requested.emit(route_id)
