from __future__ import annotations

from aip.ui.services.notification_service import NotificationService
from aip.ui.services.theme_service import ThemeService
from aip.ui.services.ui_event_bus import UIEventBus


def test_services_initialize_without_errors() -> None:
    event_bus = UIEventBus()
    assert event_bus is not None

    notification_service = NotificationService()
    assert notification_service is not None

    theme_service = ThemeService()
    assert theme_service is not None
