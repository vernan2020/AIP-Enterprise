from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LiquidityMetricCard(QWidget):
    def __init__(self, label: str, value: str) -> None:
        super().__init__()
        self._label = QLabel(label)
        self._value = QLabel(value)
        layout = QVBoxLayout(self)
        layout.addWidget(self._label)
        layout.addWidget(self._value)

    def text(self) -> str:
        return self._label.text()

    def setText(self, value: str) -> None:
        self._value.setText(value)
