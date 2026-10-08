from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class ExecutiveDonutChart(QFrame):
    """Compact value card pending a typed composition series from the presenter."""

    def __init__(self, label: str, value: str) -> None:
        super().__init__()
        self.setObjectName("executiveCompositionCard")
        self.setStyleSheet(
            "QFrame#executiveCompositionCard {background:#FFFFFF; border:1px solid #D7E0E8; "
            "border-radius:9px;}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)

        title = QLabel(label)
        title.setStyleSheet("color:#657D8C; font-size:8px; border:none;")
        metric = QLabel(value)
        metric.setStyleSheet("color:#00345F; font-size:13px; font-weight:800; border:none;")

        layout.addWidget(title)
        layout.addWidget(metric)
