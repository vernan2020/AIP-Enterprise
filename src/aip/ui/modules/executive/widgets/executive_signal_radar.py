"""Executive decision radar built solely from certified presenter signal rows.

This is a count visualization, not a replacement for financial-risk engines.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QProgressBar, QVBoxLayout

from aip.ui.modules.executive.models.executive_row import ExecutiveRow


class ExecutiveSignalRadar(QFrame):
    """Legible signal volumes and severity, with no synthetic financial values."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("executiveSignalRadar")
        self.setMinimumHeight(122)
        self.setStyleSheet(
            "QFrame#executiveSignalRadar {background:#FFFFFF;"
            "border:1px solid #C9DDE9; border-radius:12px;}"
            "QFrame#executiveSignalRadar QLabel {border:none; background:transparent;}"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(13, 9, 13, 10)
        root.setSpacing(7)
        title = QLabel("RADAR DE SEÑALES · INFORMACIÓN CONSOLIDADA")
        title.setStyleSheet("font-size:10pt; font-weight:800; color:#00345F;")
        title.setWordWrap(True)
        root.addWidget(title)
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(6)
        self._counts: dict[str, QLabel] = {}
        self._bars: dict[str, QProgressBar] = {}
        for col, (key, caption, color) in enumerate(
            (
                ("alerts", "Alertas registradas", "#E4002B"),
                ("high", "Severidad alta/crítica", "#FF8200"),
                ("recommendations", "Observaciones y oportunidades", "#005EB8"),
            )
        ):
            text = QLabel(caption)
            text.setWordWrap(True)
            text.setStyleSheet("color:#566D7C; font-size:9pt;")
            number = QLabel("0")
            number.setAccessibleName(f"Cantidad: {caption}")
            number.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            number.setStyleSheet("color:#00345F; font-size:15pt; font-weight:800;")
            bar = QProgressBar()
            bar.setRange(0, 1)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setMaximumHeight(9)
            bar.setStyleSheet(
                "QProgressBar {background:#EDF3F7; border:none; border-radius:4px;}"
                f"QProgressBar::chunk {{background:{color}; border-radius:4px;}}"
            )
            grid.addWidget(text, 0, col)
            grid.addWidget(number, 1, col)
            grid.addWidget(bar, 2, col)
            self._counts[key] = number
            self._bars[key] = bar
        root.addLayout(grid)

    @staticmethod
    def _high_priority(severity: str) -> bool:
        return str(severity).strip().casefold() in {
            "high",
            "critical",
            "alta",
            "alto",
            "crítica",
            "critica",
        }

    def set_rows(
        self, alerts: tuple[ExecutiveRow, ...], recommendations: tuple[ExecutiveRow, ...]
    ) -> None:
        counts = {
            "alerts": len(alerts),
            "high": sum(self._high_priority(item.severity) for item in alerts),
            "recommendations": len(recommendations),
        }
        largest = max(1, counts["alerts"], counts["recommendations"])
        for key, value in counts.items():
            self._counts[key].setText(str(value))
            self._bars[key].setRange(0, largest)
            self._bars[key].setValue(value)
        self.setToolTip(
            "Conteos de señales emitidas por los servicios institucionales. "
            "Las barras comparan cantidades, no magnitudes financieras ni severidad calculada."
        )
