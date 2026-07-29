from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from aip.ui.modules.liquidity.models.liquidity_row import LiquidityRow


class HQLAView(QWidget):
    def __init__(self, rows: tuple[LiquidityRow, ...]) -> None:
        super().__init__()
        self._rows = rows
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("HQLA"))
        for row in self._rows:
            layout.addWidget(QLabel(f"{row.label}: {row.value} ({row.policy_reference})"))
