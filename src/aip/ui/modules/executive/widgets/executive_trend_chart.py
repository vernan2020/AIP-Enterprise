from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class ExecutiveTrendChart(QFrame):
    """Presentation card for externally prepared trend points.

    This widget intentionally does not infer or recalculate numeric series from
    display strings. A plotted chart is enabled only when a typed trend model is
    introduced upstream.
    """

    def __init__(self, label: str, points: tuple[str, ...]) -> None:
        super().__init__()
        self.setObjectName("executiveTrendCard")
        self.setStyleSheet(
            "QFrame#executiveTrendCard {background:#FFFFFF; border:1px solid #D7E0E8; "
            "border-radius:9px;}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        title = QLabel(label)
        title.setStyleSheet("color:#00477F; font-size:9px; font-weight:800; border:none;")
        values = QLabel(" · ".join(points) if points else "Sin serie disponible")
        values.setWordWrap(True)
        values.setStyleSheet("color:#52687A; font-size:9px; border:none;")

        layout.addWidget(title)
        layout.addWidget(values)
