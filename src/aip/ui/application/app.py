from __future__ import annotations

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from aip.core.version import APP_NAME, APP_VERSION
from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.product.demo.configuration.environment_loader import EnvironmentLoader
from aip.ui.shell.main_window import MainWindow


class AIPApplication:
    """Small application wrapper for the desktop shell."""

    def __init__(
        self,
        argv: list[str] | None = None,
        *,
        application_factory: DemoApplicationFactory | None = None,
    ) -> None:
        self._qt_app: QCoreApplication = QApplication.instance() or QApplication(argv or [])
        self._qt_app.setApplicationName(APP_NAME)
        self._qt_app.setApplicationVersion(APP_VERSION)
        self._window: MainWindow | None = None
        if application_factory is None:
            loader = EnvironmentLoader()
            config = loader.load()
            source_config = loader.load_source_config()
            application_factory = DemoApplicationFactory(
                config,
                source_config=source_config,
            )

        self._factory = application_factory

    @property
    def qt_app(self) -> QCoreApplication:
        return self._qt_app

    @property
    def factory(self) -> DemoApplicationFactory:
        return self._factory

    def create_window(self) -> MainWindow:
        self._window = MainWindow(
            demo_factory=self._factory,
        )
        self._window.showMaximized()
        return self._window

    def exec(self) -> int:
        return self._qt_app.exec()
