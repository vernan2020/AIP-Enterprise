from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from aip.ui.modules.executive.models.executive_row import ExecutiveRow


class ExecutiveDecisionsView(QWidget):
    def __init__(self, recommendations: tuple[ExecutiveRow, ...]) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        for item in recommendations:
            layout.addWidget(QLabel(f"{item.title}: {item.detail}"))
