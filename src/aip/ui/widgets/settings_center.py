from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QLabel, QVBoxLayout, QWidget


class SettingsCenterDialog(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Centro de Configuración")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Entorno", QLabel("demostración"))
        form.addRow("Rutas", QLabel("/config, /data, /logs"))
        form.addRow("Conectores Habilitados", QLabel("SQL, Monitoreo de Carpetas, BCCR"))
        form.addRow("Configuración del Programador", QLabel("Habilitado"))
        form.addRow("Proveedores de Notificación", QLabel("Consola"))
        form.addRow("Nivel de Registro", QLabel("INFO"))
        form.addRow("Tema", QLabel("Claro"))
        form.addRow("Modo Demostración", QLabel("Habilitado"))
        layout.addLayout(form)

    def is_read_only(self) -> bool:
        return True
