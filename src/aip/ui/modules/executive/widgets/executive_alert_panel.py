from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from aip.ui.modules.executive.models.executive_row import ExecutiveRow


class ExecutiveAlertPanel(QWidget):
    def __init__(self, alerts: tuple[ExecutiveRow, ...]) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Alerts"))
        for item in alerts:
            layout.addWidget(QLabel(f"{item.category}: {item.severity}: {item.title}"))
