from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class ExecutiveKPIWidget(QFrame):
    """Compact contextual strip for secondary executive indicators."""

    def __init__(self, items: tuple[str, ...]) -> None:
        super().__init__()
        self.setObjectName("executiveKpiStrip")
        self.setStyleSheet(
            "QFrame#executiveKpiStrip {background:#F7FAFC; border:1px solid #D7E0E8; "
            "border-radius:9px;}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(18)

        for item in items:
            cell = QWidget()
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(1)
            value = QLabel(item)
            value.setWordWrap(True)
            value.setStyleSheet("color:#17324D; font-size:9px; font-weight:700; border:none;")
            cell_layout.addWidget(value)
            layout.addWidget(cell, 1)
