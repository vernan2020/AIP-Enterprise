"""Detail inspector connected to the selected real financial instrument."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class PortfolioDetailsView(QWidget):
    FIELDS = (
        ("isin", "ISIN"),
        ("issuer", "Emisor"),
        ("instrument", "Instrumento"),
        ("currency", "Moneda"),
        ("nominal", "Nominal"),
        ("market_value", "Valor de mercado"),
        ("book_value", "Valor en libros"),
        ("yield_value", "TIR"),
        ("modified_duration", "Duración modificada"),
        ("classification", "Clasificación"),
        ("hqla_status", "Elegibilidad HQLA"),
        ("mil_status", "Elegibilidad MIL"),
        ("recommendation", "Recomendación"),
    )

    def __init__(self, selected_row: object | None = None) -> None:
        super().__init__()
        self.setObjectName("portfolioDetailsView")
        self.setMinimumWidth(255)
        self.setStyleSheet(
            "QWidget#portfolioDetailsView {background:#F5FAFD;"
            "border:1px solid #C9DDE9; border-radius:10px;}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        title = QLabel("DETALLE DEL INSTRUMENTO")
        title.setStyleSheet("color:#00345F; font-size:11pt; font-weight:800; border:none;")
        title.setWordWrap(True)
        layout.addWidget(title)
        self._selected_label = QLabel("")
        self._selected_label.setWordWrap(True)
        self._selected_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._selected_label.setStyleSheet(
            "color:#005EB8; font-size:10pt; font-weight:700; border:none;"
        )
        layout.addWidget(self._selected_label)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        grid = QGridLayout(body)
        grid.setColumnStretch(1, 1)
        grid.setContentsMargins(0, 3, 0, 3)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(9)
        self._values: dict[str, QLabel] = {}
        for index, (key, caption) in enumerate(self.FIELDS):
            label = QLabel(caption)
            label.setWordWrap(True)
            label.setStyleSheet("color:#566D7C; font-size:9pt;")
            value = QLabel("—")
            value.setObjectName(f"portfolioDetail_{key}")
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value.setStyleSheet("color:#17324D; font-size:9.5pt; font-weight:600;")
            grid.addWidget(label, index, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(value, index, 1, Qt.AlignmentFlag.AlignTop)
            self._values[key] = value
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)
        self.bind_row(selected_row)

    def bind_row(self, row: object | None) -> None:
        self._selected_label.setText(
            str(getattr(row, "isin", "Seleccione una posición"))
            if row is not None
            else "Seleccione una posición"
        )
        for key, value in self._values.items():
            raw = getattr(row, key, None) if row is not None else None
            text = str(raw) if raw is not None and str(raw).strip() else "N/D"
            value.setText(text)
            value.setToolTip(text)
