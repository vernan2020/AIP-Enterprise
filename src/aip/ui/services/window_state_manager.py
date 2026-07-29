from __future__ import annotations

from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import QMainWindow


class WindowStateManager:
    """Persists basic window geometry and state."""

    def __init__(self) -> None:
        self._geometry: QByteArray | None = None

    def restore(self, window: QMainWindow) -> None:
        if self._geometry is not None:
            window.restoreGeometry(self._geometry)

    def save(self, window: QMainWindow) -> None:
        self._geometry = window.saveGeometry()
