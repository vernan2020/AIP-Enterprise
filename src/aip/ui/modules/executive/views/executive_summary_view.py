from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ExecutiveSummaryView(QWidget):
    def __init__(self, summary: tuple[str, ...]) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        for item in summary:
            layout.addWidget(QLabel(item))
