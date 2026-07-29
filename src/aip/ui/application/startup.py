from __future__ import annotations

from aip.core.container import Container
from aip.ui.navigation.navigation_manager import NavigationManager
from aip.ui.services.notification_service import NotificationService
from aip.ui.services.theme_service import ThemeService
from aip.ui.services.ui_event_bus import UIEventBus
from aip.ui.services.window_state_manager import WindowStateManager


def initialize_ui(container: Container | None = None) -> Container:
    container = container or Container()
    container.register_instance(UIEventBus, UIEventBus())
    container.register_instance(NotificationService, NotificationService())
    container.register_instance(ThemeService, ThemeService())
    container.register_instance(NavigationManager, NavigationManager())
    container.register_factory(WindowStateManager, lambda _container: WindowStateManager())
    return container
