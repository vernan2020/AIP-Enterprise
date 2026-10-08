from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class ExecutiveMetricCard(QFrame):
    """Compact executive metric tile used by secondary executive views."""

    def __init__(self, title: str, value: str) -> None:
        super().__init__()
        self.setObjectName("executiveMetricCard")
        self.setMinimumHeight(72)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(2)

        caption = QLabel(title)
        caption.setStyleSheet("color:#657D8C; font-size:8px; border:none;")
        metric = QLabel(value)
        metric.setStyleSheet("color:#00345F; font-size:13px; font-weight:800; border:none;")
        metric.setWordWrap(True)

        layout.addWidget(caption)
        layout.addWidget(metric)
