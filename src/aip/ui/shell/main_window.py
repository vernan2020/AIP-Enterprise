from __future__ import annotations

from datetime import date
from typing import cast

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

from aip.core.version import APP_DISPLAY_VERSION
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
    """Entorno de escritorio institucional de AIP Enterprise."""

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
            Route("macro_intelligence", "Inteligencia Macroeconómica", "macro"),
            Route("liquidity", "Liquidez", "liquidity"),
            Route("treasury", "Tesorería", "treasury"),
            Route("financial_analysis", "Análisis Financiero", "financial_analysis"),
            Route("reports", "Reportes", "reports"),
        ]
        self._navigation.register_many(routes)
        self._navigation.navigate("home")

    def _build_ui(self) -> None:
        self._ribbon = Ribbon()
        ribbon_routes = {
            "Inicio": "home",
            "Ejecutivo": "executive",
            "Portafolio": "portfolio",
            "Mercado": "market",
            "Riesgo de Precio": "price_risk",
            "Inteligencia Macroeconómica": "macro_intelligence",
            "Liquidez": "liquidity",
            "Tesorería": "treasury",
            "Análisis Financiero": "financial_analysis",
            "Reportes": "reports",
        }
        for label, route_id in ribbon_routes.items():
            self._ribbon.action(label).triggered.connect(
                lambda _checked=False, route=route_id: self.open_workspace(route)
            )
        self._ribbon.action("Actualizar Todo").triggered.connect(self._handle_refresh_all)
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

        self._dock_notifications = QDockWidget("Notificaciones", self)
        self._dock_notifications.setWidget(self._notifications_panel)
        self._dock_notifications.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea,
            self._dock_notifications,
        )
        self._dock_notifications.hide()

        self._system_status_text = QTextEdit()
        self._system_status_text.setReadOnly(True)
        self._dock_status = QDockWidget("Estado del Sistema", self)
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
        frame.setMinimumHeight(62)
        frame.setMaximumHeight(66)
        frame.setStyleSheet(
            "QFrame#institutionalHeader {background:#005EB8; border:none;}"
            "QFrame#institutionalHeader QLabel {background:transparent; border:none; color:#FFFFFF;}"
            "QLabel#headerMode {background:#00477F; border:1px solid #00A9E0; border-radius:10px; "
            "padding:4px 9px; color:#FFFFFF; font-size:9px; font-weight:700;}"
            "QLabel#headerStatus {background:#2B9E8B; border:1px solid #40C1AC; border-radius:10px; "
            "padding:4px 9px; color:#FFFFFF; font-size:9px; font-weight:700;}"
            "QDateEdit {min-width:112px; padding:5px 8px; background:#FFFFFF; color:#00345F; "
            "border:1px solid #73B3DD; border-radius:5px;}"
        )
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setSpacing(12)
        execution_mode = self._config.execution_mode

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title = QLabel("AIP ENTERPRISE 2.0")
        title.setStyleSheet(
            "font-size:14px; font-weight:800; letter-spacing:0.7px; background:transparent;"
        )
        subtitle = QLabel("PLATAFORMA DE INTELIGENCIA FINANCIERA")
        subtitle.setStyleSheet(
            "font-size:8px; color:#D9F4FC; letter-spacing:1px; background:transparent;"
        )
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box)

        mode = QLabel("MODO CONFIGURADO" if execution_mode == "CONFIGURED" else "MODO DEMO")
        mode.setObjectName("headerMode")
        layout.addWidget(mode)
        layout.addStretch(1)

        self._header_status = QLabel("SISTEMA LISTO")
        self._header_status.setObjectName("headerStatus")
        layout.addWidget(self._header_status)

        cutoff_label = QLabel("CORTE")
        cutoff_label.setStyleSheet(
            "font-size:8px; color:#D9F4FC; font-weight:700; background:transparent;"
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
            raise RuntimeError("Espacio de trabajo no inicializado")
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
                "Inteligencia Macroeconómica",
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
        if route_id == "financial_analysis":
            from aip.ui.modules.financial_analysis.presenters.financial_analysis_presenter import (
                FinancialAnalysisPresenter,
            )
            from aip.ui.modules.financial_analysis.views.financial_analysis_view import (
                FinancialAnalysisView,
            )

            return (
                FinancialAnalysisView(presenter=FinancialAnalysisPresenter(self._demo_factory)),
                "Análisis Financiero",
            )
        if route_id == "reports":
            from aip.ui.modules.reports.views.reports_view import ReportsView

            return (ReportsView(), "Reportes")
        raise KeyError(f"Ruta desconocida: {route_id}")

    def _handle_qdate_changed(self, value: QDate) -> None:
        selected = date(value.year(), value.month(), value.day())
        try:
            self._valuation_context.set_valuation_date(selected)
        except Exception as exc:
            current = self._valuation_context.valuation_date
            self._date_edit.blockSignals(True)
            self._date_edit.setDate(QDate(current.year, current.month, current.day))
            self._date_edit.blockSignals(False)
            QMessageBox.warning(
                self,
                "Fecha de valoración",
                f"No se pudo cambiar la fecha de valoración.\n\nDetalle:\n{exc}",
            )
            return
        self._status_bar.set_message(f"Corte activo: {selected:%d/%m/%Y}")
        self._handle_refresh_all()

    def _handle_refresh_all(self) -> None:
        if self._workspace is None:
            return
        self._header_status.setText("ACTUALIZANDO")
        try:
            from aip.product.configured.adapters.configured_portfolio_provider import (
                ConfiguredPortfolioProvider,
            )
            from aip.product.configured.services.configured_portfolio_var_service import (
                ConfiguredPortfolioVaRService,
            )

            self._demo_factory.container.resolve(ConfiguredPortfolioProvider).clear_cache()
            self._demo_factory.container.resolve(ConfiguredPortfolioVaRService).clear_result_cache()
        except Exception:
            # Demo mode and reduced test containers do not register configured caches.
            pass
        refreshed = 0
        for index in range(self._workspace.count()):
            widget = self._workspace.widget(index)
            refresh = getattr(widget, "refresh", None)
            if callable(refresh):
                try:
                    refresh()
                    refreshed += 1
                except Exception as exc:
                    self._notifications.push(
                        "warning",
                        f"No se pudo actualizar {self._workspace.tabText(index)}: {exc}",
                    )
        self._header_status.setText("SISTEMA LISTO")
        self._status_bar.set_message(f"Actualización completada · {refreshed} módulos")
        self._refresh_status_panel()

    def _add_operational_menu_actions(self) -> None:
        view_menu = self.menuBar().addMenu("Vista")
        inspector_action = view_menu.addAction("Inspector")
        inspector_action.setCheckable(True)
        inspector_action.triggered.connect(
            lambda checked: self._dock_inspector.setVisible(bool(checked))
        )
        self._inspector_action = inspector_action

        notifications_action = view_menu.addAction("Notificaciones")
        notifications_action.setCheckable(True)
        notifications_action.triggered.connect(
            lambda checked: self._dock_notifications.setVisible(bool(checked))
        )

        status_action = view_menu.addAction("Estado del Sistema")
        status_action.setCheckable(True)
        status_action.triggered.connect(lambda checked: self._dock_status.setVisible(bool(checked)))

        tools_menu = self.menuBar().addMenu("Herramientas")
        tools_menu.addAction("Centro de Estado", self._show_health_center)
        tools_menu.addAction("Configuración", self._show_settings_center)
        tools_menu.addAction("Visor de Registros", self._show_log_viewer)
        tools_menu.addSeparator()
        tools_menu.addAction("Tema Claro", lambda: self._set_theme("light"))
        tools_menu.addAction("Tema Oscuro", lambda: self._set_theme("dark"))

        help_menu = self.menuBar().addMenu("Ayuda")
        help_menu.addAction("Acerca de AIP Enterprise", self._show_about)

    def _show_health_center(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Centro de Estado")
        layout = QVBoxLayout(dialog)
        layout.addWidget(HealthCenterWidget())
        dialog.resize(820, 560)
        dialog.exec()

    def _show_settings_center(self) -> None:
        SettingsCenterDialog(self).exec()

    def _show_log_viewer(self) -> None:
        LogViewerDialog(self).exec()

    def _show_about(self) -> None:
        AboutDialog(self).exec()

    def _set_theme(self, theme_name: str) -> None:
        self._theme_service.set_theme(theme_name)
        self._apply_theme()

    def _apply_theme(self) -> None:
        app = cast(QApplication | None, QApplication.instance())
        if app is not None:
            app.setStyleSheet(self._theme_service.stylesheet())

    def _refresh_status_panel(self) -> None:
        if self._system_status_text is None:
            return
        try:
            report = self._diagnostic_service.evaluate()
            self._system_status_text.setPlainText(str(report))
        except Exception as exc:
            self._system_status_text.setPlainText(f"Diagnóstico no disponible: {exc}")

    def closeEvent(self, event) -> None:  # noqa: N802
        self._window_state.save(self)
        super().closeEvent(event)
