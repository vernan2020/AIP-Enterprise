from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QMainWindow, QSplitter, QTextEdit, QVBoxLayout, QWidget

from aip.ui.modules.executive.views.executive_workspace import ExecutiveWorkspace
from aip.ui.modules.liquidity.views.liquidity_view import LiquidityView
from aip.ui.modules.market.views.market_view import MarketView
from aip.ui.modules.portfolio.views.portfolio_view import PortfolioView
from aip.ui.modules.treasury.views.treasury_view import TreasuryView

from aip.core.version import APP_NAME, APP_VERSION
from aip.ui.navigation.navigation_manager import NavigationManager
from aip.ui.navigation.routes import Route
from aip.ui.services.notification_service import NotificationService
from aip.ui.services.theme_service import ThemeService
from aip.ui.services.ui_event_bus import UIEventBus
from aip.ui.services.window_state_manager import WindowStateManager
from aip.ui.shell.inspector import InspectorPanel
from aip.ui.shell.notification_panel import NotificationPanel
from aip.ui.shell.ribbon import Ribbon
from aip.ui.shell.sidebar import Sidebar
from aip.ui.shell.status_bar import StatusBar
from aip.ui.shell.workspace import Workspace


class MainWindow(QMainWindow):
    """Main desktop shell for AIP Enterprise."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1400, 900)

        self._event_bus = UIEventBus()
        self._notifications = NotificationService()
        self._theme_service = ThemeService()
        self._navigation = NavigationManager()
        self._window_state = WindowStateManager()
        self._workspace: Workspace | None = None

        self._setup_navigation()
        self._build_ui()
        self._apply_theme()

    def _setup_navigation(self) -> None:
        routes = [
            Route("home", "Home", "home"),
            Route("portfolio", "Portfolio", "portfolio"),
            Route("market", "Market", "market"),
            Route("liquidity", "Liquidity", "liquidity"),
            Route("treasury", "Treasury", "treasury"),
            Route("executive", "Executive", "executive"),
            Route("reports", "Reports", "reports"),
        ]
        self._navigation.register_many(routes)
        self._navigation.navigate("home")

    def _build_ui(self) -> None:
        self._ribbon = Ribbon()
        self._ribbon.action("Portfolio").triggered.connect(lambda: self.open_workspace("portfolio"))
        self._ribbon.action("Market").triggered.connect(lambda: self.open_workspace("market"))
        self._ribbon.action("Liquidity").triggered.connect(lambda: self.open_workspace("liquidity"))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._ribbon)

        self._sidebar = Sidebar(self._navigation)
        self._workspace = Workspace()
        self._sidebar.set_workspace(self._workspace)
        self._inspector = InspectorPanel()
        self._notifications_panel = NotificationPanel()
        self._status_bar = StatusBar()

        self._workspace.add_tab("Home", QTextEdit("Welcome to AIP Enterprise"))

        self._content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._content_splitter.addWidget(self._sidebar)
        self._content_splitter.addWidget(self._workspace)
        self._content_splitter.setSizes([260, 900])

        self._right_splitter = QSplitter(Qt.Orientation.Vertical)
        self._right_splitter.addWidget(self._inspector)
        self._right_splitter.addWidget(self._notifications_panel)
        self._right_splitter.setSizes([500, 220])

        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter.addWidget(self._content_splitter)
        self._main_splitter.addWidget(self._right_splitter)
        self._main_splitter.setSizes([1100, 300])

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._main_splitter)
        self.setCentralWidget(container)

        self.setStatusBar(self._status_bar)
        self._status_bar.set_message("Ready")

        self._dock_workspace = QDockWidget("Workspace", self)
        self._dock_workspace.setWidget(self._workspace)
        self._dock_workspace.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._dock_workspace)

        self._dock_inspector = QDockWidget("Inspector", self)
        self._dock_inspector.setWidget(self._inspector)
        self._dock_inspector.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._dock_inspector)

        self._dock_notifications = QDockWidget("Notifications", self)
        self._dock_notifications.setWidget(self._notifications_panel)
        self._dock_notifications.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._dock_notifications)

        self._window_state.restore(self)

    def open_workspace(self, route_id: str) -> None:
        if self._workspace is None:
            raise RuntimeError("Workspace not initialized")
        if route_id == "portfolio":
            self._workspace.open_tab("Portfolio", PortfolioView())
            return
        if route_id == "market":
            self._workspace.open_tab("Market", MarketView())
            return
        if route_id == "liquidity":
            self._workspace.open_tab("Liquidity", LiquidityView())
            return
        if route_id == "treasury":
            self._workspace.open_tab("Treasury", TreasuryView())
            return
        if route_id == "executive":
            self._workspace.open_tab("Executive", ExecutiveWorkspace())
            return
        self._workspace.open_tab(route_id.title(), QTextEdit(route_id))

    @property
    def workspace(self) -> Workspace:
        if self._workspace is None:
            raise RuntimeError("Workspace not initialized")
        return self._workspace

    def _apply_theme(self) -> None:
        self._theme_service.apply(self)
