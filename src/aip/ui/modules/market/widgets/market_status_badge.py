from __future__ import annotations

from PySide6.QtWidgets import QLabel


class MarketStatusBadge(QLabel):
    """Indicador compacto de estado del módulo de Mercado."""

    def __init__(self, text: str = "Ready") -> None:
        super().__init__(text)
        self.setStyleSheet(
            "background:#E2F6F1; color:#167A68; border:1px solid #40C1AC; "
            "padding:4px 8px; border-radius:9px; font-weight:700;"
        )
