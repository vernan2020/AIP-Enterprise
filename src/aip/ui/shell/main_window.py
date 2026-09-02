from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QDateEdit,
    QDialog,
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from aip.core.version import APP_DISPLAY_NAME, APP_DISPLAY_VERSION
from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.product.demo.configuration.environment_loader import EnvironmentLoader
from aip.ui.dialogs.about_dialog import AboutDialog
from aip.ui.modules.executive.presenters.executive_presenter import ExecutivePresenter
from aip.ui.modules.executive.views.executive_workspace import ExecutiveWorkspace
from aip.ui.modules.home.home_workspace import HomeWorkspace
from aip.ui.modules.liquidity.presenters.liquidity_presenter import LiquidityPresenter
from aip.ui.modules.liquidity.views.liquidity_view import LiquidityView
from aip.ui.modules.market.presenters.market_presenter import MarketPresenter
from aip.ui.modules.market.views.market_view import MarketView
from aip.ui.modules.portfolio.presenters.portfolio_presenter import PortfolioPresenter
from aip.ui.modules.portfolio.views.portfolio_view import PortfolioView
from aip.ui.modules.treasury.presenters.treasury_presenter import TreasuryPresenter
from aip.ui.modules.treasury.views.treasury_view import TreasuryView
from aip.ui.navigation.navigation_manager import NavigationManager
from aip.ui.navigation.routes import Route
from aip.ui.services.diagnostic_service import (
    DiagnosticMetricsStore,
    ProductionReadinessService,
)
from aip.ui.services.export_service import TableExportService
from aip.ui.services.notification_service import NotificationService
from aip.ui.services.theme_service import ThemeService
from aip.ui.services.ui_event_bus import UIEventBus
from aip.ui.services.valuation_context import ValuationContext
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
    """Institutional desktop shell for AIP Enterprise.

    ``demo_factory`` is a legacy parameter name retained for API compatibility.
    In CONFIGURED mode it is the already composed institutional application
    factory created during bootstrap. The shell never creates a second
    container when that factory is supplied.
    """

    def __init__(
        self,
        demo_factory: DemoApplicationFactory | None = None,
    ) -> None:
        if QApplication.instance() is None:
            QApplication([])
        super().__init__()

        self.setWindowTitle(APP_DISPLAY_VERSION)
        self.resize(1600, 900)

        self._event_bus = UIEventBus()
        self._notifications = NotificationService()
        self._theme_service = ThemeService()
        self._navigation = NavigationManager()
        self._window_state = WindowStateManager()

        if demo_factory is None:
            loader = EnvironmentLoader()
            config = loader.load()
            demo_factory = DemoApplicationFactory(
                config,
                source_config=loader.load_source_config(),
            )

        self._demo_factory = demo_factory
        self._config = self._demo_factory.config
        self._valuation_context = self._build_valuation_context()

        self._workspace: Workspace | None = None
        self._system_status_text: QTextEdit | None = None
        self._diagnostic_mode = False
        self._diagnostic_metrics = DiagnosticMetricsStore()
        try:
            self._diagnostic_service = ProductionReadinessService(
                application_factory=self._demo_factory
            )
        except TypeError:
            self._diagnostic_service = ProductionReadinessService()
        self._export_service = TableExportService()
        self._inspector_action: QAction | None = None

        self._setup_navigation()
        self._build_ui()
        self._apply_theme()

    def _build_valuation_context(self) -> ValuationContext:
        source_context = None
        try:
            from aip.product.configured.context.valuation_date_context import (
                ValuationDateContext as ProductValuationDateContext,
            )

            source_context = self._demo_factory.container.resolve(ProductValuationDateContext)
        except Exception:
            source_context = None
        try:
            return ValuationContext(
                self._config.data_cutoff_date,
                source_context=source_context,
            )
        except TypeError:
            return ValuationContext(self._config.data_cutoff_date)

    def _setup_navigation(self) -> None:
        routes = [
            Route("home", "Inicio", "home"),
            Route("executive", "Ejecutivo", "executive"),
            Route("portfolio", "Portafolio", "portfolio"),
            Route("market", "Mercado", "market"),
            Route("price_risk", "Riesgo de Precio", "risk"),
            Route("macro_intelligence", "Macro Intelligence", "macro"),
            Route("liquidity", "Liquidez", "liquidity"),
            Route("treasury", "Tesorería", "treasury"),
            Route("reports", "Reportes", "reports"),
        ]
        self._navigation.register_many(routes)
        self._navigation.navigate("home")

    def _build_ui(self) -> None:
        self._ribbon = Ribbon()
        ribbon_routes = {
            "Home": "home",
            "Executive": "executive",
            "Portfolio": "portfolio",
            "Market": "market",
            "Price Risk": "price_risk",
            "Macro Intelligence": "macro_intelligence",
            "Liquidity": "liquidity",
            "Treasury": "treasury",
            "Reports": "reports",
        }
        for label, route_id in ribbon_routes.items():
            self._ribbon.action(label).triggered.connect(
                lambda _checked=False, route=route_id: self.open_workspace(route)
            )
        self._ribbon.action("Refresh All").triggered.connect(self._handle_refresh_all)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._ribbon)
        self._add_operational_menu_actions()

        self._sidebar = Sidebar(self._navigation, self._demo_factory)
        self._workspace = Workspace()
        self._sidebar.set_workspace(self._workspace)
        self._sidebar.route_requested.connect(self.open_workspace)

        self._inspector = InspectorPanel()
        self._notifications_panel = NotificationPanel()
        self._status_bar = StatusBar()
        self.setStatusBar(self._status_bar)
        self._header = self._build_header()

        self._workspace.add_tab("Inicio", self._create_home_workspace())

        self._content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._content_splitter.setObjectName("contentSplitter")
        self._content_splitter.setChildrenCollapsible(False)
        self._content_splitter.addWidget(self._sidebar)
        self._content_splitter.addWidget(self._workspace)
        self._content_splitter.setStretchFactor(0, 0)
        self._content_splitter.setStretchFactor(1, 1)
        self._content_splitter.setSizes([168, 1432])

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._header)
        layout.addWidget(self._content_splitter, 1)
        self.setCentralWidget(container)

        self._dock_inspector = QDockWidget("Inspector", self)
        self._dock_inspector.setObjectName("contextInspectorDock")
        self._dock_inspector.setWidget(self._inspector)
        self._dock_inspector.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea,
            self._dock_inspector,
        )
        self._dock_inspector.hide()

        self._dock_notifications = QDockWidget("Notifications", self)
        self._dock_notifications.setWidget(self._notifications_panel)
        self._dock_notifications.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea,
            self._dock_notifications,
        )
        self._dock_notifications.hide()

        self._system_status_text = QTextEdit()
        self._system_status_text.setReadOnly(True)
        self._dock_status = QDockWidget("System Status", self)
        self._dock_status.setWidget(self._system_status_text)
        self._dock_status.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea,
            self._dock_status,
        )
        self._dock_status.hide()

        self._window_state.restore(self)
        self._status_bar.set_message("SISTEMA LISTO")
        self._refresh_status_panel()
        self.open_workspace("executive")

    def _create_home_workspace(self) -> HomeWorkspace:
        home = HomeWorkspace(self._demo_factory)
        home.route_requested.connect(self.open_workspace)
        return home

    def _build_header(self) -> QWidget:
        frame = QFrame(self)
        frame.setObjectName("institutionalHeader")
        frame.setMinimumHeight(58)
        frame.setStyleSheet(
            "QFrame#institutionalHeader {background:#173F63; border:none;}"
            "QFrame#institutionalHeader QLabel {background:transparent; border:none; color:#FFFFFF;}"
            "QLabel#headerMode {background:#245A84; border:1px solid #4E7EA2; border-radius:10px; "
            "padding:4px 9px; color:#EAF3FA; font-size:9px; font-weight:700;}"
            "QLabel#headerStatus {background:#246B5A; border:1px solid #4A907F; border-radius:10px; "
            "padding:4px 9px; color:#FFFFFF; font-size:9px; font-weight:700;}"
            "QDateEdit {min-width:112px; padding:5px 8px; background:#FFFFFF; color:#17324D; "
            "border:1px solid #B9CAD7; border-radius:5px;}"
        )
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setSpacing(10)
        execution_mode = self._config.execution_mode

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title = QLabel("AIP HYBRID" if execution_mode == "CONFIGURED" else APP_DISPLAY_NAME)
        title.setStyleSheet(
            "font-size:15px; font-weight:800; letter-spacing:0.7px; background:transparent;"
        )
        subtitle = QLabel("FINANCIAL INTELLIGENCE PLATFORM")
        subtitle.setStyleSheet(
            "font-size:8px; color:#BFD3E2; letter-spacing:1px; background:transparent;"
        )
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box)

        mode = QLabel(
            "MODO CONFIGURADO" if execution_mode == "CONFIGURED" else "MODO DEMO"
        )
        mode.setObjectName("headerMode")
        layout.addWidget(mode)
        layout.addStretch(1)

        self._header_status = QLabel("SISTEMA LISTO")
        self._header_status.setObjectName("headerStatus")
        layout.addWidget(self._header_status)

        cutoff_label = QLabel("CORTE")
        cutoff_label.setStyleSheet(
            "font-size:8px; color:#BFD3E2; font-weight:700; background:transparent;"
        )
        layout.addWidget(cutoff_label)
        self._date_edit = QDateEdit()
        self._date_edit.setCalendarPopup(True)
        active = self._valuation_context.valuation_date
        self._date_edit.setDate(QDate(active.year, active.month, active.day))
        self._date_edit.setDisplayFormat("dd/MM/yyyy")
        self._date_edit.dateChanged.connect(self._handle_qdate_changed)
        layout.addWidget(self._date_edit)
        return frame

    def open_workspace(self, route_id: str) -> None:
        if self._workspace is None:
            raise RuntimeError("Workspace not initialized")
        try:
            widget, title = self._build_workspace_widget(route_id)
            self._workspace.open_tab(title, widget)
        except Exception as exc:
            self._status_bar.set_message(f"No se pudo abrir {route_id}")
            QMessageBox.critical(
                self,
                "Módulo no disponible",
                f"No fue posible abrir {route_id}.\n\nDetalle:\n{exc}",
            )

    def _build_workspace_widget(self, route_id: str) -> tuple[QWidget, str]:
        if route_id == "home":
            return (self._create_home_workspace(), "Inicio")
        if route_id == "executive":
            return (
                ExecutiveWorkspace(presenter=ExecutivePresenter(self._demo_factory)),
                "Ejecutivo",
            )
        if route_id == "portfolio":
            return (
                PortfolioView(presenter=PortfolioPresenter(self._demo_factory)),
                "Portafolio",
            )
        if route_id == "market":
            return (MarketView(presenter=MarketPresenter(self._demo_factory)), "Mercado")
        if route_id == "price_risk":
            from aip.ui.modules.price_risk.presenters.price_risk_presenter import (
                PriceRiskPresenter,
            )
            from aip.ui.modules.price_risk.views.price_risk_view import PriceRiskView

            return (
                PriceRiskView(presenter=PriceRiskPresenter(self._demo_factory)),
                "Riesgo de Precio",
            )
        if route_id == "macro_intelligence":
            from aip.ui.modules.macro_intelligence.views.macro_intelligence_view import (
                MacroIntelligenceView,
            )

            return (
                MacroIntelligenceView(application_factory=self._demo_factory),
                "Macro Intelligence",
            )
        if route_id == "liquidity":
            return (
                LiquidityView(presenter=LiquidityPresenter(self._demo_factory)),
                "Liquidez",
            )
        if route_id == "treasury":
            return (
                TreasuryView(presenter=TreasuryPresenter(self._demo_factory)),
                "Tesorería",
            )
        if route_id == "reports":
            return (QTextEdit("Reportes institucionales"), "Reportes")
        return (QTextEdit(route_id), route_id.title())

    def _handle_qdate_changed(self, value: QDate) -> None:
        self._handle_valuation_date_changed(date(value.year(), value.month(), value.day()))

    def _handle_valuation_date_changed(self, value: date) -> None:
        previous = self._valuation_context.valuation_date
        if value == previous:
            return
        self._date_edit.setEnabled(False)
        self._status_bar.set_message(f"Cambiando fecha de corte a {value.strftime('%d/%m/%Y')}...")
        self._header_status.setText("ACTUALIZANDO")
        QApplication.processEvents()
        try:
            self._demo_factory.set_data_cutoff_date(value)
            self._valuation_context.set_valuation_date(value)
            self._refresh_open_workspaces()
            self._refresh_status_panel()
            self._status_bar.set_message(f"Fecha de corte activa: {value.strftime('%d/%m/%Y')}")
            self._header_status.setText("SISTEMA LISTO")
        except Exception as exc:
            self._date_edit.blockSignals(True)
            self._date_edit.setDate(QDate(previous.year, previous.month, previous.day))
            self._date_edit.blockSignals(False)
            self._header_status.setText("REVISAR")
            QMessageBox.critical(
                self,
                "Cambio de fecha no completado",
                f"No fue posible cargar el corte {value:%d/%m/%Y}.\n\n{exc}",
            )
        finally:
            self._date_edit.setEnabled(True)

    def _refresh_open_workspaces(self) -> int:
        workspace = self._workspace
        if workspace is None:
            return 0
        refreshed = 0
        for index in range(workspace.count()):
            widget = workspace.widget(index)
            refresh_method = getattr(widget, "refresh", None)
            if callable(refresh_method):
                refresh_method()
                refreshed += 1
        return refreshed

    def _handle_refresh_all(self) -> None:
        try:
            self._status_bar.set_message("Actualizando fuentes institucionales...")
            self._header_status.setText("ACTUALIZANDO")
            workflow = self._demo_factory.refresh_all_workflow()
            result = workflow.execute("corr-refresh-all")
            refreshed = self._refresh_open_workspaces()
            self._refresh_status_panel()
            self._status_bar.set_message(
                f"Actualización completada · {result['valuation_date']} · {refreshed} módulos"
            )
            self._header_status.setText("SISTEMA LISTO")
        except Exception as exc:
            self._status_bar.set_message("Actualización fallida")
            self._header_status.setText("REVISAR")
            QMessageBox.critical(self, "Refresh failed", str(exc))

    def refresh_all(self) -> dict[str, object]:
        workflow = self._demo_factory.refresh_all_workflow()
        result = workflow.execute("corr-refresh-all")
        refreshed = self._refresh_open_workspaces()
        self._refresh_status_panel()
        return {
            "status": "completed",
            "correlation_id": result["correlation_id"],
            "valuation_date": result["valuation_date"],
            "refreshed_workspaces": refreshed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _refresh_status_panel(self) -> None:
        if self._system_status_text is None:
            return
        try:
            status = self._demo_factory.build_system_status()
            source_states = status.source_states
            lines = [
                f"Environment: {status.environment}",
                f"Execution Mode: {status.execution_mode}",
                f"Demo Mode: {self._demo_factory.config.demo_mode_enabled}",
                f"Valuation Date: {self._valuation_context.valuation_date.isoformat()}",
                *[f"{name}: {state}" for name, state in sorted(source_states.items())],
            ]
        except Exception as exc:
            lines = [f"System status unavailable: {exc}"]
        self._system_status_text.setPlainText("\n".join(lines))

    def toggle_diagnostic_mode(self, enabled: bool) -> None:
        self._diagnostic_mode = enabled
        self._diagnostic_metrics.diagnostic_mode = enabled
        self._refresh_status_panel()

    def diagnostic_snapshot(self) -> dict[str, Any]:
        snapshot = self._diagnostic_service.diagnostic_snapshot()
        snapshot.update(
            {
                "diagnostic_mode": self._diagnostic_mode,
                "valuation_date": self._valuation_context.valuation_date.isoformat(),
                "execution_mode": self._config.execution_mode,
            }
        )
        return snapshot

    def _add_operational_menu_actions(self) -> None:
        view_menu = self.menuBar().addMenu("View")
        inspector_action = QAction("Inspector", self)
        inspector_action.setCheckable(True)
        inspector_action.triggered.connect(self._toggle_inspector)
        view_menu.addAction(inspector_action)
        self._inspector_action = inspector_action
        view_menu.addSeparator()
        for label, handler in (
            ("Health Center", self.show_health_center),
            ("Settings Center", self.show_settings_center),
            ("Log Viewer", self.show_log_viewer),
        ):
            action = QAction(label, self)
            action.triggered.connect(handler)
            view_menu.addAction(action)
        help_menu = self.menuBar().addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def _toggle_inspector(self, visible: bool) -> None:
        self._dock_inspector.setVisible(visible)

    def show_health_center(self) -> None:
        self._show_dialog("Health Center", HealthCenterWidget())

    def show_settings_center(self) -> None:
        self._show_dialog("Settings Center", SettingsCenterDialog())

    def show_log_viewer(self) -> None:
        self._show_dialog("Log Viewer", LogViewerDialog())

    def show_about(self) -> None:
        AboutDialog().exec()

    def _show_dialog(self, title: str, widget: QWidget) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        layout = QVBoxLayout(dialog)
        layout.addWidget(widget)
        dialog.resize(760, 540)
        dialog.exec()

    def export_current_workspace_table(
        self,
        path: str | None = None,
        *,
        export_format: str = "csv",
    ) -> str:
        if self._workspace is None:
            raise RuntimeError("Workspace not initialized")
        current_widget = self._workspace.currentWidget()
        if current_widget is None:
            raise RuntimeError("No active workspace tab")
        table = current_widget
        if not (hasattr(table, "columnCount") and hasattr(table, "rowCount")):
            table = getattr(current_widget, "table", None)
        if table is None or not (hasattr(table, "columnCount") and hasattr(table, "rowCount")):
            raise RuntimeError("Active workspace tab does not expose a table")
        headers = [
            (
                table.horizontalHeaderItem(index).text()
                if table.horizontalHeaderItem(index) is not None
                else str(index)
            )
            for index in range(table.columnCount())
        ]
        rows: list[list[object]] = []
        for row_index in range(table.rowCount()):
            row: list[object] = []
            for column_index in range(table.columnCount()):
                item = table.item(row_index, column_index)
                row.append(item.text() if item is not None else "")
            rows.append(row)
        return self._export_service.export_records(
            path or "workspace-export",
            headers=headers,
            rows=rows,
            export_format=export_format,
        )

    @property
    def workspace(self) -> Workspace:
        if self._workspace is None:
            raise RuntimeError("Workspace not initialized")
        return self._workspace

    @property
    def inspector(self) -> InspectorPanel:
        return self._inspector

    def _apply_theme(self) -> None:
        self._theme_service.apply(self)
