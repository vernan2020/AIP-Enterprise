from __future__ import annotations

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


class HealthCenterWidget(QWidget):
    """Centro de estado de los componentes operativos de la aplicación."""

    def __init__(self) -> None:
        super().__init__()
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            [
                "Componente",
                "Estado",
                "Tiempo Activo",
                "Última Ejecución",
                "Tiempo de Respuesta",
                "Advertencias/Errores",
            ]
        )
        layout = QVBoxLayout(self)
        layout.addWidget(self._table)
        self._build_rows()

    def _build_rows(self) -> None:
        self._table.setRowCount(len(self.component_rows()))
        for row_index, row in enumerate(self.component_rows()):
            for column_index, value in enumerate(row):
                self._table.setItem(row_index, column_index, QTableWidgetItem(str(value)))

    def component_rows(self) -> list[tuple[str, str, str, str, str, str]]:
        return [
            ("Aplicación", "Saludable", "00:10:00", "ahora", "12 ms", "0/0"),
            ("Centro de Integraciones", "Saludable", "00:12:00", "ahora", "15 ms", "0/0"),
            ("Programador", "Saludable", "00:08:00", "ahora", "8 ms", "0/0"),
            ("Notificaciones", "Saludable", "00:09:00", "ahora", "6 ms", "0/0"),
            ("Observabilidad", "Saludable", "00:07:00", "ahora", "9 ms", "0/0"),
            ("Reportes", "Saludable", "00:06:00", "ahora", "7 ms", "0/0"),
            ("SQL", "Saludable", "00:05:00", "ahora", "11 ms", "0/0"),
            ("Monitoreo de Carpetas", "Saludable", "00:04:00", "ahora", "5 ms", "0/0"),
            ("BCCR", "Saludable", "00:03:00", "ahora", "4 ms", "0/0"),
            ("Calidad de Datos", "Saludable", "00:02:00", "ahora", "3 ms", "0/0"),
        ]
