from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from aip.ui.modules.executive.models.executive_row import ExecutiveRow


class ExecutiveAlertPanel(QFrame):
    """Compact prioritized alert panel; no synthetic severity or metrics are derived."""

    def __init__(self, alerts: tuple[ExecutiveRow, ...]) -> None:
        super().__init__()
        self.setObjectName("executiveAlertPanel")
        self.setStyleSheet(
            "QFrame#executiveAlertPanel {background:#FFFFFF; border:1px solid #D7E0E8; "
            "border-radius:9px;}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)

        title = QLabel("ALERTAS")
        title.setStyleSheet("color:#00477F; font-size:9px; font-weight:800; border:none;")
        layout.addWidget(title)

        if not alerts:
            empty = QLabel("Sin alertas disponibles para el corte.")
            empty.setStyleSheet("color:#718096; font-size:9px; border:none;")
            layout.addWidget(empty)
            return

        for item in alerts:
            label = QLabel(f"{item.severity} · {item.category} · {item.title}")
            label.setWordWrap(True)
            label.setToolTip(item.detail)
            label.setStyleSheet("color:#354B5E; font-size:9px; border:none; padding:2px 0;")
            layout.addWidget(label)
