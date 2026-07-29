from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout


class AboutDialog(QDialog):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("About AIP Enterprise")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("AIP Enterprise desktop shell"))
