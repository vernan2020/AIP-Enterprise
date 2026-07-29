from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QTextEdit, QVBoxLayout


class ExceptionDialog(QDialog):
    def __init__(self, exception: Exception) -> None:
        super().__init__()
        self.setWindowTitle("Unexpected Error")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("An unexpected error occurred."))
        details = QTextEdit(str(exception))
        details.setReadOnly(True)
        layout.addWidget(details)
