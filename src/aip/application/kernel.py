from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:
    from PySide6.QtWidgets import QApplication
except Exception:  # pragma: no cover - exercised in headless test environments
    QApplication = Any  # type: ignore[assignment,misc]

from aip.core.bootstrap import BootstrapServices

if TYPE_CHECKING:
    from aip.ui.main_window import MainWindow
else:
    try:
        from aip.ui.main_window import MainWindow
    except Exception:  # pragma: no cover - exercised in headless test environments
        MainWindow = Any  # type: ignore[assignment,misc]


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
