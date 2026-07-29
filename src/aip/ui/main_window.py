from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QStatusBar, QVBoxLayout, QWidget

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
