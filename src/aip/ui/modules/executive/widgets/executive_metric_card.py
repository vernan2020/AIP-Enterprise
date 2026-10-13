from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout

from aip.ui.themes.typography import numeric_font_family


class ExecutiveMetricCard(QFrame):
    """Institutional KPI presentation for secondary executive pages."""

    def __init__(self, title: str, value: str) -> None:
        super().__init__()
        self.setObjectName("executiveMetricCard")
        self.setAccessibleName(title)
        self.setMinimumHeight(104)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setToolTip(f"{title}: {value}")
        self.setStyleSheet(
            "QFrame#executiveMetricCard {"
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #00477F,stop:0.6 #005EB8,stop:1 #00A9E0);"
            "border:1px solid #1675C5; border-radius:12px;}"
            "QFrame#executiveMetricCard QLabel {background:transparent; border:none;}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(4)

        caption = QLabel(title)
        caption.setWordWrap(True)
        caption.setStyleSheet("color:#DDF4FF; font-size:10pt; font-weight:600;")
        metric = QLabel(value)
        metric_font = QFont(numeric_font_family())
        metric_font.setPointSize(14)
        metric_font.setBold(True)
        metric.setFont(metric_font)
        metric.setStyleSheet("color:#FFFFFF;")
        metric.setWordWrap(True)
        metric.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        metric.setAccessibleName(f"Valor de {title}")

        layout.addWidget(caption)
        layout.addWidget(metric)
