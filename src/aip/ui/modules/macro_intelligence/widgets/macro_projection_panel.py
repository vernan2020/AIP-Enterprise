from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from aip.product.configured.services.configured_macro_intelligence_service import (
    ConfiguredMacroIntelligenceService,
)
from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory


class MacroProjectionPanel(QGroupBox):
    """Presentation panel for the approved institutional macro scenario.

    The panel contains no forecasting logic. It only resolves the configured
    application service and renders the governed scenario already persisted by
    the economic/econometric layer.
    """

    _COLUMNS = (
        "Periodo",
        "USD/CRC",
        "TPM",
        "TBP",
        "TRI CRC 12M",
        "TRI USD 12M",
        "Inflación",
        "IMAE",
    )

    def __init__(
        self,
        *,
        application_factory: DemoApplicationFactory,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("PROYECCIÓN MACROECONÓMICA INSTITUCIONAL", parent)
        self._application_factory = application_factory
        self._status = QLabel("Cargando escenario institucional...")
        self._status.setWordWrap(True)

        self._table = QTableWidget(0, len(self._COLUMNS))
        self._table.setHorizontalHeaderLabels(list(self._COLUMNS))
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setMinimumHeight(300)

        layout = QVBoxLayout(self)
        layout.addWidget(self._status)
        layout.addWidget(self._table)

        self.refresh_projection()

    def refresh_projection(self) -> None:
        try:
            service = self._application_factory.container.resolve(
                ConfiguredMacroIntelligenceService
            )
            payload = service.get_projection()
        except Exception as exc:
            self._show_unavailable(f"{type(exc).__name__}: {exc}")
            return

        if str(payload.get("status", "")).upper() != "AVAILABLE":
            self._show_unavailable(str(payload.get("diagnostic") or "Escenario no disponible"))
            return

        rows = payload.get("rows") or []
        self._table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            values = (
                self._period(row.get("period")),
                self._number(row.get("fx_sell"), decimals=2),
                self._percent(row.get("tpm")),
                self._percent(row.get("tbp")),
                self._percent(row.get("tri_crc_12m")),
                self._percent(row.get("tri_usd_12m")),
                self._percent(row.get("inflation")),
                self._percent(row.get("imae")),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column > 0:
                    item.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))
                self._table.setItem(row_index, column, item)

        dataset_date = payload.get("dataset_as_of_date")
        scenario_type = payload.get("scenario_type") or "BASE"
        scenario_status = payload.get("scenario_status") or "APPROVED"
        scenario_id = payload.get("scenario_id") or "BASE-MACRO-INSTITUTIONAL"
        version = payload.get("version")
        horizon = payload.get("horizon") or len(rows)
        self._status.setText(
            f"{scenario_id} · v{version} · {scenario_type} · {scenario_status} · "
            f"Dataset as-of: {dataset_date} · Horizonte: {horizon} meses"
        )

    def _show_unavailable(self, diagnostic: str) -> None:
        self._table.setRowCount(0)
        self._status.setText(f"Escenario institucional no disponible · {diagnostic}")

    @staticmethod
    def _period(value: Any) -> str:
        if value is None:
            return "N/D"
        if hasattr(value, "strftime"):
            return value.strftime("%b-%Y").upper()
        text = str(value)
        if len(text) >= 7:
            return text[:7]
        return text

    @staticmethod
    def _number(value: Any, *, decimals: int = 2) -> str:
        if value is None:
            return "N/D"
        try:
            return f"{float(value):,.{decimals}f}"
        except (TypeError, ValueError):
            return str(value)

    @classmethod
    def _percent(cls, value: Any) -> str:
        number = cls._number(value, decimals=2)
        return "N/D" if number == "N/D" else f"{number}%"
