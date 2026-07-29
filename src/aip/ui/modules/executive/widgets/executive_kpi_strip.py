from __future__ import annotations

from PySide6.QtWidgets import QLabel, QHBoxLayout, QWidget


class ExecutiveKPIWidget(QWidget):
    def __init__(self, items: tuple[str, ...]) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        for item in items:
            layout.addWidget(QLabel(item))
