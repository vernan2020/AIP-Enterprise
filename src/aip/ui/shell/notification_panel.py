from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class NotificationPanel(QWidget):
    """Cola de notificaciones acoplable."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Notificaciones"))
        layout.addWidget(QLabel("Sin notificaciones"))
