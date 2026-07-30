from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QLabel, QVBoxLayout, QWidget


class SettingsCenterDialog(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Settings Center")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Environment", QLabel("demo"))
        form.addRow("Paths", QLabel("/config, /data, /logs"))
        form.addRow("Enabled Connectors", QLabel("SQL, Folder Watch, BCCR"))
        form.addRow("Scheduler Configuration", QLabel("Enabled"))
        form.addRow("Notification Providers", QLabel("Console"))
        form.addRow("Logging Level", QLabel("INFO"))
        form.addRow("Theme", QLabel("Light"))
        form.addRow("Demo Mode", QLabel("Enabled"))
        layout.addLayout(form)

    def is_read_only(self) -> bool:
        return True
