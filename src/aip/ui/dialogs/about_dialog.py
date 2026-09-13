from __future__ import annotations

import platform

from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout

from aip.core.version import (
    APP_DISPLAY_NAME,
    APP_DISPLAY_VERSION,
    APP_NAME,
    APP_RELEASE,
    APP_VERSION,
    ORGANIZATION,
)


class AboutDialog(QDialog):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Acerca de AIP Enterprise")
        self._text = self.release_text()
        layout = QVBoxLayout(self)
        label = QLabel(self._text)
        label.setWordWrap(True)
        layout.addWidget(label)

    def release_text(self) -> str:
        return "\n".join(
            [
                f"{APP_DISPLAY_NAME}",
                f"{APP_DISPLAY_VERSION}",
                f"Versión: {APP_VERSION}",
                f"Version: {APP_VERSION}",
                f"Edición: {APP_RELEASE}",
                f"Python: {platform.python_version()}",
                f"Organización: {ORGANIZATION}",
                f"Aplicación: {APP_NAME}",
            ]
        )
