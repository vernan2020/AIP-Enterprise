from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QDialog, QDockWidget, QLabel, QMainWindow, QMessageBox, QSplitter, QTextEdit, QVBoxLayout, QWidget

from aip.core.version import APP_DISPLAY_NAME, APP_DISPLAY_VERSION
from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.product.demo.configuration.environment_loader import EnvironmentLoader
from aip.ui.dialogs.about_dialog import AboutDialog
from aip.ui.modules.executive.views.executive_workspace import ExecutiveWorkspace
from aip.ui.modules.liquidity.views.liquidity_view import LiquidityView
from aip.ui.modules.market.views.market_view import MarketView
from aip.ui.modules.portfolio.presenters.portfolio_presenter import PortfolioPresenter
from aip.ui.modules.portfolio.views.portfolio_view import PortfolioView
from aip.ui.modules.treasury.views.treasury_view import TreasuryView
from aip.ui.navigation.navigation_manager import NavigationManager
from aip.ui.navigation.routes import Route
from aip.ui.services.diagnostic_service import DiagnosticMetricsStore, ProductionReadinessService
from aip.ui.services.export_service import TableExportService
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
from aip.ui.widgets.health_center import HealthCenterWidget
from aip.ui.widgets.log_viewer import LogViewerDialog
from aip.ui.widgets.settings_center import SettingsCenterDialog


