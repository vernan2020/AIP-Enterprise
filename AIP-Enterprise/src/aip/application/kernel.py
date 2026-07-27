from __future__ import annotations

try:
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError:  # pragma: no cover - exercised in headless test environment
    class QApplication:  # type: ignore[override]
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.aboutToQuit = None

from aip.core.bootstrap import BootstrapServices
from aip.ui.main_window import MainWindow


class ApplicationKernel:
    def __init__(self, qt_application: QApplication, services: BootstrapServices) -> None:
        self._qt_application = qt_application
        self._services = services
        self._window: MainWindow | None = None

    def run(self) -> int:
        logger = self._services.logging.bind(component="APPLICATION")
        logger.info("Inicializando interfaz")
        self._window = MainWindow(
            settings=self._services.configuration.settings,
            database=self._services.database,
        )
        self._window.show()
        self._qt_application.aboutToQuit.connect(self._shutdown)
        logger.info("AIP Enterprise iniciado")
        return self._qt_application.exec()

    def _shutdown(self) -> None:
        self._services.audit.record("SYSTEM_SHUTDOWN", {})
        self._services.database.close()
        self._services.logging.bind(component="APPLICATION").info("Cierre controlado completado")
