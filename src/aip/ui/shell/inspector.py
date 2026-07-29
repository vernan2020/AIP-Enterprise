from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget


class InspectorPanel(QWidget):
    """Context inspector for selected workspace content."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Inspector"))
        layout.addWidget(QTextEdit("Select an item to inspect details."))