class MainWindow(QMainWindow):
    """Main desktop shell for AIP Enterprise."""

    def __init__(self) -> None:
        if QApplication.instance() is None:
            QApplication([])
        super().__init__()
        self.setWindowTitle(APP_DISPLAY_VERSION)
        self.resize(1400, 900)

        self._event_bus = UIEventBus()
        self._notifications = NotificationService()
        self._theme_service = ThemeService()
        self._navigation = NavigationManager()
        self._window_state = WindowStateManager()
        self._config = EnvironmentLoader().load()
        self._demo_factory = DemoApplicationFactory(self._config)
        self._workspace: Workspace | None = None
        self._system_status_text: QTextEdit | None = None
        self._diagnostic_mode = False
        self._diagnostic_metrics = DiagnosticMetricsStore()
        self._diagnostic_service = ProductionReadinessService()
        self._export_service = TableExportService()

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
        self._ribbon.action("Treasury").triggered.connect(lambda: self.open_workspace("treasury"))
        self._ribbon.action("Executive").triggered.connect(lambda: self.open_workspace("executive"))
        self._ribbon.action("Refresh All").triggered.connect(self._handle_refresh_all)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._ribbon)

        self._add_operational_menu_actions()

        self._sidebar = Sidebar(self._navigation, self._demo_factory)
        self._workspace = Workspace()
        self._sidebar.set_workspace(self._workspace)
        self._inspector = InspectorPanel()
        self._notifications_panel = NotificationPanel()
        self._status_bar = StatusBar()
        execution_mode = self._demo_factory.config.execution_mode
        banner_label = "CONFIGURED MODE" if execution_mode == "CONFIGURED" else "DEMO MODE"
        header_name = "AIP Enterprise — CONFIGURED MODE" if execution_mode == "CONFIGURED" else APP_DISPLAY_NAME
        self._demo_banner = QLabel(f"{header_name}\n{banner_label} • Executive Workspace")
        self._demo_banner.setStyleSheet("background: #1f4e79; color: white; padding: 4px 8px; font-weight: bold;")
        self._demo_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._workspace.add_tab("Home", QTextEdit("Welcome to AIP Enterprise Demo 0.9"))
        self._workspace.add_tab("Executive", ExecutiveWorkspace())

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
        layout.addWidget(self._demo_banner)
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

        self._system_status_text = QTextEdit()
        self._system_status_text.setReadOnly(True)
        self._system_status_text.setMinimumHeight(140)
        self._dock_status = QDockWidget("System Status", self)
        self._dock_status.setWidget(self._system_status_text)
        self._dock_status.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._dock_status)

        self._window_state.restore(self)
        self._refresh_status_panel()
        self.open_workspace("executive")

    def _add_operational_menu_actions(self) -> None:
        menu_bar = self.menuBar()
        view_menu = menu_bar.addMenu("View")
        health_action = QAction("Health Center", self)
        health_action.triggered.connect(self.show_health_center)
        view_menu.addAction(health_action)

        settings_action = QAction("Settings Center", self)
        settings_action.triggered.connect(self.show_settings_center)
        view_menu.addAction(settings_action)

        logs_action = QAction("Log Viewer", self)
        logs_action.triggered.connect(self.show_log_viewer)
        view_menu.addAction(logs_action)

        help_menu = menu_bar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def toggle_diagnostic_mode(self, enabled: bool) -> None:
        self._diagnostic_mode = enabled
        self._diagnostic_metrics.diagnostic_mode = enabled
        self._refresh_status_panel()

    def diagnostic_snapshot(self) -> dict[str, Any]:
        snapshot = self._diagnostic_service.diagnostic_snapshot()
        snapshot.update(
            {
                "startup_time_ms": self._diagnostic_metrics.startup_time_ms,
                "initial_load_time_ms": self._diagnostic_metrics.initial_load_time_ms,
                "refresh_all_duration_ms": self._diagnostic_metrics.refresh_all_duration_ms,
                "workspace_switch_time_ms": self._diagnostic_metrics.workspace_switch_time_ms,
                "memory_after_startup_mb": self._diagnostic_metrics.memory_after_startup_mb,
                "memory_after_refresh_mb": self._diagnostic_metrics.memory_after_refresh_mb,
                "last_refresh_duration_ms": self._diagnostic_metrics.last_refresh_duration_ms,
                "diagnostic_mode": self._diagnostic_mode,
            }
        )
        return snapshot

    def show_health_center(self) -> None:
        self._show_dialog("Health Center", HealthCenterWidget())

    def show_settings_center(self) -> None:
        self._show_dialog("Settings Center", SettingsCenterDialog())

    def show_log_viewer(self) -> None:
        self._show_dialog("Log Viewer", LogViewerDialog())

    def show_about(self) -> None:
        dialog = AboutDialog()
        dialog.exec()

    def export_current_workspace_table(self, path: str | None = None, *, export_format: str = "csv") -> str:
        if self._workspace is None:
            raise RuntimeError("Workspace not initialized")

        current_widget = self._workspace.currentWidget()
        if current_widget is None:
            raise RuntimeError("No active workspace tab")

        headers: list[str] = []
        rows: list[list[object]] = []
        if hasattr(current_widget, "columnCount") and hasattr(current_widget, "rowCount"):
            headers = [current_widget.horizontalHeaderItem(index).text() if current_widget.horizontalHeaderItem(index) is not None else str(index) for index in range(current_widget.columnCount())]
            for row_index in range(current_widget.rowCount()):
                row: list[object] = []
                for column_index in range(current_widget.columnCount()):
                    item = current_widget.item(row_index, column_index)
                    row.append(item.text() if item is not None else "")
                rows.append(row)
        elif hasattr(current_widget, "table") and hasattr(current_widget.table, "columnCount"):
            table = current_widget.table
            headers = [table.horizontalHeaderItem(index).text() if table.horizontalHeaderItem(index) is not None else str(index) for index in range(table.columnCount())]
            for row_index in range(table.rowCount()):
                row = []
                for column_index in range(table.columnCount()):
                    item = table.item(row_index, column_index)
                    row.append(item.text() if item is not None else "")
                rows.append(row)
        else:
            raise RuntimeError("Active workspace tab does not expose a table")

        return self._export_service.export_records(path or "workspace-export", headers=headers, rows=rows, export_format=export_format)

    def _show_dialog(self, title: str, widget: QWidget) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        layout = QVBoxLayout(dialog)
        layout.addWidget(widget)
        dialog.resize(700, 500)
        dialog.exec()

    def open_workspace(self, route_id: str) -> None:
        if self._workspace is None:
            raise RuntimeError("Workspace not initialized")
        if route_id == "portfolio":
            self._workspace.open_tab("Portfolio", PortfolioView(presenter=PortfolioPresenter(self._demo_factory)))
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

    def _handle_refresh_all(self) -> None:
        try:
            self._status_bar.set_message("Refresh All started")
            workflow = self._demo_factory.refresh_all_workflow()
            result = workflow.execute("corr-demo-refresh")
            self._refresh_status_panel()
            workspace = self._workspace
            if workspace is None:
                return
            for index in range(workspace.count()):
                widget = workspace.widget(index)
                if widget is not None and hasattr(widget, "refresh"):
                    widget.refresh()
            self._status_bar.set_message(
                f"Refresh All completed · {result['valuation_date']} · {result['correlation_id']}"
            )
            self._refresh_status_panel()
        except Exception as exc:  # pragma: no cover - defensive UI handling
            self._status_bar.set_message("Refresh All failed")
            QMessageBox.critical(self, "Refresh failed", str(exc))

    def refresh_all(self) -> dict[str, object]:
        workflow = self._demo_factory.refresh_all_workflow()
        result = workflow.execute("corr-demo-refresh")
        self._refresh_status_panel()
        workspace = self._workspace
        if workspace is None:
            return {
                "status": "completed",
                "correlation_id": result["correlation_id"],
                "valuation_date": result["valuation_date"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        for index in range(workspace.count()):
            widget = workspace.widget(index)
            if widget is not None and hasattr(widget, "refresh"):
                widget.refresh()
        self._status_bar.set_message(
            f"Refresh All completed · {result['valuation_date']} · {result['correlation_id']}"
        )
        return {
            "status": "completed",
            "correlation_id": result["correlation_id"],
            "valuation_date": result["valuation_date"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _refresh_status_panel(self) -> None:
        if self._system_status_text is None:
            return
        status = self._demo_factory.build_system_status()
        component_states = {
            "Application": status.component_details.get("mode", status.execution_mode),
            "Integration Hub": status.source_states.get("integration_hub", "HEALTHY"),
            "SQL Server": status.source_states.get("sql_server", "UNKNOWN"),
            "Folder Watch": status.source_states.get("folder_watch", "UNKNOWN"),
            "BCCR": status.source_states.get("bccr", "UNKNOWN"),
            "Data Quality": status.source_states.get("data_quality", "HEALTHY"),
            "Scheduler": status.source_states.get("scheduler", "HEALTHY"),
            "Notifications": status.source_states.get("notifications", "HEALTHY"),
            "Observability": status.source_states.get("observability", "HEALTHY"),
            "Security": status.source_states.get("security", "HEALTHY"),
            "Reporting": status.source_states.get("reporting", "HEALTHY"),
        }
        lines = [
            f"Environment: {status.environment}",
            f"Execution Mode: {status.execution_mode}",
            f"Demo Mode: {self._demo_factory.config.demo_mode_enabled}",
            f"Configured Mode: {status.execution_mode == 'CONFIGURED'}",
            "Demo Badge: ABSENT" if status.execution_mode == "CONFIGURED" else "Demo Badge: PRESENT",
            f"Diagnostic Mode: {'ON' if self._diagnostic_mode else 'OFF'}",
            *[f"{name}: {state}" for name, state in component_states.items()],
        ]
        self._system_status_text.setPlainText("\n".join(lines))

    @property
    def workspace(self) -> Workspace:
        if self._workspace is None:
            raise RuntimeError("Workspace not initialized")
        return self._workspace

    def _apply_theme(self) -> None:
        self._theme_service.apply(self)
