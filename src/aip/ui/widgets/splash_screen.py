from __future__ import annotations

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QSplashScreen


class SplashScreen(QSplashScreen):
    def __init__(self, pixmap: QPixmap | None = None) -> None:
        super().__init__(pixmap or QPixmap())
