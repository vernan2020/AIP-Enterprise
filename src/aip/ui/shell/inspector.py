from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget


class InspectorPanel(QWidget):
    """Inspector contextual del contenido seleccionado."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Inspector"))
        detail = QTextEdit("Seleccione un elemento para inspeccionar sus detalles.")
        detail.setReadOnly(True)
        layout.addWidget(detail)
