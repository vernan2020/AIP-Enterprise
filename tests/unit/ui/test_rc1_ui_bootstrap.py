from __future__ import annotations

from PySide6.QtWidgets import QApplication

from aip.ui.application.startup import initialize_ui
from aip.ui.navigation.menu_registry import MenuRegistry
from aip.ui.services.notification_service import NotificationService
from aip.ui.services.theme_service import ThemeService
from aip.ui.services.ui_event_bus import UIEventBus
from aip.ui.services.window_state_manager import WindowStateManager


def test_initialize_ui_registers_core_services() -> None:
    app = QApplication.instance() or QApplication([])
    container = initialize_ui()
    assert isinstance(container.resolve(UIEventBus), UIEventBus)
    assert isinstance(container.resolve(NotificationService), NotificationService)
    assert isinstance(container.resolve(ThemeService), ThemeService)
    assert isinstance(container.resolve(WindowStateManager), WindowStateManager)
    app.processEvents()


def test_menu_registry_keeps_labels() -> None:
    registry = MenuRegistry()
    registry.register_many([("portfolio", "Portfolio"), ("market", "Market")])
    assert registry.route_label("portfolio") == "Portfolio"
    assert registry.route_label("market") == "Market"
