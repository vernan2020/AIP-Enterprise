from __future__ import annotations

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLabel, QMainWindow, QStatusBar, QVBoxLayout, QWidget
except ModuleNotFoundError:  # pragma: no cover - exercised in headless test environment
    class Qt:  # type: ignore[override]
        class AlignmentFlag:  # type: ignore[override]
            AlignCenter = 0

    class QLabel:  # type: ignore[override]
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.text = ""

        def setAlignment(self, *args: object, **kwargs: object) -> None:
            return None

        def setStyleSheet(self, *args: object, **kwargs: object) -> None:
            return None

    class QMainWindow:  # type: ignore[override]
        def __init__(self, *args: object, **kwargs: object) -> None:
            self._central_widget = None

        def setWindowTitle(self, *args: object, **kwargs: object) -> None:
            return None

        def resize(self, *args: object, **kwargs: object) -> None:
            return None

        def setCentralWidget(self, widget: object) -> None:
            self._central_widget = widget

        def setStatusBar(self, *args: object, **kwargs: object) -> None:
            return None

    class QStatusBar:  # type: ignore[override]
        def showMessage(self, *args: object, **kwargs: object) -> None:
            return None

    class QVBoxLayout:  # type: ignore[override]
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.widgets = []

        def addStretch(self, *args: object, **kwargs: object) -> None:
            return None

        def addWidget(self, *args: object, **kwargs: object) -> None:
            return None

    class QWidget:  # type: ignore[override]
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.layout = None

        def setLayout(self, layout: object) -> None:
            self.layout = layout

from aip.core.version import APP_NAME, APP_RELEASE, APP_VERSION
from aip.infrastructure.configuration.models import Settings
from aip.infrastructure.database.manager import DatabaseManager


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings, database: DatabaseManager) -> None:
        super().__init__()
        self._settings = settings
        self._database = database
        self._build()

    def _build(self) -> None:
        app = self._settings.application
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(app.window_width, app.window_height)

        title = QLabel(APP_NAME)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 30px; font-weight: 700;")

        subtitle = QLabel("Foundation operativa")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 18px;")

        schema_version = self._database.scalar(
            "SELECT value FROM system_metadata WHERE key = 'schema_version'"
        )
        database_status = QLabel(f"DuckDB: {self._database.path}\nEsquema: {schema_version}")
        database_status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout()
        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(database_status)
        layout.addStretch()

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        status = QStatusBar()
        status.showMessage(f"{APP_RELEASE} | {app.organization} | Ambiente: {app.environment}")
        self.setStatusBar(status)
