from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PortfolioDetailsView(QWidget):
    def __init__(self, selected_row: object | None = None) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Instrumento"))
        layout.addWidget(QLabel(getattr(selected_row, "instrument", "Sin selección")))
        layout.addWidget(QLabel("Resumen de Valoración"))
        layout.addWidget(QLabel("Resumen generado por la capa de aplicación"))
        layout.addWidget(QLabel("Referencias de Política"))
        layout.addWidget(QLabel("No aplica"))
